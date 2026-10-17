"""Tests for the pooled, pipelined transfer engine (fast_transfer.py).

A simulated network (`FakeNet`) stands in for Telegram: it enforces the real
upload.getFile alignment rules, injects latency so parts complete out of
order, counts sockets and in-flight requests, and can inject failures.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import random
from pathlib import Path

import pytest
from telethon.errors import FileReferenceExpiredError, FloodWaitError
from telethon.tl.functions.upload import (
    GetFileRequest,
    SaveBigFilePartRequest,
    SaveFilePartRequest,
)
from telethon.tl.types import InputFile, InputFileBig

from telegrab.telegram import fast_transfer as ft

MB = 1024 * 1024


class FakeLocation:
    """Stands in for a Document: `utils.get_input_location` is patched."""

    def __init__(self, size: int) -> None:
        self.size = size


class FakeNet:
    def __init__(self, blob: bytes = b"", *, latency=(0.0, 0.004), connect_cost=0.0):
        self.blob = blob
        self.latency = latency
        self.connect_cost = connect_cost
        self.sockets_opened = 0
        self.open_sockets = 0
        self.max_open_sockets = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self.requests = 0
        self.uploaded: dict[int, bytes] = {}
        self.upload_meta: list[tuple[type, int | None]] = []
        self.fail_next: list[BaseException] = []

    async def sender_factory(self):
        await asyncio.sleep(self.connect_cost)
        self.sockets_opened += 1
        self.open_sockets += 1
        self.max_open_sockets = max(self.max_open_sockets, self.open_sockets)
        net = self

        class Sender:
            def disconnect(self):
                net.open_sockets -= 1

        return Sender()

    async def call(self, sender, request):
        self.requests += 1
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(random.uniform(*self.latency))
            if self.fail_next:
                raise self.fail_next.pop(0)
            if isinstance(request, GetFileRequest):
                off, lim = request.offset, request.limit
                assert off % 4096 == 0 and lim % 4096 == 0, (off, lim)
                assert MB % lim == 0, lim
                assert off // MB == (off + lim - 1) // MB, "request crosses a 1 MB boundary"

                class R:
                    bytes = self.blob[off : off + lim]

                return R()
            if isinstance(request, SaveBigFilePartRequest):
                self.upload_meta.append((SaveBigFilePartRequest, request.file_total_parts))
                self.uploaded[request.file_part] = request.bytes
                return True
            if isinstance(request, SaveFilePartRequest):
                self.upload_meta.append((SaveFilePartRequest, None))
                self.uploaded[request.file_part] = request.bytes
                return True
            raise AssertionError(f"unexpected request {request!r}")
        finally:
            self.in_flight -= 1

    def pool(self, **kw) -> ft.DcPool:
        kw.setdefault("max_connections", 4)
        kw.setdefault("requests_per_connection", 2)
        return ft.DcPool(None, 2, sender_factory=self.sender_factory, call=self.call, **kw)


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch):
    monkeypatch.setattr(ft, "_BACKOFF_START", 0.001)
    monkeypatch.setattr(ft, "_BACKOFF_MAX", 0.002)
    monkeypatch.setattr(
        ft.utils, "get_input_location", lambda loc: (2, getattr(loc, "fresh", "loc"))
    )


async def _download(net, size, tmp_path, pool=None, **kw):
    out = tmp_path / "out.bin"
    await ft.download_file(None, FakeLocation(size), out, pool=pool or net.pool(), **kw)
    return out.read_bytes()


class TestDownload:
    @pytest.mark.parametrize("size", [0, 1, 4096, 300_000, MB, 5 * MB + 12345])
    async def test_reassembles_exactly(self, tmp_path, size):
        blob = os.urandom(size)
        net = FakeNet(blob)
        assert await _download(net, size, tmp_path) == blob

    async def test_respects_connection_and_pipeline_caps(self, tmp_path):
        blob = os.urandom(24 * MB)
        net = FakeNet(blob, latency=(0.002, 0.01))
        pool = net.pool(max_connections=3, requests_per_connection=2)
        assert await _download(net, len(blob), tmp_path, pool=pool) == blob
        assert net.max_open_sockets <= 3
        assert net.max_in_flight <= 6
        # And it actually pipelines (more than one request per socket).
        assert net.max_in_flight > 3

    async def test_progress_is_monotonic_and_complete(self, tmp_path):
        blob = os.urandom(3 * MB + 7)
        net = FakeNet(blob)
        seen: list[int] = []
        await _download(net, len(blob), tmp_path, progress_callback=lambda d, t: seen.append(d))
        assert seen == sorted(seen) and seen[-1] == len(blob)

    async def test_transient_errors_are_retried_on_a_new_connection(self, tmp_path):
        blob = os.urandom(2 * MB)
        net = FakeNet(blob)
        net.fail_next = [ConnectionError("reset"), TimeoutError()]
        assert await _download(net, len(blob), tmp_path) == blob
        assert net.sockets_opened >= 2  # broken sockets were replaced

    async def test_flood_wait_is_waited_out(self, tmp_path):
        blob = os.urandom(MB)
        net = FakeNet(blob)
        net.fail_next = [FloodWaitError(request=None, capture=0)]
        waits: list[float] = []
        assert await _download(net, len(blob), tmp_path, on_flood_wait=waits.append) == blob
        assert waits == [0.0]

    async def test_long_flood_wait_fails_fast(self, tmp_path):
        net = FakeNet(os.urandom(MB))
        net.fail_next = [FloodWaitError(request=None, capture=10_000)]
        with pytest.raises(FloodWaitError):
            await _download(net, MB, tmp_path)

    async def test_expired_file_reference_is_refreshed(self, tmp_path):
        blob = os.urandom(MB)
        net = FakeNet(blob)
        net.fail_next = [FileReferenceExpiredError(request=None)]
        refreshed = []

        async def refresh():
            refreshed.append(1)
            loc = FakeLocation(len(blob))
            loc.fresh = "fresh-loc"
            return loc

        assert await _download(net, len(blob), tmp_path, refresh_location=refresh) == blob
        assert refreshed == [1]

    async def test_cancel_from_progress_stops_all_workers(self, tmp_path):
        net = FakeNet(os.urandom(40 * MB))

        def progress(done, total):
            if done >= 2 * MB:
                raise FtCancelError("stop")

        with pytest.raises(FtCancelError):
            await _download(net, 40 * MB, tmp_path, progress_callback=progress)
        requests_at_cancel = net.requests
        await asyncio.sleep(0.05)
        assert net.requests == requests_at_cancel  # nothing keeps running
        assert net.requests < 40


    async def test_slow_disk_bounds_read_ahead(self, tmp_path, monkeypatch):
        """Fetching never runs far ahead of the disk (bounded memory)."""
        blob = os.urandom(30 * MB)
        net = FakeNet(blob, latency=(0.0, 0.001))
        written = {"parts": 0}
        max_gap = {"v": 0}
        orig_call = net.call

        async def tracking_call(sender, request):
            index = request.offset // MB
            max_gap["v"] = max(max_gap["v"], index - written["parts"])
            return await orig_call(sender, request)

        net.call = tracking_call
        orig_write = ft._SequentialWriter._write_all

        def slow_write(self, chunks):
            import time

            time.sleep(0.01)
            orig_write(self, chunks)
            written["parts"] += len(chunks)

        monkeypatch.setattr(ft._SequentialWriter, "_write_all", slow_write)
        pool = net.pool(max_connections=2, requests_per_connection=2)  # 4 workers
        assert await _download(net, len(blob), tmp_path, pool=pool) == blob
        # max_ahead = max(4, 2 * workers) = 8, plus parts already in flight.
        assert max_gap["v"] <= 8 + 4


class FtCancelError(Exception):  # stands in for TransferCancelledError
    pass


class TestPool:
    async def test_connections_are_reused_across_transfers(self, tmp_path):
        blob = os.urandom(4 * MB)
        net = FakeNet(blob)
        pool = net.pool(max_connections=4)
        await _download(net, len(blob), tmp_path, pool=pool)
        opened = net.sockets_opened
        await _download(net, len(blob), tmp_path, pool=pool)
        assert net.sockets_opened == opened  # second transfer opened nothing

    async def test_concurrent_transfers_share_one_budget(self, tmp_path):
        blob = os.urandom(8 * MB)
        net = FakeNet(blob, latency=(0.002, 0.006))
        pool = net.pool(max_connections=4, requests_per_connection=2)
        outs = [tmp_path / f"o{i}.bin" for i in range(3)]
        await asyncio.gather(
            *(ft.download_file(None, FakeLocation(len(blob)), o, pool=pool) for o in outs)
        )
        assert all(o.read_bytes() == blob for o in outs)
        assert net.max_open_sockets <= 4
        assert net.max_in_flight <= 8

    async def test_idle_connections_are_closed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ft, "_REAPER_INTERVAL", 0.01)
        net = FakeNet(os.urandom(2 * MB))
        pool = net.pool(idle_timeout=0.02)
        await _download(net, 2 * MB, tmp_path, pool=pool)
        await asyncio.sleep(0.15)
        assert pool.connection_count == 0 and net.open_sockets == 0

    async def test_closed_pool_is_not_retried(self):
        net = FakeNet()
        pool = net.pool()
        await pool.close()
        with pytest.raises(ft.PoolClosedError):
            await pool.request(lambda: None)


class _BytesSource:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.size = len(data)

    def read(self, offset, length):
        return self.data[offset : offset + length]

    def md5(self):
        return hashlib.md5(self.data).hexdigest()

    def close(self):
        pass


class TestUpload:
    async def test_big_file_parts_all_sent_once(self):
        data = os.urandom(12 * MB + 99)
        net = FakeNet(latency=(0.0, 0.003))
        result = await ft.upload_source(None, _BytesSource(data), "a.bin", pool=net.pool())
        assert isinstance(result, InputFileBig)
        parts = [net.uploaded[i] for i in sorted(net.uploaded)]
        assert b"".join(parts) == data
        assert result.parts == len(parts)
        assert set(net.upload_meta) == {(SaveBigFilePartRequest, len(parts))}

    async def test_small_file_uses_md5(self):
        data = os.urandom(700_000)
        net = FakeNet()
        result = await ft.upload_source(None, _BytesSource(data), "a.bin", pool=net.pool())
        assert isinstance(result, InputFile)
        assert result.md5_checksum == hashlib.md5(data).hexdigest()
        assert b"".join(net.uploaded[i] for i in sorted(net.uploaded)) == data

    async def test_rejects_files_over_the_part_limit(self):
        src = _BytesSource(b"")
        src.size = 5 * 1024**3
        with pytest.raises(ValueError, match="too large"):
            await ft.upload_source(None, src, "a.bin", pool=FakeNet().pool())

    async def test_file_source_reads_any_offset(self, tmp_path):
        p = tmp_path / "f.bin"
        data = os.urandom(3 * MB)
        p.write_bytes(data)
        src = ft.FilePartSource(p)
        try:
            assert src.read(MB + 5, 100) == data[MB + 5 : MB + 105]
            assert src.md5() == hashlib.md5(data).hexdigest()
        finally:
            src.close()


class TestStreaming:
    @pytest.mark.parametrize(
        ("start", "end"),
        [(0, 0), (0, 5 * MB - 1), (123, 4567), (MB - 1, MB), (3 * MB + 10, 5 * MB - 1)],
    )
    async def test_iter_range_returns_exact_slice(self, start, end):
        blob = os.urandom(5 * MB)
        net = FakeNet(blob)
        chunks = [
            c
            async for c in ft.iter_range(
                None, FakeLocation(len(blob)), start, end, pool=net.pool()
            )
        ]
        assert b"".join(chunks) == blob[start : end + 1]

    async def test_readahead_is_bounded(self):
        blob = os.urandom(20 * MB)
        net = FakeNet(blob, latency=(0.003, 0.003))
        pool = net.pool(max_connections=8, requests_per_connection=2)
        async for _ in ft.iter_range(None, FakeLocation(len(blob)), 0, len(blob) - 1, readahead=3, pool=pool):
            pass
        assert net.max_in_flight <= 3


class TestVaultUploadSource:
    def test_matches_vault_format_and_supports_random_reads(self, data_dirs, tmp_path, monkeypatch):
        from telegrab.services import vault

        monkeypatch.setattr(vault, "_V2_CHUNK_SIZE", 64 * 1024)
        vault._session_keys[3] = bytearray(os.urandom(32))
        src_path = tmp_path / "plain.bin"
        plain = os.urandom(300_000)
        src_path.write_bytes(plain)

        source = vault.VaultUploadSource(src_path, 3)
        try:
            # Read in shuffled 512 KB-ish parts, like the uploader does.
            step = 50_000
            offsets = list(range(0, source.size, step))
            random.shuffle(offsets)
            pieces = {o: source.read(o, step) for o in offsets}
            cipher = b"".join(pieces[o] for o in sorted(pieces))
            assert len(cipher) == source.size
        finally:
            source.close()

        enc = tmp_path / "x.enc"
        enc.write_bytes(cipher)
        vault.decrypt_file(str(enc), 3, tmp_path / "out.bin")
        assert (tmp_path / "out.bin").read_bytes() == plain

    def test_empty_file(self, data_dirs, tmp_path):
        from telegrab.services import vault

        vault._session_keys[4] = bytearray(os.urandom(32))
        p = tmp_path / "empty"
        p.write_bytes(b"")
        source = vault.VaultUploadSource(p, 4)
        cipher = source.read(0, source.size)
        source.close()
        enc = tmp_path / "e.enc"
        enc.write_bytes(cipher)
        vault.decrypt_file(str(enc), 4, tmp_path / "o")
        assert Path(tmp_path / "o").read_bytes() == b""
