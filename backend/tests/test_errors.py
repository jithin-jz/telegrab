"""Unit tests for the BridgeError dataclass and ErrorCode constants.

Run with: python -m pytest tests/test_errors.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Import the module directly to avoid triggering webview dependency chain
_errors_path = Path(__file__).resolve().parent.parent / "telegrab" / "api" / "errors.py"
_spec = __import__("importlib").util.spec_from_file_location(
    "telegrab.api.errors", str(_errors_path)
)
_mod = __import__("importlib").util.module_from_spec(_spec)
sys.modules["telegrab.api.errors"] = _mod
_spec.loader.exec_module(_mod)

BridgeError = _mod.BridgeError
ErrorCode = _mod.ErrorCode
ERROR_CODE_PATTERN = _mod.ERROR_CODE_PATTERN
MAX_MESSAGE_LENGTH = _mod.MAX_MESSAGE_LENGTH
MAX_DETAIL_LENGTH = _mod.MAX_DETAIL_LENGTH


class TestBridgeError:
    """Tests for BridgeError dataclass."""

    def test_basic_creation(self):
        e = BridgeError(code="NETWORK_TIMEOUT", message="Timed out", detail="After 60s")
        assert e.code == "NETWORK_TIMEOUT"
        assert e.message == "Timed out"
        assert e.detail == "After 60s"

    def test_to_dict(self):
        e = BridgeError(code="VAULT_LOCKED", message="Vault is locked", detail="folder 42")
        d = e.to_dict()
        assert d == {
            "__error": True,
            "code": "VAULT_LOCKED",
            "message": "Vault is locked",
            "detail": "folder 42",
        }

    def test_invalid_code_format_raises(self):
        with pytest.raises(ValueError, match="must match"):
            BridgeError(code="invalid_code", message="msg", detail="det")

    def test_code_with_lowercase_raises(self):
        with pytest.raises(ValueError, match="must match"):
            BridgeError(code="Network_Timeout", message="msg", detail="det")

    def test_code_without_underscore_raises(self):
        with pytest.raises(ValueError, match="must match"):
            BridgeError(code="TIMEOUT", message="msg", detail="det")

    def test_message_truncated_at_200(self):
        long_msg = "a" * 300
        e = BridgeError(code="BRIDGE_TIMEOUT", message=long_msg, detail="d")
        assert len(e.message) == MAX_MESSAGE_LENGTH

    def test_detail_truncated_at_1000(self):
        long_detail = "b" * 2000
        e = BridgeError(code="STORE_CORRUPT", message="m", detail=long_detail)
        assert len(e.detail) == MAX_DETAIL_LENGTH

    def test_message_at_exact_limit_not_truncated(self):
        msg = "c" * MAX_MESSAGE_LENGTH
        e = BridgeError(code="NETWORK_TIMEOUT", message=msg, detail="d")
        assert e.message == msg

    def test_detail_at_exact_limit_not_truncated(self):
        det = "d" * MAX_DETAIL_LENGTH
        e = BridgeError(code="NETWORK_TIMEOUT", message="m", detail=det)
        assert e.detail == det

    def test_frozen_cannot_modify(self):
        e = BridgeError(code="NETWORK_TIMEOUT", message="msg", detail="det")
        with pytest.raises(AttributeError):
            e.code = "VAULT_LOCKED"


class TestErrorCode:
    """Tests for ErrorCode constants."""

    def test_all_codes_match_pattern(self):
        for attr in dir(ErrorCode):
            if attr.startswith("_"):
                continue
            val = getattr(ErrorCode, attr)
            assert ERROR_CODE_PATTERN.match(val), (
                f"ErrorCode.{attr} = {val!r} does not match {ERROR_CODE_PATTERN.pattern}"
            )

    def test_all_required_categories_present(self):
        codes = [
            getattr(ErrorCode, a)
            for a in dir(ErrorCode)
            if not a.startswith("_")
        ]
        categories = {c.split("_")[0] for c in codes}
        expected = {"NETWORK", "VALIDATION", "TRANSFER", "VAULT", "STORE", "BRIDGE"}
        assert expected.issubset(categories), (
            f"Missing categories: {expected - categories}"
        )

    def test_network_codes(self):
        assert ErrorCode.NETWORK_TIMEOUT == "NETWORK_TIMEOUT"
        assert ErrorCode.NETWORK_DISCONNECTED == "NETWORK_DISCONNECTED"
        assert ErrorCode.NETWORK_FLOOD_WAIT == "NETWORK_FLOOD_WAIT"
        assert ErrorCode.NETWORK_UNAVAILABLE == "NETWORK_UNAVAILABLE"

    def test_validation_codes(self):
        assert ErrorCode.VALIDATION_MISSING_FIELD == "VALIDATION_MISSING_FIELD"
        assert ErrorCode.VALIDATION_INVALID_TYPE == "VALIDATION_INVALID_TYPE"

    def test_transfer_codes(self):
        assert ErrorCode.TRANSFER_CANCELLED == "TRANSFER_CANCELLED"
        assert ErrorCode.TRANSFER_NETWORK_ERROR == "TRANSFER_NETWORK_ERROR"
        assert ErrorCode.TRANSFER_FILE_NOT_FOUND == "TRANSFER_FILE_NOT_FOUND"
        assert ErrorCode.TRANSFER_CLEANUP_FAILED == "TRANSFER_CLEANUP_FAILED"

    def test_vault_codes(self):
        assert ErrorCode.VAULT_LOCKED == "VAULT_LOCKED"
        assert ErrorCode.VAULT_DECRYPTION_FAILED == "VAULT_DECRYPTION_FAILED"
        assert ErrorCode.VAULT_DB_CORRUPT == "VAULT_DB_CORRUPT"
        assert ErrorCode.VAULT_WRONG_PASSWORD == "VAULT_WRONG_PASSWORD"

    def test_store_codes(self):
        assert ErrorCode.STORE_CORRUPT == "STORE_CORRUPT"
        assert ErrorCode.STORE_PERMISSION_ERROR == "STORE_PERMISSION_ERROR"

    def test_bridge_codes(self):
        assert ErrorCode.BRIDGE_TIMEOUT == "BRIDGE_TIMEOUT"
        assert ErrorCode.BRIDGE_NOT_READY == "BRIDGE_NOT_READY"

    def test_attribute_names_match_values(self):
        """Each constant's attribute name should equal its value."""
        for attr in dir(ErrorCode):
            if attr.startswith("_"):
                continue
            assert attr == getattr(ErrorCode, attr)
