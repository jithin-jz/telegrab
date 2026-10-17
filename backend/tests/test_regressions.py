"""Regression tests for bugs found in the production-readiness audit."""

from __future__ import annotations

import asyncio
import os
import struct
from types import SimpleNamespace

import pytest

# ───────────────────────────── peer cache ─────────────────────────────


class TestPeerCache:
    async def test_cached_entities_from_folder_scan_resolve(self):
        """Folder scans used to store bare entities, crashing resolve_peer."""
        from telethon.tl.types import Channel, ChatPhotoEmpty

        from telegrab.telegram import peers
        from telegrab.telegram.client import TelegramState

        state = TelegramState()
        channel = Channel(
            id=123, title="Docs [TD]", photo=ChatPhotoEmpty(), date=None, access_hash=1
        )
        peers.remember_peer(state, channel)
        assert await peers.resolve_peer(state, None, 123) is channel

    async def test_uses_session_cache_before_scanning_dialogs(self):
        from telegrab.telegram import peers
        from telegrab.telegram.client import TelegramState

        entity = SimpleNamespace(id=55)

        class Client:
            async def get_entity(self, peer):
                return entity

            def iter_dialogs(self):  # pragma: no cover - must not be called
                raise AssertionError("dialog scan should not be needed")

        state = TelegramState()
        assert await peers.resolve_peer(state, Client(), 55) is entity
        assert state.peer_cache[55][0] is entity

    async def test_falls_back_to_dialog_scan(self):
        from telegrab.telegram import peers
        from telegrab.telegram.client import TelegramState

        entity = SimpleNamespace(id=77)

        class Client:
            async def get_entity(self, peer):
                raise ValueError("not cached")

            async def iter_dialogs(self):
                yield SimpleNamespace(entity=SimpleNamespace(id=1))
                yield SimpleNamespace(entity=entity)

        assert await peers.resolve_peer(TelegramState(), Client(), 77) is entity


# ───────────────────────────── vault ─────────────────────────────


class TestVaultMetadata:
    def test_tag_roundtrip_and_fits_channel_description(self):
        from telegrab.services import vault

        salt = os.urandom(32)
        key = vault._derive_key("password123", salt)
        check = vault._encrypt_bytes(vault._KEY_CHECK_PLAINTEXT, key)
        about = f"Telegram Drive Storage Folder\n[telegram-drive-folder]\n{vault.format_vault_tag(salt, check)}"
        assert len(about) <= vault._ABOUT_MAX
        assert vault.parse_vault_tag(about) == (salt, check)
        assert vault.strip_vault_tag(about) == (
            "Telegram Drive Storage Folder\n[telegram-drive-folder]"
        )

    def test_parse_ignores_garbage(self):
        from telegrab.services import vault

        assert vault.parse_vault_tag("hello") is None
        assert vault.parse_vault_tag(None) is None

    async def test_vault_restored_from_telegram_after_reinstall(self, data_dirs, monkeypatch):
        """With an empty local DB, the vault must come back from Telegram."""
        from telegrab import telegram as tg
        from telegrab.services import vault

        salt = os.urandom(32)
        key = vault._derive_key("correct horse", salt)
        about = vault.format_vault_tag(salt, vault._encrypt_bytes(vault._KEY_CHECK_PLAINTEXT, key))

        async def fake_read_about(client, folder_id):
            return about, SimpleNamespace(title="Secret [TD]")

        monkeypatch.setattr(vault, "_read_about", fake_read_about)
        monkeypatch.setattr(tg.get_state(), "client", object())

        status = await vault.cmd_get_vault_status(9)
        assert status == {"is_vault": True, "locked": True}
        with pytest.raises(Exception, match="Incorrect password"):
            await vault.cmd_unlock_vault(9, "wrong password")
        assert await vault.cmd_unlock_vault(9, "correct horse") is True
        assert vault.is_unlocked(9)
        monkeypatch.setattr(tg.get_state(), "client", None)


class TestVaultFileFormat:
    @pytest.fixture
    def key_for(self, data_dirs):
        from telegrab.services import vault

        vault._session_keys[1] = bytearray(os.urandom(32))
        return vault

    @pytest.mark.parametrize("size", [0, 1, 1000, 3 * 1024 * 1024 + 7])
    def test_roundtrip(self, key_for, tmp_path, monkeypatch, size):
        vault = key_for
        monkeypatch.setattr(vault, "_V2_CHUNK_SIZE", 1024 * 1024)
        src = tmp_path / "plain.bin"
        src.write_bytes(os.urandom(size))
        enc = vault.encrypt_file(str(src), 1, tmp_path)
        out = vault.decrypt_file(enc, 1, tmp_path / "out.bin")
        assert (tmp_path / "out.bin").read_bytes() == src.read_bytes()
        assert out == str(tmp_path / "out.bin")

    def test_truncation_detected(self, key_for, tmp_path, monkeypatch):
        """Dropping the last chunk (and fixing up the count) must not decrypt."""
        vault = key_for
        monkeypatch.setattr(vault, "_V2_CHUNK_SIZE", 1024)
        src = tmp_path / "plain.bin"
        src.write_bytes(os.urandom(4096))
        enc = tmp_path / "x.enc"
        enc.write_bytes(open(vault.encrypt_file(str(src), 1, tmp_path), "rb").read())  # noqa: SIM115, PTH123
        data = bytearray(enc.read_bytes())
        header_len = 8 + 12 + 4 + 8
        n = struct.unpack(">Q", data[header_len - 8 : header_len])[0]
        data[header_len - 8 : header_len] = struct.pack(">Q", n - 1)
        chunk_len = struct.unpack(">I", data[header_len : header_len + 4])[0]
        truncated = data[: len(data) - (4 + chunk_len)]
        enc.write_bytes(bytes(truncated))
        with pytest.raises(Exception, match="corrupted"):
            vault.decrypt_file(str(enc), 1, tmp_path / "out.bin")
        assert not (tmp_path / "out.bin").exists()

    def test_legacy_v1_chunked_files_still_decrypt(self, key_for, tmp_path):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        vault = key_for
        key = bytes(vault._session_keys[1])
        base = os.urandom(12)
        plain = os.urandom(5000)
        ct = AESGCM(key).encrypt(vault._chunk_nonce(base, 0), plain, None)
        legacy = vault._CHUNKED_MAGIC + base + struct.pack(">I", 1) + struct.pack(">I", len(ct)) + ct
        enc = tmp_path / "legacy.enc"
        enc.write_bytes(legacy)
        vault.decrypt_file(str(enc), 1, tmp_path / "out.bin")
        assert (tmp_path / "out.bin").read_bytes() == plain


# ───────────────────────────── transfer engine ─────────────────────────────


class _Sender:
    def __init__(self, parts, fail_at=None):
        self.parts = list(parts)
        self.fail_at = fail_at
        self.calls = 0
        self.disconnected = False

    async def next(self):
        self.calls += 1
        if self.fail_at is not None and self.calls == self.fail_at:
            raise ConnectionError("dropped")
        await asyncio.sleep(0)
        return self.parts.pop(0) if self.parts else None

    async def disconnect(self):
        self.disconnected = True


def _transferrer(senders):
    from telegrab.telegram.fast_transfer import ParallelTransferrer

    t = ParallelTransferrer.__new__(ParallelTransferrer)
    t.loop = asyncio.get_running_loop()
    t.senders = senders

    async def fake_init(connections, file, part_count, part_size):
        t.senders = senders

    t._init_download = fake_init
    return t


class TestTransferCleanup:
    async def test_download_error_disconnects_all_senders(self):
        senders = [_Sender([b"a" * 4] * 3, fail_at=2), _Sender([b"b" * 4] * 3)]
        t = _transferrer(senders)
        with pytest.raises(ConnectionError):
            async for _ in t.download(object(), 24, part_size_kb=4 / 1024, connection_count=2):
                pass
        assert all(s.disconnected for s in senders)

    async def test_consumer_stopping_early_disconnects(self):
        import contextlib

        senders = [_Sender([b"a" * 4] * 5), _Sender([b"b" * 4] * 5)]
        t = _transferrer(senders)
        async with contextlib.aclosing(
            t.download(object(), 40, part_size_kb=4 / 1024, connection_count=2)
        ) as gen:
            async for _ in gen:
                break
        assert all(s.disconnected for s in senders)

    async def test_partial_sender_creation_failure_closes_opened(self):
        from telegrab.telegram.fast_transfer import ParallelTransferrer

        t = ParallelTransferrer.__new__(ParallelTransferrer)
        t.senders = None
        opened = []

        async def factory(i):
            if i == 2:
                raise ConnectionError("dc down")
            s = _Sender([])
            opened.append(s)
            return s

        with pytest.raises(ConnectionError):
            await t._create_senders(4, factory)
        assert opened and all(s.disconnected for s in opened)

    async def test_upload_part_limit(self):
        from telegrab.telegram.fast_transfer import ParallelTransferrer

        t = ParallelTransferrer.__new__(ParallelTransferrer)
        with pytest.raises(ValueError, match="too large"):
            await t.init_upload(1, 5 * 1024**3)


# ───────────────────────────── streaming ─────────────────────────────


class TestStreaming:
    def test_content_disposition_is_header_safe(self):
        from telegrab.api.streaming import _content_disposition

        header = _content_disposition('evil"\r\nSet-Cookie: x=1.mp4')
        assert "\r" not in header and "\n" not in header
        assert header.count('"') == 2

    def test_falls_back_to_free_port_when_taken(self):
        from telegrab.api.streaming import _bind_socket

        first = _bind_socket(0)
        try:
            port = first.getsockname()[1]
            with pytest.raises(OSError):
                _bind_socket(port)
        finally:
            first.close()


# ───────────────────────────── updater ─────────────────────────────


class TestUpdaterChecksums:
    BODY = (
        "## SHA-256 Checksums\n```\n"
        f"{'1' * 64}  ./telegrab-linux/telegrab-linux.tar.gz\n"
        f"{'2' * 64}  ./telegrab-windows/telegrab-windows-setup.exe\n```\n"
    )

    def test_picks_hash_for_the_matching_asset(self):
        from telegrab.services.updater import checksum_from_release

        release = {"body": self.BODY}
        asset = {"name": "telegrab-windows-setup.exe"}
        assert checksum_from_release(release, asset) == "2" * 64

    def test_prefers_github_digest(self):
        from telegrab.services.updater import checksum_from_release

        asset = {"name": "telegrab-windows-setup.exe", "digest": "sha256:" + "a" * 64}
        assert checksum_from_release({"body": self.BODY}, asset) == "a" * 64

    def test_install_without_check_is_refused(self, monkeypatch):
        from telegrab.services import updater

        monkeypatch.setattr(updater, "_pending_update", None)
        with pytest.raises(RuntimeError, match="Check for updates first"):
            updater.cmd_download_and_install_update()

    @pytest.mark.parametrize(
        ("url", "ok"),
        [
            ("https://github.com/jithin-jz/telegrab/releases/download/v1/a.exe", True),
            ("https://github.com/evil/telegrab/releases/download/v1/a.exe", False),
            ("http://github.com/jithin-jz/telegrab/releases/download/v1/a.exe", False),
            ("https://raw.githubusercontent.com/jithin-jz/telegrab/main/a.exe", False),
        ],
    )
    def test_only_this_repos_release_assets(self, url, ok):
        from telegrab.services.updater import _is_release_asset_url

        assert _is_release_asset_url(url) is ok

    def test_signature_verification(self, monkeypatch):
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        from telegrab.services import updater

        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        monkeypatch.setattr(updater, "UPDATE_PUBLIC_KEY", base64.b64encode(public).decode())
        message = b"abc  telegrab-windows-setup.exe\n"
        good = base64.b64encode(private.sign(message)).decode()
        updater._verify_signature(message, good)
        with pytest.raises(RuntimeError, match="signature"):
            updater._verify_signature(message + b"x", good)


# ───────────────────────────── previews ─────────────────────────────


class TestThumbnailCache:
    async def test_cache_key_includes_folder(self, data_dirs, monkeypatch):
        from telegrab.config import thumbnail_cache_dir
        from telegrab.services import preview

        d = thumbnail_cache_dir()
        (d / "11_5.jpg").write_bytes(b"\xff\xd8folder-11")
        (d / "22_5.jpg").write_bytes(b"\xff\xd8folder-22")
        a = await preview.cmd_get_thumbnail(5, 11)
        b = await preview.cmd_get_thumbnail(5, 22)
        assert a != b

    def test_old_unscoped_thumbnails_are_removed(self, data_dirs):
        from telegrab.config import thumbnail_cache_dir
        from telegrab.services import preview

        d = thumbnail_cache_dir()
        (d / "5.jpg").write_bytes(b"old")
        (d / "home_5.jpg").write_bytes(b"new")
        preview._last_prune.clear()
        preview._prune_thumbnails(d)
        assert not (d / "5.jpg").exists()
        assert (d / "home_5.jpg").exists()


class TestStoreFlush:
    def test_flush_writes_pending_changes(self, data_dirs):
        from telegrab.infra.store import JsonStore

        store = JsonStore()
        store.set("theme", "dark")
        store.flush()
        assert JsonStore().get("theme") == "dark"
