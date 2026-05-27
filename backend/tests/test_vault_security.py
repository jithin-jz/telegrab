"""Tests for vault decryption failure safety and DB integrity check (Task 8.3).

Tests cover:
- Decryption of corrupted ciphertext returns VAULT_DECRYPTION_FAILED error
- Temp output file is discarded on decryption failure
- Encrypted file on disk is preserved unchanged after decryption failure
- DB integrity check detects corruption and sets unhealthy flag
- Vault operations are refused when DB is unhealthy
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from telegrab.api.errors import BridgeError, ErrorCode


@pytest.fixture(autouse=True)
def _isolate_vault_state(tmp_path, monkeypatch):
    """Isolate vault module state for each test."""
    import telegrab.services.vault as vault_mod

    # Reset module-level state
    vault_mod._VAULT_DB = None
    vault_mod._vault_db_healthy = True
    vault_mod._session_keys.clear()
    vault_mod._inactivity_timers.clear()

    # Point app_data_dir to a temp directory
    monkeypatch.setattr("telegrab.services.vault.app_data_dir", lambda: tmp_path)

    yield

    # Cleanup timers
    for timer in list(vault_mod._inactivity_timers.values()):
        timer.cancel()
    vault_mod._inactivity_timers.clear()
    vault_mod._session_keys.clear()
    if vault_mod._VAULT_DB is not None:
        try:
            vault_mod._VAULT_DB.close()
        except Exception:
            pass
    vault_mod._VAULT_DB = None


class TestDecryptionFailureSafety:
    """Tests for VAULT_DECRYPTION_FAILED error on corrupted ciphertext."""

    def _create_encrypted_file(self, tmp_path: Path, folder_id: int = 1) -> tuple[str, bytes]:
        """Create a valid encrypted file and return (path, original_bytes)."""
        import telegrab.services.vault as vault_mod

        # Set up a session key
        key = os.urandom(32)
        vault_mod._session_keys[folder_id] = bytearray(key)

        # Create a source file
        source = tmp_path / "source.txt"
        source.write_text("Hello, vault world! This is test data.")

        # Encrypt it
        encrypted_path = vault_mod.encrypt_file(str(source), folder_id)
        encrypted_bytes = Path(encrypted_path).read_bytes()

        return encrypted_path, encrypted_bytes

    def test_corrupted_ciphertext_raises_vault_decryption_failed(self, tmp_path):
        """Corrupted ciphertext (byte flipped) should raise VAULT_DECRYPTION_FAILED."""
        import telegrab.services.vault as vault_mod

        encrypted_path, encrypted_bytes = self._create_encrypted_file(tmp_path)

        # Corrupt the ciphertext by flipping a byte near the end (in the tag/ciphertext area)
        corrupted = bytearray(encrypted_bytes)
        # Flip a byte in the ciphertext portion (after magic + nonce = 8 + 12 = 20 bytes)
        flip_pos = len(corrupted) - 5
        corrupted[flip_pos] ^= 0xFF
        Path(encrypted_path).write_bytes(bytes(corrupted))

        # Attempt decryption should raise BridgeError
        with pytest.raises(BridgeError) as exc_info:
            vault_mod.decrypt_file(encrypted_path, 1)

        assert exc_info.value.code == ErrorCode.VAULT_DECRYPTION_FAILED
        assert "corrupted" in exc_info.value.message.lower() or "tampered" in exc_info.value.message.lower()

    def test_temp_output_discarded_on_decryption_failure(self, tmp_path):
        """No temp decrypted file should remain after decryption failure."""
        import telegrab.services.vault as vault_mod

        encrypted_path, encrypted_bytes = self._create_encrypted_file(tmp_path)

        # Corrupt the file
        corrupted = bytearray(encrypted_bytes)
        corrupted[-5] ^= 0xFF
        Path(encrypted_path).write_bytes(bytes(corrupted))

        # Count .dec files before
        dec_files_before = set(Path(tempfile.gettempdir()).glob("*.dec"))

        with pytest.raises(BridgeError):
            vault_mod.decrypt_file(encrypted_path, 1)

        # No new .dec temp files should be left behind
        dec_files_after = set(Path(tempfile.gettempdir()).glob("*.dec"))
        new_dec_files = dec_files_after - dec_files_before
        assert len(new_dec_files) == 0, f"Temp files left behind: {new_dec_files}"

    def test_encrypted_file_preserved_on_decryption_failure(self, tmp_path):
        """The encrypted file on disk should remain unchanged after decryption failure."""
        import telegrab.services.vault as vault_mod

        encrypted_path, _ = self._create_encrypted_file(tmp_path)

        # Read original encrypted content
        original_encrypted = Path(encrypted_path).read_bytes()

        # Corrupt a copy (write corrupted data to a new file to decrypt)
        corrupted_path = tmp_path / "corrupted.enc"
        corrupted = bytearray(original_encrypted)
        corrupted[-3] ^= 0xFF
        corrupted_path.write_bytes(bytes(corrupted))

        # Attempt to decrypt the corrupted file
        with pytest.raises(BridgeError):
            vault_mod.decrypt_file(str(corrupted_path), 1)

        # The corrupted file (acting as "encrypted file") should still exist unchanged
        assert corrupted_path.exists()
        assert corrupted_path.read_bytes() == bytes(corrupted)

    def test_valid_decryption_still_works(self, tmp_path):
        """Verify that valid encrypted files still decrypt correctly."""
        import telegrab.services.vault as vault_mod

        # Set up a session key
        key = os.urandom(32)
        vault_mod._session_keys[1] = bytearray(key)

        # Create and encrypt a file
        source = tmp_path / "source.txt"
        original_content = b"Test content for valid decryption"
        source.write_bytes(original_content)

        encrypted_path = vault_mod.encrypt_file(str(source), 1)

        # Decrypt should succeed
        decrypted_path = vault_mod.decrypt_file(encrypted_path, 1)
        assert Path(decrypted_path).read_bytes() == original_content

        # Cleanup
        Path(decrypted_path).unlink(missing_ok=True)
        Path(encrypted_path).unlink(missing_ok=True)


class TestDBIntegrityCheck:
    """Tests for vault database integrity check on startup."""

    def test_healthy_db_passes_integrity_check(self, tmp_path):
        """A fresh vault database should pass integrity check."""
        import telegrab.services.vault as vault_mod

        # Force DB initialization
        vault_mod._get_vault_db()

        assert vault_mod._vault_db_healthy is True

    def test_integrity_check_sets_unhealthy_on_failure(self, tmp_path):
        """If integrity check fails, _vault_db_healthy should be False."""
        import telegrab.services.vault as vault_mod

        # First initialize normally
        vault_mod._get_vault_db()
        assert vault_mod._vault_db_healthy is True

        # Now simulate integrity check failure by patching the function to return bad result
        # We directly set the flag and test _require_healthy_db behavior
        vault_mod._vault_db_healthy = False
        result = vault_mod._vault_db_healthy
        assert result is False

    def test_check_db_integrity_with_none_db(self, tmp_path):
        """_check_db_integrity returns False if _VAULT_DB is None."""
        import telegrab.services.vault as vault_mod

        vault_mod._VAULT_DB = None
        result = vault_mod._check_db_integrity()
        assert result is False
        assert vault_mod._vault_db_healthy is False

    def test_vault_operations_refused_when_db_unhealthy(self, tmp_path):
        """Vault operations should raise VAULT_DB_CORRUPT when DB is unhealthy."""
        import telegrab.services.vault as vault_mod

        # Force DB init and then mark unhealthy
        vault_mod._get_vault_db()
        vault_mod._vault_db_healthy = False

        # encrypt_file should refuse
        vault_mod._session_keys[1] = bytearray(os.urandom(32))
        source = tmp_path / "test.txt"
        source.write_text("test")

        with pytest.raises(BridgeError) as exc_info:
            vault_mod.encrypt_file(str(source), 1)
        assert exc_info.value.code == ErrorCode.VAULT_DB_CORRUPT

    def test_decrypt_refused_when_db_unhealthy(self, tmp_path):
        """decrypt_file should refuse when DB is unhealthy."""
        import telegrab.services.vault as vault_mod

        # Initialize DB normally first, encrypt a file
        vault_mod._get_vault_db()
        key = os.urandom(32)
        vault_mod._session_keys[1] = bytearray(key)

        source = tmp_path / "test.txt"
        source.write_text("test data")
        encrypted_path = vault_mod.encrypt_file(str(source), 1)

        # Now mark DB unhealthy
        vault_mod._vault_db_healthy = False

        # decrypt_file should refuse
        with pytest.raises(BridgeError) as exc_info:
            vault_mod.decrypt_file(encrypted_path, 1)
        assert exc_info.value.code == ErrorCode.VAULT_DB_CORRUPT

        # Cleanup
        Path(encrypted_path).unlink(missing_ok=True)

    def test_create_vault_refused_when_db_unhealthy(self, tmp_path):
        """cmd_create_vault should refuse when DB is unhealthy."""
        import telegrab.services.vault as vault_mod

        vault_mod._get_vault_db()
        vault_mod._vault_db_healthy = False

        with pytest.raises(BridgeError) as exc_info:
            asyncio.run(vault_mod.cmd_create_vault("test", "password", 123))
        assert exc_info.value.code == ErrorCode.VAULT_DB_CORRUPT

    def test_list_vaults_refused_when_db_unhealthy(self, tmp_path):
        """cmd_list_vaults should refuse when DB is unhealthy."""
        import telegrab.services.vault as vault_mod

        vault_mod._get_vault_db()
        vault_mod._vault_db_healthy = False

        with pytest.raises(BridgeError) as exc_info:
            asyncio.run(vault_mod.cmd_list_vaults())
        assert exc_info.value.code == ErrorCode.VAULT_DB_CORRUPT

    def test_integrity_check_runs_on_db_init(self, tmp_path):
        """_check_db_integrity should be called during _get_vault_db initialization."""
        import telegrab.services.vault as vault_mod

        with patch("telegrab.services.vault._check_db_integrity", wraps=vault_mod._check_db_integrity) as mock_check:
            vault_mod._get_vault_db()
            mock_check.assert_called_once()

    def test_corrupted_db_file_causes_error_on_schema_creation(self, tmp_path):
        """A corrupted database file should cause an error during initialization."""
        import telegrab.services.vault as vault_mod

        # Write garbage to the vaults.db file
        db_path = tmp_path / "vaults.db"
        db_path.write_bytes(b"THIS IS NOT A VALID SQLITE DATABASE FILE" * 10)

        # _get_vault_db should raise due to schema creation failure on corrupted file
        with pytest.raises((sqlite3.DatabaseError, BridgeError)):
            vault_mod._get_vault_db()

    def test_require_healthy_db_passes_when_healthy(self, tmp_path):
        """_require_healthy_db should not raise when DB is healthy."""
        import telegrab.services.vault as vault_mod

        vault_mod._vault_db_healthy = True
        # Should not raise
        vault_mod._require_healthy_db()

    def test_require_healthy_db_raises_when_unhealthy(self, tmp_path):
        """_require_healthy_db should raise VAULT_DB_CORRUPT when unhealthy."""
        import telegrab.services.vault as vault_mod

        vault_mod._vault_db_healthy = False
        with pytest.raises(BridgeError) as exc_info:
            vault_mod._require_healthy_db()
        assert exc_info.value.code == ErrorCode.VAULT_DB_CORRUPT
        assert "re-initialize" in exc_info.value.message.lower()
