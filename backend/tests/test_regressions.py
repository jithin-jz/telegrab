"""Regression tests for bugs found in the production-readiness audit."""

from __future__ import annotations

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


class TestTransferEngineWiring:
    """Pool lifecycle hooks (engine behaviour itself: test_fast_transfer.py)."""

    async def test_pools_are_closed_with_the_client(self, monkeypatch):
        from telegrab.telegram import client as client_mod
        from telegrab.telegram import fast_transfer

        closed = []

        async def fake_close(client):
            closed.append(client)

        class Client:
            async def disconnect(self):
                return None

        monkeypatch.setattr(fast_transfer, "close_pools", fake_close)
        state = client_mod.TelegramState()
        state.client = Client()
        c = state.client
        await client_mod._shutdown_client(state)
        assert closed == [c] and state.client is None


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
    async def test_cache_key_includes_folder_and_quality(self, data_dirs):
        from telegrab.config import thumbnail_cache_dir
        from telegrab.services import preview

        d = thumbnail_cache_dir()
        (d / "11_5_medium.jpg").write_bytes(b"\xff\xd8folder-11")
        (d / "22_5_medium.jpg").write_bytes(b"\xff\xd8folder-22")
        (d / "22_5_low.jpg").write_bytes(b"\xff\xd8folder-22-low")
        a = await preview.get_thumbnail_bytes(5, 11, "medium")
        b = await preview.get_thumbnail_bytes(5, 22, "medium")
        c = await preview.get_thumbnail_bytes(5, 22, "low")
        assert len({a, b, c}) == 3

    def test_old_unscoped_thumbnails_are_removed(self, data_dirs, monkeypatch):
        from telegrab.config import thumbnail_cache_dir
        from telegrab.services import preview

        monkeypatch.setattr(preview, "_legacy_thumbs_removed", False)
        d = thumbnail_cache_dir()
        (d / "5.jpg").write_bytes(b"old")
        (d / "home_5.jpg").write_bytes(b"older format")
        (d / "home_5_medium.jpg").write_bytes(b"new")
        preview._last_prune.clear()
        preview._prune_thumbnails(d)
        assert not (d / "5.jpg").exists()
        assert not (d / "home_5.jpg").exists()
        assert (d / "home_5_medium.jpg").exists()


class TestThumbnailChoice:
    def _sizes(self):
        from telethon.tl.types import (
            PhotoPathSize,
            PhotoSize,
            PhotoStrippedSize,
            VideoSize,
        )

        return [
            PhotoStrippedSize(type="i", bytes=b"x" * 20),
            PhotoSize(type="s", w=90, h=60, size=1_000),
            PhotoSize(type="m", w=320, h=213, size=9_000),
            PhotoSize(type="x", w=800, h=533, size=60_000),
            VideoSize(type="u", w=1280, h=720, size=900_000),
            PhotoPathSize(type="j", bytes=b"svg"),
        ]

    @pytest.mark.parametrize(("quality", "expected"), [("low", "m"), ("medium", "m"), ("high", "x")])
    def test_picks_jpeg_size_for_quality(self, quality, expected):
        from telegrab.services.preview import pick_thumbnail

        assert pick_thumbnail(self._sizes(), quality).type == expected

    def test_never_picks_video_or_vector_thumbs(self):
        from telethon.tl.types import PhotoPathSize, VideoSize

        from telegrab.services.preview import pick_thumbnail

        only_bad = [VideoSize(type="u", w=1, h=1, size=1), PhotoPathSize(type="j", bytes=b"")]
        assert pick_thumbnail(only_bad, "high") is None

    def test_stripped_preview_is_last_resort(self):
        from telethon.tl.types import PhotoStrippedSize

        from telegrab.services.preview import pick_thumbnail

        stripped = PhotoStrippedSize(type="i", bytes=b"x")
        assert pick_thumbnail([stripped], "medium") is stripped


class TestThumbEndpoint:
    async def test_serves_cached_jpeg_with_long_cache(self, data_dirs, monkeypatch):
        from telegrab.api import streaming
        from telegrab.services import preview

        async def fake_bytes(message_id, folder_id, quality):
            assert (message_id, folder_id, quality) == (5, 9, "low")
            return b"\xff\xd8jpeg"

        monkeypatch.setattr(preview, "get_thumbnail_bytes", fake_bytes)
        written: list[bytes] = []

        class Writer:
            def write(self, data):
                written.append(data)

            async def drain(self):
                return None

        await streaming._serve_thumbnail(Writer(), 5, 9, "low")
        response = b"".join(written)
        assert response.startswith(b"HTTP/1.1 200")
        assert b"Content-Type: image/jpeg" in response
        assert b"immutable" in response
        assert response.endswith(b"\xff\xd8jpeg")

    async def test_missing_thumbnail_is_404(self, monkeypatch):
        from telegrab.api import streaming
        from telegrab.services import preview

        async def none(*a):
            return None

        monkeypatch.setattr(preview, "get_thumbnail_bytes", none)
        written: list[bytes] = []

        class Writer:
            def write(self, data):
                written.append(data)

            async def drain(self):
                return None

        await streaming._serve_thumbnail(Writer(), 5, None)
        assert b"".join(written).startswith(b"HTTP/1.1 404")


class TestStoreFlush:
    def test_flush_writes_pending_changes(self, data_dirs):
        from telegrab.infra.store import JsonStore

        store = JsonStore()
        store.set("theme", "dark")
        store.flush()
        assert JsonStore().get("theme") == "dark"


class TestTray:
    def test_missing_display_does_not_break_startup(self, monkeypatch):
        """pystray raises display errors (not ImportError) on headless Linux."""
        import builtins

        from telegrab.services import tray

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pystray":
                raise RuntimeError("DisplayNameError: no display")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert tray._import_pystray() is None
        tray.start_tray(lambda: None, lambda: None)  # must not raise
        assert tray._icon is None
