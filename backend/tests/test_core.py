"""Unit tests for Telegrab backend core logic.

Run with: python -m pytest tests/ -v
"""

import os
import threading
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────── Bandwidth Manager Tests ───────────────────────


class TestBandwidthManager:
    """Tests for telegrab.infra.bandwidth.BandwidthManager."""

    def _make_manager(self, tmp_path):
        """Create a BandwidthManager with a temp file."""
        from telegrab.infra.bandwidth import BandwidthManager

        with patch("telegrab.infra.bandwidth.bandwidth_path", return_value=tmp_path / "bw.json"):
            return BandwidthManager()

    def test_initial_state(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        stats = mgr.get_stats()
        assert stats["up_bytes"] == 0
        assert stats["down_bytes"] == 0
        assert stats["date"] == date.today().isoformat()

    def test_add_up_down(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.add_up(1000)
        mgr.add_down(2000)
        stats = mgr.get_stats()
        assert stats["up_bytes"] == 1000
        assert stats["down_bytes"] == 2000

    def test_can_transfer_within_limit(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        ok, err = mgr.can_transfer(1024)
        assert ok is True
        assert err is None

    def test_can_transfer_exceeds_limit(self, tmp_path):
        from telegrab.infra.bandwidth import DAILY_LIMIT_BYTES

        mgr = self._make_manager(tmp_path)
        ok, err = mgr.can_transfer(DAILY_LIMIT_BYTES + 1)
        assert ok is False
        assert "exceeded" in err.lower()

    def test_daily_reset(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        mgr.add_up(5000)
        # Simulate yesterday's date
        mgr._stats.date = "2020-01-01"
        stats = mgr.get_stats()
        # Should have reset
        assert stats["up_bytes"] == 0
        assert stats["date"] == date.today().isoformat()

    def test_thread_safety(self, tmp_path):
        mgr = self._make_manager(tmp_path)
        errors = []

        def add_bytes():
            try:
                for _ in range(100):
                    mgr.add_up(1)
                    mgr.add_down(1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_bytes) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = mgr.get_stats()
        assert stats["up_bytes"] == 400
        assert stats["down_bytes"] == 400


# ─────────────────────── Vault Encrypt/Decrypt Tests ───────────────────────


class TestVault:
    """Tests for telegrab.services.vault encrypt/decrypt round-trip."""

    def test_encrypt_decrypt_bytes_roundtrip(self):
        from telegrab.services.vault import _decrypt_bytes, _derive_key, _encrypt_bytes

        password = "test-password-123"
        salt = os.urandom(32)
        key = _derive_key(password, salt)

        plaintext = b"Hello, Telegrab vault!"
        encrypted = _encrypt_bytes(plaintext, key)
        decrypted = _decrypt_bytes(encrypted, key)

        assert decrypted == plaintext

    def test_encrypt_decrypt_file_roundtrip(self, tmp_path):
        from telegrab.services.vault import (
            _derive_key,
            _session_keys,
            decrypt_file,
            encrypt_file,
        )

        # Setup: create a test file
        test_file = tmp_path / "test.txt"
        test_content = b"This is secret vault content " * 100
        test_file.write_bytes(test_content)

        # Derive key and store in session
        password = "vault-pass"
        salt = os.urandom(32)
        key = _derive_key(password, salt)
        folder_id = 99999
        _session_keys[folder_id] = key

        try:
            # Encrypt
            enc_path = encrypt_file(str(test_file), folder_id)
            assert Path(enc_path).exists()
            assert Path(enc_path).read_bytes() != test_content

            # Decrypt
            dec_path = decrypt_file(enc_path, folder_id)
            assert Path(dec_path).exists()
            assert Path(dec_path).read_bytes() == test_content
        finally:
            _session_keys.pop(folder_id, None)
            for p in [enc_path, dec_path]:
                Path(p).unlink(missing_ok=True)

    def test_wrong_password_fails(self):
        from telegrab.services.vault import _decrypt_bytes, _derive_key, _encrypt_bytes

        salt = os.urandom(32)
        key1 = _derive_key("correct-password", salt)
        key2 = _derive_key("wrong-password", salt)

        encrypted = _encrypt_bytes(b"secret", key1)
        with pytest.raises(Exception):
            _decrypt_bytes(encrypted, key2)

    def test_locked_vault_raises(self):
        from telegrab.services.vault import _session_keys, encrypt_file

        # Ensure no key for this folder
        _session_keys.pop(12345, None)
        with pytest.raises(RuntimeError, match="locked"):
            encrypt_file("dummy.txt", 12345)


# ─────────────────────── Transfer Cancellation Tests ───────────────────────


class TestTransferCancellation:
    """Tests for telegrab.telegram.transfers cancellation registry."""

    def test_cancel_and_check(self):
        from telegrab.telegram.client import TelegramState
        from telegrab.telegram.transfers import (
            cancel_transfer,
            clear_cancellation,
            is_cancelled,
        )

        state = TelegramState()
        tid = "test-transfer-001"

        assert is_cancelled(state, tid) is False
        cancel_transfer(state, tid)
        assert is_cancelled(state, tid) is True
        clear_cancellation(state, tid)
        assert is_cancelled(state, tid) is False

    def test_empty_transfer_id(self):
        from telegrab.telegram.client import TelegramState
        from telegrab.telegram.transfers import cancel_transfer, is_cancelled

        state = TelegramState()
        cancel_transfer(state, "")
        assert is_cancelled(state, "") is False

    def test_multiple_cancellations(self):
        from telegrab.telegram.client import TelegramState
        from telegrab.telegram.transfers import cancel_transfer, is_cancelled

        state = TelegramState()
        for i in range(10):
            cancel_transfer(state, f"t-{i}")
        for i in range(10):
            assert is_cancelled(state, f"t-{i}") is True
        assert is_cancelled(state, "t-999") is False


# ─────────────────────── Auth Flow Tests ───────────────────────


class TestAuthFlow:
    """Tests for telegrab.services.auth command validation."""

    @pytest.mark.asyncio
    async def test_connect_stores_api_id(self):
        from telegrab.services.auth import cmd_connect
        from telegrab.telegram.client import get_state

        state = get_state()
        old_id = state.api_id
        old_hash = state.api_hash

        try:
            # cmd_connect with no api_hash should just store the id
            result = await cmd_connect(12345, None)
            assert result is True
            assert state.api_id == 12345
        finally:
            state.api_id = old_id
            state.api_hash = old_hash

    @pytest.mark.asyncio
    async def test_request_code_empty_hash_raises(self):
        from telegrab.services.auth import cmd_auth_request_code

        with pytest.raises(ValueError, match="empty"):
            await cmd_auth_request_code("+1234567890", 12345, "   ")

    @pytest.mark.asyncio
    async def test_sign_in_no_client_raises(self):
        from telegrab.services.auth import cmd_auth_sign_in
        from telegrab.telegram.client import get_state

        state = get_state()
        old_client = state.client
        state.client = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                await cmd_auth_sign_in("12345")
        finally:
            state.client = old_client

    @pytest.mark.asyncio
    async def test_check_password_no_client_raises(self):
        from telegrab.services.auth import cmd_auth_check_password
        from telegrab.telegram.client import get_state

        state = get_state()
        old_client = state.client
        state.client = None
        try:
            with pytest.raises(RuntimeError, match="not initialized"):
                await cmd_auth_check_password("password")
        finally:
            state.client = old_client


# ─────────────────────── Updater Disk Space Tests ───────────────────────


class TestUpdaterDiskSpace:
    """Tests for the disk space check in the updater."""

    def test_disk_space_check_raises_on_low_space(self):
        from telegrab.services.updater import cmd_download_and_install_update

        # Mock shutil.disk_usage to return very low free space
        fake_usage = MagicMock()
        fake_usage.free = 50 * 1024 * 1024  # 50MB (below 200MB threshold)

        with patch("shutil.disk_usage", return_value=fake_usage):
            with pytest.raises(RuntimeError, match="Insufficient disk space"):
                cmd_download_and_install_update(
                    "https://github.com/test/repo/releases/download/v1.0/update.exe",
                    expected_sha256="abc123",
                )


# ─────────────────────── Dedup Hash Tests ───────────────────────


class TestDedup:
    """Tests for file hash computation."""

    def test_compute_file_hash_deterministic(self, tmp_path):
        from telegrab.services.dedup import compute_file_hash

        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world" * 1000)

        h1 = compute_file_hash(str(f))
        h2 = compute_file_hash(str(f))
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_content_different_hash(self, tmp_path):
        from telegrab.services.dedup import compute_file_hash

        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"content A")
        f2.write_bytes(b"content B")

        assert compute_file_hash(str(f1)) != compute_file_hash(str(f2))

    def test_same_content_different_size_different_hash(self, tmp_path):
        from telegrab.services.dedup import compute_file_hash

        # Same first 1MB but different total size → different hash
        f1 = tmp_path / "small.bin"
        f2 = tmp_path / "large.bin"
        content = b"x" * 100
        f1.write_bytes(content)
        f2.write_bytes(content + b"extra")

        assert compute_file_hash(str(f1)) != compute_file_hash(str(f2))


# ─────────────────────── Folder Validation Tests ───────────────────────


class TestFolderValidation:
    """Tests for folder name input validation."""

    @pytest.mark.asyncio
    async def test_empty_name_raises(self):
        from telegrab.services.folders import cmd_create_folder

        with pytest.raises(RuntimeError, match="empty"):
            await cmd_create_folder("")

    @pytest.mark.asyncio
    async def test_whitespace_only_raises(self):
        from telegrab.services.folders import cmd_create_folder

        with pytest.raises(RuntimeError, match="empty"):
            await cmd_create_folder("   ")

    @pytest.mark.asyncio
    async def test_too_long_raises(self):
        from telegrab.services.folders import cmd_create_folder

        with pytest.raises(RuntimeError, match="too long"):
            await cmd_create_folder("x" * 200)

    @pytest.mark.asyncio
    async def test_control_chars_raises(self):
        from telegrab.services.folders import cmd_create_folder

        with pytest.raises(RuntimeError, match="invalid characters"):
            await cmd_create_folder("folder\x00name")

    @pytest.mark.asyncio
    async def test_path_separator_raises(self):
        from telegrab.services.folders import cmd_create_folder

        with pytest.raises(RuntimeError, match="invalid characters"):
            await cmd_create_folder("folder/name")
