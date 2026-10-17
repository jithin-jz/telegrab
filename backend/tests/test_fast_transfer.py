"""Unit tests for the parallel transfer engine (fast_transfer.py).

Covers the two correctness-critical, network-free parts of the engine:
- adaptive connection-count selection by file size
- the pipelined download loop: in-order yield, exact part count, and full
  byte-for-byte reassembly (guards the off-by-one / ordering risk in the
  round-robin pipeline).

Real MTProtoSenders are replaced with in-memory fakes so no client or
network is required.
"""

from __future__ import annotations

import asyncio

import pytest

from telegrab.telegram import fast_transfer as ft

ParallelTransferrer = ft.ParallelTransferrer


class _FakeSender:
    """Stands in for a DownloadSender: returns preassigned parts in order."""

    def __init__(self, parts: list[bytes]) -> None:
        self._parts = parts
        self._i = 0

    async def next(self) -> bytes | None:
        if self._i >= len(self._parts):
            return None
        data = self._parts[self._i]
        self._i += 1
        return data

    def disconnect(self):
        async def _noop():
            return None

        return _noop()


def _make_transferrer(senders):
    """Build a ParallelTransferrer without invoking __init__ (no client)."""
    t = ParallelTransferrer.__new__(ParallelTransferrer)
    t.loop = asyncio.get_event_loop()
    t.senders = senders
    # _init_download is patched out; download() reads t.senders directly.
    return t


class TestConnectionCount:
    @pytest.mark.parametrize(
        "size_mb,expected",
        [(200, 20), (50, 20), (5, 16), (0.5, 8)],
    )
    def test_adaptive_counts(self, size_mb, expected):
        size = int(size_mb * 1024 * 1024)
        assert ParallelTransferrer._get_connection_count(size) == expected


class TestPipelinedDownload:
    async def _run(self, parts_per_sender, file_size, part_size, monkeypatch):
        senders = [_FakeSender(p) for p in parts_per_sender]
        t = _make_transferrer(senders)

        async def _fake_init(connections, file, part_count, p_size):
            t.senders = senders

        monkeypatch.setattr(t, "_init_download", _fake_init)

        out = []
        async for chunk in t.download(
            file=object(),
            file_size=file_size,
            part_size_kb=part_size / 1024,
            connection_count=len(senders),
        ):
            out.append(chunk)
        return out

    async def test_round_robin_order_and_reassembly(self, monkeypatch):
        # 3 senders, file split into 7 parts across them in round-robin:
        # sender0 -> parts 0,3,6 ; sender1 -> 1,4 ; sender2 -> 2,5
        part_size = 4
        parts = [b"AAAA", b"BBBB", b"CCCC", b"DDDD", b"EEEE", b"FFFF", b"GG"]
        per_sender = [
            [parts[0], parts[3], parts[6]],
            [parts[1], parts[4]],
            [parts[2], parts[5]],
        ]
        file_size = sum(len(p) for p in parts)
        out = await self._run(per_sender, file_size, part_size, monkeypatch)
        # Bytes must reassemble in exact original order.
        assert b"".join(out) == b"".join(parts)

    async def test_stops_at_part_count_no_extra_yield(self, monkeypatch):
        # Senders could return more, but part_count must bound the output.
        part_size = 4
        per_sender = [[b"AAAA", b"BBBB"], [b"CCCC", b"DDDD"]]
        file_size = 4 * 3  # only 3 parts worth — 4th must not be yielded
        out = await self._run(per_sender, file_size, part_size, monkeypatch)
        assert len(out) == 3
        assert b"".join(out) == b"AAAACCCCBBBB"
