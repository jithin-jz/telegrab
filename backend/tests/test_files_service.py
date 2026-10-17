"""Behavioural tests for the file service (listing, transfers, moves).

A small in-memory fake stands in for the Telethon client, so these tests
exercise the real service code paths without any network.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegrab import telegram as tg
from telegrab.services import NotConnectedError, files, folders, localdb


class FakeClient:
    def __init__(self, messages=None):
        # Newest first, like Telegram.
        self.messages = sorted(messages or [], key=lambda m: -m.id)
        self.deleted: list[int] = []
        self.forward_result = None

    async def iter_messages(self, peer, limit=100, offset_id=0, search=None):
        count = 0
        for msg in self.messages:
            if offset_id and msg.id >= offset_id:
                continue
            if search and search.lower() not in (msg.name or "").lower():
                continue
            if count >= limit:
                return
            count += 1
            yield msg

    async def delete_messages(self, peer, ids):
        self.deleted.extend(ids)

    async def forward_messages(self, target, ids, src):
        return self.forward_result

    async def get_messages(self, peer, ids):
        return next((m for m in self.messages if m.id == ids), None)


def _msg(mid: int, name: str | None):
    """A fake message; `name=None` means a text/service message (no file)."""
    return SimpleNamespace(id=mid, name=name, media=object() if name else None)


@pytest.fixture
def fake_tg(monkeypatch, data_dirs):
    """Install a fake client and simplify media helpers."""
    state = tg.get_state()

    def install(client):
        monkeypatch.setattr(state, "client", client)
        return client

    async def fake_resolve(client, folder_id):
        return f"peer-{folder_id}"

    monkeypatch.setattr(tg, "resolve_peer", fake_resolve)
    monkeypatch.setattr(
        tg,
        "file_metadata_from_message",
        lambda m, fid: (
            {"id": m.id, "folder_id": fid, "name": m.name, "created_at": str(m.id)}
            if m.name
            else None
        ),
    )
    monkeypatch.setattr(state, "folder_ids", set())
    yield install
    monkeypatch.setattr(state, "client", None)


# ───────────────────────────── not connected ─────────────────────────────


class TestNotConnected:
    """Commands must fail loudly instead of faking success while offline."""

    @pytest.fixture(autouse=True)
    def _no_client(self, monkeypatch, data_dirs):
        monkeypatch.setattr(tg.get_state(), "client", None)

    async def test_download_does_not_touch_target(self, tmp_path):
        target = tmp_path / "important.docx"
        target.write_text("REAL USER DATA")
        with pytest.raises(NotConnectedError):
            await files.cmd_download_file(1, str(target), None, "t1")
        assert target.read_text() == "REAL USER DATA"

    async def test_upload_raises(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x")
        with pytest.raises(NotConnectedError):
            await files.cmd_upload_file(str(src), None, "t1")

    @pytest.mark.parametrize(
        "call",
        [
            lambda: files.cmd_get_files(None),
            lambda: files.cmd_delete_file(1, None),
            lambda: files.cmd_move_files([1], None, 5),
            lambda: folders.cmd_create_folder("Docs"),
            lambda: folders.cmd_rename_folder(5, "Docs"),
            lambda: folders.cmd_delete_folder(5),
            lambda: folders.cmd_scan_folders(),
        ],
    )
    async def test_other_commands_raise(self, call):
        with pytest.raises(NotConnectedError):
            await call()


# ─────────────────────────────── pagination ───────────────────────────────


class TestPagination:
    async def test_cursor_is_last_scanned_message_not_last_file(self, fake_tg):
        # Page of 4 messages where two are text messages (no file).
        fake_tg(FakeClient([_msg(i, None if i % 2 else f"f{i}") for i in range(1, 11)]))
        page = await files.cmd_get_files(None, limit=4)
        assert [f["id"] for f in page["files"]] == [10, 8]
        # Cursor must be the 4th scanned message (7), not the last file (8).
        assert page["next_offset_id"] == 7

    async def test_walks_every_file_exactly_once(self, fake_tg):
        fake_tg(FakeClient([_msg(i, None if i % 3 == 0 else f"f{i}") for i in range(1, 251)]))
        seen: list[int] = []
        cursor = 0
        while True:
            page = await files.cmd_get_files(None, limit=100, offset_id=cursor)
            seen.extend(f["id"] for f in page["files"])
            cursor = page["next_offset_id"]
            if not cursor:
                break
        expected = [i for i in range(250, 0, -1) if i % 3 != 0]
        assert seen == expected

    async def test_last_page_has_no_cursor(self, fake_tg):
        fake_tg(FakeClient([_msg(i, f"f{i}") for i in range(1, 6)]))
        page = await files.cmd_get_files(None, limit=100)
        assert page["next_offset_id"] == 0


# ─────────────────────────────── search ───────────────────────────────


class TestSearch:
    async def test_searches_only_telegrab_folders(self, fake_tg, monkeypatch):
        fake_tg(FakeClient([_msg(1, "report.pdf"), _msg(2, "notes.txt")]))
        searched: list = []

        async def fake_resolve(client, folder_id):
            searched.append(folder_id)
            return f"peer-{folder_id}"

        monkeypatch.setattr(tg, "resolve_peer", fake_resolve)
        results = await files.cmd_search_global("report", folder_ids=[7, 9])
        assert sorted(searched, key=str) == sorted([None, 7, 9], key=str)
        assert {r["name"] for r in results} == {"report.pdf"}


# ─────────────────────────────── downloads ───────────────────────────────


def _fake_fast_download(monkeypatch, *, payload=b"hello", fail: Exception | None = None):
    from telegrab.telegram import fast_transfer

    async def fake_download(client, location, out, progress_callback=None):
        Path(out).write_bytes(payload[:2])  # partial data first
        if progress_callback:
            progress_callback(2, len(payload))
        if fail:
            raise fail
        Path(out).write_bytes(payload)
        return out

    monkeypatch.setattr(fast_transfer, "download_file", fake_download)


@pytest.fixture
def doc_message(monkeypatch):
    from telethon.tl import types

    msg = SimpleNamespace(
        id=1,
        name="x",
        media=types.MessageMediaDocument(document=SimpleNamespace(size=5)),
    )
    monkeypatch.setattr(tg, "media_total_size", lambda m: 5)
    return msg


class TestDownload:
    async def test_success_writes_target_and_no_partial(self, fake_tg, doc_message, tmp_path, monkeypatch):
        fake_tg(FakeClient([doc_message]))
        _fake_fast_download(monkeypatch)
        target = tmp_path / "out.bin"
        result = await files.cmd_download_file(1, str(target), None, "t1")
        assert result == str(target)
        assert target.read_bytes() == b"hello"
        assert not (tmp_path / "out.bin.part").exists()

    async def test_failure_leaves_no_partial_and_keeps_existing_file(
        self, fake_tg, doc_message, tmp_path, monkeypatch
    ):
        fake_tg(FakeClient([doc_message]))
        _fake_fast_download(monkeypatch, fail=ValueError("boom"))
        target = tmp_path / "out.bin"
        target.write_bytes(b"old")
        with pytest.raises(RuntimeError, match="Download failed"):
            await files.cmd_download_file(1, str(target), None, "t1")
        assert target.read_bytes() == b"old"
        assert list(tmp_path.glob("*.part")) == []

    async def test_cancel_cleans_up_and_clears_flag(self, fake_tg, doc_message, tmp_path, monkeypatch):
        fake_tg(FakeClient([doc_message]))
        _fake_fast_download(monkeypatch)
        tg.cancel_transfer("t-cancel")
        target = tmp_path / "out.bin"
        with pytest.raises(RuntimeError, match="Transfer cancelled"):
            await files.cmd_download_file(1, str(target), None, "t-cancel")
        assert not target.exists()
        assert list(tmp_path.glob("*.part")) == []
        assert not tg.is_cancelled("t-cancel")

    async def test_dir_download_never_overwrites(self, fake_tg, doc_message, tmp_path, monkeypatch):
        fake_tg(FakeClient([doc_message]))
        _fake_fast_download(monkeypatch)
        (tmp_path / "report.pdf").write_bytes(b"mine")
        result = await files.cmd_download_file(
            1, None, None, "t1", dir_path=str(tmp_path), file_name="report.pdf"
        )
        assert Path(result).name == "report (1).pdf"
        assert (tmp_path / "report.pdf").read_bytes() == b"mine"

    async def test_rejects_relative_and_traversal_paths(self, fake_tg, doc_message, tmp_path):
        fake_tg(FakeClient([doc_message]))
        with pytest.raises(RuntimeError, match="absolute"):
            await files.cmd_download_file(1, "relative.bin", None)
        with pytest.raises(RuntimeError, match="traversal"):
            await files.cmd_download_file(1, str(tmp_path / ".." / "x.bin"), None)


class TestSafeFilename:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("report.pdf", "report.pdf"),
            ('a<b>:c"d|e?f*.txt', "a_b__c_d_e_f_.txt"),
            ("CON.txt", "_CON.txt"),
            ("nul", "_nul"),
            ("trailing. ", "trailing"),
            ("../../etc/passwd", "____etc_passwd"),
            ("", "download"),
            ("line\nbreak.txt", "line_break.txt"),
        ],
    )
    def test_sanitises(self, raw, expected):
        assert files.safe_filename(raw) == expected

    def test_truncates_long_names_keeping_extension(self):
        name = files.safe_filename("a" * 500 + ".mp4")
        assert len(name) <= 200
        assert name.endswith(".mp4")


# ─────────────────────────────── uploads ───────────────────────────────


class TestUpload:
    async def test_vault_upload_keeps_original_name_and_cleans_ciphertext(
        self, fake_tg, tmp_path, monkeypatch
    ):
        from telegrab.services import vault as vault_mod
        from telegrab.telegram import fast_transfer

        client = fake_tg(FakeClient())
        sent: dict = {}

        async def send_file(peer, file, caption, file_name, force_document):
            sent["name"] = file_name
            return SimpleNamespace(id=42)

        client.send_file = send_file
        staged: list[str] = []

        async def fake_upload(client, f, filename=None, progress_callback=None):
            staged.append(f.name)
            sent["upload_name"] = filename
            return object()

        monkeypatch.setattr(fast_transfer, "upload_file", fake_upload)

        async def always_vault(folder_id):
            return True

        monkeypatch.setattr(vault_mod, "ensure_vault_known", always_vault)
        vault_mod._session_keys[5] = bytearray(os.urandom(32))

        src = tmp_path / "Holiday Photo.jpg"
        src.write_bytes(b"secret" * 100)
        await files.cmd_upload_file(str(src), 5, "t1")

        assert sent == {"name": "Holiday Photo.jpg", "upload_name": "Holiday Photo.jpg"}
        assert staged and not Path(staged[0]).exists()  # ciphertext removed
        assert Path(staged[0]).parent == vault_mod.vault_temp_dir()

    async def test_locked_vault_upload_refused(self, fake_tg, tmp_path, monkeypatch):
        from telegrab.services import vault as vault_mod

        fake_tg(FakeClient())

        async def always_vault(folder_id):
            return True

        monkeypatch.setattr(vault_mod, "ensure_vault_known", always_vault)
        src = tmp_path / "a.txt"
        src.write_text("x")
        with pytest.raises(RuntimeError, match="Vault is locked"):
            await files.cmd_upload_file(str(src), 5, "t1")

    async def test_failure_after_progress_emits_transfer_failed(
        self, fake_tg, tmp_path, monkeypatch
    ):
        from telegrab.services import files as files_mod
        from telegrab.telegram import fast_transfer

        fake_tg(FakeClient())
        events: list = []
        monkeypatch.setattr(files_mod.bus, "emit", lambda e, p: events.append((e, p)))
        monkeypatch.setattr(files_mod, "_emit_progress", lambda e, p: None)

        async def fake_upload(client, f, filename=None, progress_callback=None):
            progress_callback(10, 20)  # after the throttle window
            raise ValueError("server said no")

        monkeypatch.setattr(fast_transfer, "upload_file", fake_upload)
        monkeypatch.setattr(files_mod, "_PROGRESS_INTERVAL_SECS", 0.0)
        src = tmp_path / "a.txt"
        src.write_bytes(b"x" * 20)
        with pytest.raises(RuntimeError, match="server said no"):
            await files.cmd_upload_file(str(src), None, "t1")
        failed = [p for e, p in events if e == "transfer-failed"]
        assert failed and failed[0]["transferId"] == "t1"
        assert failed[0]["bytesSent"] == 10


# ───────────────────────────────── moves ─────────────────────────────────


class TestMove:
    async def test_refuses_vault_boundary(self, fake_tg, monkeypatch):
        from telegrab.services import vault as vault_mod

        client = fake_tg(FakeClient())

        async def is_vault(folder_id):
            return folder_id == 9

        monkeypatch.setattr(vault_mod, "ensure_vault_known", is_vault)
        with pytest.raises(RuntimeError, match="vault"):
            await files.cmd_move_files([1], None, 9)
        assert client.deleted == []

    async def test_keeps_originals_if_forward_incomplete(self, fake_tg, monkeypatch):
        client = fake_tg(FakeClient())
        client.forward_result = [SimpleNamespace(id=100), None]
        with pytest.raises(RuntimeError, match="originals were kept"):
            await files.cmd_move_files([1, 2], None, 5)
        assert client.deleted == []

    async def test_repoints_fingerprints(self, fake_tg):
        from telegrab.services import dedup

        client = fake_tg(FakeClient())
        client.forward_result = [SimpleNamespace(id=100)]
        dedup.store_hash("h1", None, 1, "a.txt", 3)
        await files.cmd_move_files([1], None, 5)
        assert client.deleted == [1]
        assert dedup.find_duplicate("h1", 5)["message_id"] == 100
        assert dedup.find_duplicate("h1", None) is None


class TestDelete:
    async def test_delete_forgets_pin_and_hash(self, fake_tg):
        from telegrab.services import dedup, pins

        fake_tg(FakeClient())
        dedup.store_hash("h1", 5, 7, "a.txt", 3)
        await pins.cmd_pin_file(7, 5, "a.txt", 3)
        await files.cmd_delete_file(7, 5)
        assert dedup.find_duplicate("h1", 5) is None
        assert await pins.cmd_get_pinned_files() == []


def test_localdb_wipe(data_dirs):
    localdb.execute(
        "INSERT INTO pinned_files VALUES (?, ?, ?, ?, ?)", (1, -1, "a", 1, 0.0)
    )
    localdb.wipe_account_data()
    assert localdb.query("SELECT * FROM pinned_files") == []


def test_event_loop_unblocked_marker():
    # Sanity check: the service module must not create loop-bound objects
    # at import time (they break after a runtime restart).
    assert not any(isinstance(v, asyncio.Semaphore) for v in vars(files).values())
