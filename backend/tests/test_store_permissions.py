"""Unit tests for store permission validation, correction, and DPAPI fallback.

Tests cover:
- Permission validation on Unix (mode 0o600 check)
- Permission correction when too permissive
- Warning logged when permissions are incorrect
- DPAPI fallback to base64 with warning logged on Windows
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import telegrab.infra.store as store_module
from telegrab.infra.store import (
    JsonStore,
    _encrypt,
    _validate_permissions,
)


class TestPermissionValidation:
    """Tests for _validate_permissions function."""

    def _make_store_file(self, tmp_path: Path, mode: int = 0o600) -> Path:
        """Create a store file with specified permissions."""
        store_file = tmp_path / "store.json"
        store_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        if sys.platform != "win32":
            store_file.chmod(mode)
        return store_file

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific permission test")
    def test_valid_permissions_no_warning(self, tmp_path, caplog):
        """No warning when file has correct 0o600 permissions."""
        store_file = self._make_store_file(tmp_path, 0o600)

        with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
            _validate_permissions(store_file)

        assert "permissions" not in caplog.text.lower() or "corrected" not in caplog.text.lower()
        # More specifically, no warning about being too permissive
        assert "too permissive" not in caplog.text
        assert "attempting to correct" not in caplog.text

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific permission test")
    def test_permissive_permissions_logs_warning(self, tmp_path, caplog):
        """Warning logged when file has overly permissive permissions (e.g. 0o644)."""
        store_file = self._make_store_file(tmp_path, 0o644)

        with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
            _validate_permissions(store_file)

        assert "0644" in caplog.text or "permissions" in caplog.text.lower()

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific permission test")
    def test_permissive_permissions_corrected(self, tmp_path):
        """Permissions are corrected from 0o644 to 0o600."""
        store_file = self._make_store_file(tmp_path, 0o644)

        _validate_permissions(store_file)

        mode = os.stat(str(store_file)).st_mode & 0o777
        assert mode == 0o600

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific permission test")
    def test_world_readable_permissions_corrected(self, tmp_path):
        """Permissions are corrected from 0o777 to 0o600."""
        store_file = self._make_store_file(tmp_path, 0o777)

        _validate_permissions(store_file)

        mode = os.stat(str(store_file)).st_mode & 0o777
        assert mode == 0o600

    def test_nonexistent_file_no_error(self, tmp_path):
        """No error when file doesn't exist."""
        store_file = tmp_path / "nonexistent.json"

        # Should not raise
        _validate_permissions(store_file)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific permission test")
    def test_windows_icacls_called(self, tmp_path):
        """On Windows, icacls is called to inspect permissions."""
        store_file = self._make_store_file(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=f"JITHI:(R,W)", returncode=0)
            _validate_permissions(store_file)

            # icacls should have been called to inspect
            mock_run.assert_called()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific permission test")
    def test_windows_permissive_acl_logs_warning(self, tmp_path, caplog):
        """On Windows, warning logged when ACL includes Everyone."""
        store_file = self._make_store_file(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=f"{store_file} Everyone:(R)\n                JITHI:(R,W)",
                returncode=0,
            )
            # Reset the global flag to allow _restrict_permissions to run
            store_module._permissions_set = False

            with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
                _validate_permissions(store_file)

            assert "too permissive" in caplog.text


class TestStorePermissionOnStartup:
    """Tests that JsonStore validates permissions on initialization."""

    def _make_store(self, tmp_path, mode: int = 0o600):
        """Create a JsonStore with a temp file."""
        store_file = tmp_path / "store.json"
        store_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        if sys.platform != "win32":
            store_file.chmod(mode)

        # Reset global flag
        store_module._permissions_set = False

        with patch.object(store_module, "store_path", return_value=store_file):
            obj = JsonStore()
        return obj, store_file

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_store_init_sets_correct_permissions(self, tmp_path):
        """JsonStore.__init__ sets 0o600 permissions on the store file."""
        store_file = tmp_path / "store.json"
        store_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        store_file.chmod(0o644)

        store_module._permissions_set = False

        with patch.object(store_module, "store_path", return_value=store_file):
            store = JsonStore()

        mode = os.stat(str(store_file)).st_mode & 0o777
        assert mode == 0o600

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    def test_store_init_validates_after_restrict(self, tmp_path, caplog):
        """JsonStore.__init__ calls both restrict and validate on startup."""
        store_file = tmp_path / "store.json"
        store_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        store_file.chmod(0o600)

        store_module._permissions_set = False

        with patch.object(store_module, "store_path", return_value=store_file):
            with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
                store = JsonStore()

        # Should not have warning since permissions are correct after restrict
        assert "too permissive" not in caplog.text


class TestDPAPIFallback:
    """Tests for DPAPI fallback to base64 with warning."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI test")
    def test_dpapi_failure_falls_back_to_base64(self, caplog):
        """When DPAPI fails, _encrypt falls back to base64 and logs warning."""
        import ctypes

        test_data = b"sensitive data"

        # Mock CryptProtectData to fail
        with patch.object(
            ctypes.windll.crypt32, "CryptProtectData", return_value=False
        ):
            with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
                result = _encrypt(test_data)

        # Should still return a base64 result
        import base64

        assert base64.b64decode(result) == test_data
        assert "DPAPI" in caplog.text
        assert "falling back to base64" in caplog.text

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI test")
    def test_dpapi_exception_falls_back_to_base64(self, caplog):
        """When DPAPI raises an exception, _encrypt falls back to base64."""
        test_data = b"sensitive data"

        with patch.dict("sys.modules", {"ctypes": None}):
            # Force import error for ctypes inside _encrypt
            pass

        # Instead, mock the function to raise
        with patch("sys.platform", "win32"):
            with patch(
                "ctypes.windll.crypt32.CryptProtectData",
                side_effect=OSError("DPAPI unavailable"),
            ):
                with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
                    result = _encrypt(test_data)

        import base64

        assert base64.b64decode(result) == test_data
        assert "DPAPI" in caplog.text or "falling back" in caplog.text

    def test_non_windows_uses_base64_without_dpapi_warning(self, caplog):
        """On non-Windows, _encrypt uses base64 without DPAPI warnings."""
        test_data = b"sensitive data"

        with patch("sys.platform", "linux"):
            with caplog.at_level(logging.WARNING, logger="telegrab.infra.store"):
                result = _encrypt(test_data)

        import base64

        assert base64.b64decode(result) == test_data
        # No DPAPI warning on non-Windows
        assert "DPAPI" not in caplog.text
