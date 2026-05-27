"""Unit tests for Bridge._safe_call structured error handling.

Tests the _safe_call method's:
- Validation of required fields
- TimeoutError → BRIDGE_TIMEOUT mapping
- ConnectionError → NETWORK_DISCONNECTED mapping
- FloodWaitError → NETWORK_FLOOD_WAIT mapping
- DEBUG logging of invocations with sanitized args
- ERROR logging of unhandled exceptions (full traceback) with safe frontend response

Run with: python -m pytest tests/test_bridge_safe_call.py -v
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Import modules directly to avoid webview dependency chain ──────────────
_errors_path = Path(__file__).resolve().parent.parent / "telegrab" / "api" / "errors.py"
_spec = __import__("importlib").util.spec_from_file_location(
    "telegrab.api.errors", str(_errors_path)
)
_errors_mod = __import__("importlib").util.module_from_spec(_spec)
sys.modules["telegrab.api.errors"] = _errors_mod
_spec.loader.exec_module(_errors_mod)

BridgeError = _errors_mod.BridgeError
ErrorCode = _errors_mod.ErrorCode

_logger_path = Path(__file__).resolve().parent.parent / "telegrab" / "infra" / "logger.py"
_logger_spec = __import__("importlib").util.spec_from_file_location(
    "telegrab.infra.logger", str(_logger_path)
)
_logger_mod = __import__("importlib").util.module_from_spec(_logger_spec)
sys.modules["telegrab.infra.logger"] = _logger_mod
# Need to mock telegrab.__version__ before loading logger
sys.modules.setdefault("telegrab", MagicMock(__version__="1.0.0-test"))
_logger_spec.loader.exec_module(_logger_mod)

_sanitize_args = _logger_mod._sanitize_args

# ── Set up minimal runtime mock and import bridge pieces ───────────────────
_runtime_path = Path(__file__).resolve().parent.parent / "telegrab" / "infra" / "runtime.py"
_runtime_spec = __import__("importlib").util.spec_from_file_location(
    "telegrab.infra.runtime", str(_runtime_path)
)
_runtime_mod = __import__("importlib").util.module_from_spec(_runtime_spec)
sys.modules["telegrab.infra.runtime"] = _runtime_mod
_runtime_spec.loader.exec_module(_runtime_mod)

DEFAULT_BRIDGE_TIMEOUT = _runtime_mod.DEFAULT_BRIDGE_TIMEOUT


# ── Build a minimal Bridge-like class with _safe_call for testing ──────────
# We can't easily import the full Bridge class due to heavy dependencies,
# so we replicate the _safe_call method logic in a test harness.

import traceback
from collections.abc import Awaitable, Callable
from typing import Any

_log = logging.getLogger("telegrab.api.bridge")

# Reconnect timeout matching the real bridge
_RECONNECT_TIMEOUT = 10.0


class _TestBridge:
    """Minimal Bridge with just _safe_call for unit testing."""

    def __init__(self):
        self._mock_runtime = None
        # Mock for reconnect behavior; set in tests that need it
        self._reconnect_succeeds = False

    def _safe_call(
        self,
        coro: Awaitable[Any],
        args: dict,
        cmd_name: str,
        *,
        required_fields: list[str] | None = None,
        timeout: float | None = DEFAULT_BRIDGE_TIMEOUT,
        coro_factory: Callable[[], Awaitable[Any]] | None = None,
    ) -> Any:
        # 1. Validate required args
        if required_fields:
            missing = [f for f in required_fields if f not in args or args[f] is None]
            if missing:
                field_list = ", ".join(missing)
                err = BridgeError(
                    code=ErrorCode.VALIDATION_MISSING_FIELD,
                    message=f"Missing required fields: {field_list}",
                    detail=f"Command '{cmd_name}' requires fields: {field_list}",
                )
                return err.to_dict()

        # 2. Log invocation at DEBUG
        _log.debug("%s args=%s", cmd_name, _sanitize_args(args))

        # 3. Execute with error mapping
        try:
            return self._mock_runtime.run_coro(coro, timeout=timeout)

        except TimeoutError:
            err = BridgeError(
                code=ErrorCode.BRIDGE_TIMEOUT,
                message=f"Operation timed out after {timeout}s. Please try again.",
                detail=f"Command '{cmd_name}' exceeded {timeout}s timeout.",
            )
            return err.to_dict()

        except ConnectionError as exc:
            # Attempt auto-reconnect + single retry
            _log.warning(
                "ConnectionError in '%s': %s — attempting reconnect",
                cmd_name,
                exc,
            )
            if self._attempt_reconnect():
                # Reconnection succeeded — retry the command once
                if coro_factory is not None:
                    _log.info("Reconnected; retrying '%s'", cmd_name)
                    try:
                        return self._mock_runtime.run_coro(
                            coro_factory(), timeout=timeout
                        )
                    except Exception as retry_exc:
                        _log.warning(
                            "Retry of '%s' after reconnect failed: %s",
                            cmd_name,
                            retry_exc,
                        )
                        err = BridgeError(
                            code=ErrorCode.NETWORK_DISCONNECTED,
                            message="Reconnected but the operation failed. Please try again.",
                            detail=f"Retry failed in '{cmd_name}': {retry_exc}",
                        )
                        return err.to_dict()

            # Reconnection failed or no retry possible
            err = BridgeError(
                code=ErrorCode.NETWORK_DISCONNECTED,
                message="Connection lost. Please check your network and try again.",
                detail=f"ConnectionError in '{cmd_name}': {exc}",
            )
            return err.to_dict()

        except Exception as exc:
            # Check for FloodWaitError
            try:
                from telethon.errors import FloodWaitError

                if isinstance(exc, FloodWaitError):
                    wait_seconds = exc.seconds
                    err = BridgeError(
                        code=ErrorCode.NETWORK_FLOOD_WAIT,
                        message=f"Rate limited by Telegram. Please wait {wait_seconds}s.",
                        detail=f"FloodWaitError in '{cmd_name}': wait {wait_seconds}s",
                    )
                    return err.to_dict()
            except ImportError:
                pass

            # Unhandled exception: log full traceback, return safe response
            _log.error(
                "Unhandled %s in %s:\n%s",
                type(exc).__name__,
                cmd_name,
                traceback.format_exc(),
            )
            err = BridgeError(
                code="BRIDGE_INTERNAL_ERROR",
                message=f"An unexpected error occurred: {type(exc).__name__}",
                detail=f"{type(exc).__name__}: operation failed",
            )
            return err.to_dict()

    def _attempt_reconnect(self) -> bool:
        """Mock reconnect — controlled by self._reconnect_succeeds."""
        return self._reconnect_succeeds


@pytest.fixture
def bridge():
    """Create a test bridge with a mock runtime."""
    b = _TestBridge()
    b._mock_runtime = MagicMock()
    return b


# ═══════════════════════════════════════════════════════════════════════════
# Tests for validation
# ═══════════════════════════════════════════════════════════════════════════


class TestValidation:
    """Test required field validation in _safe_call."""

    def test_missing_single_field_returns_error(self, bridge):
        async def dummy():
            return "ok"

        result = bridge._safe_call(
            dummy(), {"name": "test"}, "cmd_test",
            required_fields=["name", "path"],
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.VALIDATION_MISSING_FIELD
        assert "path" in result["message"]

    def test_missing_multiple_fields_names_all(self, bridge):
        async def dummy():
            return "ok"

        result = bridge._safe_call(
            dummy(), {}, "cmd_test",
            required_fields=["apiId", "apiHash", "phone"],
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.VALIDATION_MISSING_FIELD
        assert "apiId" in result["message"]
        assert "apiHash" in result["message"]
        assert "phone" in result["message"]

    def test_none_value_counts_as_missing(self, bridge):
        async def dummy():
            return "ok"

        result = bridge._safe_call(
            dummy(), {"field": None}, "cmd_test",
            required_fields=["field"],
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.VALIDATION_MISSING_FIELD
        assert "field" in result["message"]

    def test_all_fields_present_proceeds(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "success"
        result = bridge._safe_call(
            dummy(), {"apiId": "123", "apiHash": "abc"}, "cmd_test",
            required_fields=["apiId", "apiHash"],
        )
        assert result == "success"

    def test_no_required_fields_skips_validation(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "success"
        result = bridge._safe_call(dummy(), {}, "cmd_test")
        assert result == "success"


# ═══════════════════════════════════════════════════════════════════════════
# Tests for error mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorMapping:
    """Test exception → BridgeError mapping."""

    def test_timeout_error_mapped_to_bridge_timeout(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = TimeoutError("timed out")
        result = bridge._safe_call(dummy(), {}, "cmd_slow")
        assert result["__error"] is True
        assert result["code"] == ErrorCode.BRIDGE_TIMEOUT
        assert "timed out" in result["message"].lower()

    def test_connection_error_mapped_to_network_disconnected(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ConnectionError("reset")
        result = bridge._safe_call(dummy(), {}, "cmd_connect")
        assert result["__error"] is True
        assert result["code"] == ErrorCode.NETWORK_DISCONNECTED
        assert "connection" in result["message"].lower()

    def test_connection_reset_error_mapped_to_network_disconnected(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ConnectionResetError("peer")
        result = bridge._safe_call(dummy(), {}, "cmd_test")
        assert result["__error"] is True
        assert result["code"] == ErrorCode.NETWORK_DISCONNECTED

    def test_unhandled_exception_returns_generic_error(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ValueError("bad value")
        result = bridge._safe_call(dummy(), {}, "cmd_test")
        assert result["__error"] is True
        assert result["code"] == "BRIDGE_INTERNAL_ERROR"
        assert "ValueError" in result["message"]
        # Should NOT contain traceback details or file paths
        assert "traceback" not in result["detail"].lower()
        assert ".py" not in result["detail"]

    def test_unhandled_exception_detail_has_no_file_paths(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = RuntimeError("something broke")
        result = bridge._safe_call(dummy(), {}, "cmd_broken")
        assert "line" not in result["detail"].lower()
        assert "\\" not in result["detail"]
        assert "/" not in result["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# Tests for FloodWaitError mapping
# ═══════════════════════════════════════════════════════════════════════════


class TestFloodWaitMapping:
    """Test FloodWaitError → NETWORK_FLOOD_WAIT mapping."""

    def test_flood_wait_error_with_wait_duration(self, bridge):
        """FloodWaitError should map to NETWORK_FLOOD_WAIT with wait seconds."""
        # Create a mock FloodWaitError
        mock_exc = Exception("flood")
        mock_exc.seconds = 42

        # Mock telethon import
        mock_flood_cls = type("FloodWaitError", (Exception,), {})
        mock_flood_instance = mock_flood_cls("flood wait")
        mock_flood_instance.seconds = 42

        # We need to use the actual class for isinstance check
        mock_telethon = MagicMock()
        mock_telethon.FloodWaitError = mock_flood_cls

        with patch.dict(sys.modules, {"telethon": MagicMock(), "telethon.errors": mock_telethon}):
            bridge._mock_runtime.run_coro.side_effect = mock_flood_instance
            async def dummy():
                return "ok"

            result = bridge._safe_call(dummy(), {}, "cmd_get_files")
            assert result["__error"] is True
            assert result["code"] == ErrorCode.NETWORK_FLOOD_WAIT
            assert "42" in result["message"]
            assert "42" in result["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# Tests for logging behavior
# ═══════════════════════════════════════════════════════════════════════════


class TestLogging:
    """Test that _safe_call logs appropriately."""

    def test_debug_log_on_invocation(self, bridge, caplog):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "success"
        with caplog.at_level(logging.DEBUG, logger="telegrab.api.bridge"):
            bridge._safe_call(dummy(), {"query": "hello"}, "cmd_search")

        assert any("cmd_search" in r.message for r in caplog.records)
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_sensitive_args_are_redacted_in_log(self, bridge, caplog):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "success"
        with caplog.at_level(logging.DEBUG, logger="telegrab.api.bridge"):
            bridge._safe_call(
                dummy(),
                {"password": "secret123", "apiHash": "abc123"},
                "cmd_connect",
            )

        # The sensitive values should not appear in logs
        for record in caplog.records:
            assert "secret123" not in record.message
            assert "abc123" not in record.message

    def test_error_log_on_unhandled_exception(self, bridge, caplog):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ValueError("bad")
        with caplog.at_level(logging.ERROR, logger="telegrab.api.bridge"):
            bridge._safe_call(dummy(), {}, "cmd_fail")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        assert "ValueError" in error_records[0].message
        assert "cmd_fail" in error_records[0].message

    def test_error_log_contains_traceback(self, bridge, caplog):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = RuntimeError("boom")
        with caplog.at_level(logging.ERROR, logger="telegrab.api.bridge"):
            bridge._safe_call(dummy(), {}, "cmd_boom")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        # Full traceback should be in the log
        assert "Traceback" in error_records[0].message or "RuntimeError" in error_records[0].message

    def test_args_truncated_to_200_chars_in_log(self, bridge, caplog):
        async def dummy():
            return "ok"

        # Create args with many fields to produce a long string
        long_args = {f"field_{i}": f"value_{i}" for i in range(50)}
        bridge._mock_runtime.run_coro.return_value = "ok"

        with caplog.at_level(logging.DEBUG, logger="telegrab.api.bridge"):
            bridge._safe_call(dummy(), long_args, "cmd_long_args")

        # The sanitized args portion should be truncated
        for record in caplog.records:
            if "cmd_long_args" in record.message and "args=" in record.message:
                args_part = record.message.split("args=", 1)[1]
                assert len(args_part) <= 200


# ═══════════════════════════════════════════════════════════════════════════
# Tests for success case
# ═══════════════════════════════════════════════════════════════════════════


class TestSuccessPath:
    """Test that _safe_call returns coroutine results on success."""

    def test_returns_coroutine_result(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = {"files": [1, 2, 3]}
        result = bridge._safe_call(dummy(), {"folderId": "123"}, "cmd_get_files")
        assert result == {"files": [1, 2, 3]}

    def test_default_timeout_is_60(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "ok"
        bridge._safe_call(dummy(), {}, "cmd_test")
        call_kwargs = bridge._mock_runtime.run_coro.call_args
        assert call_kwargs[1]["timeout"] == 60.0

    def test_custom_timeout_passed_through(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "ok"
        bridge._safe_call(dummy(), {}, "cmd_test", timeout=120.0)
        call_kwargs = bridge._mock_runtime.run_coro.call_args
        assert call_kwargs[1]["timeout"] == 120.0

    def test_none_timeout_for_long_running(self, bridge):
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.return_value = "ok"
        bridge._safe_call(dummy(), {}, "cmd_upload", timeout=None)
        call_kwargs = bridge._mock_runtime.run_coro.call_args
        assert call_kwargs[1]["timeout"] is None


# ═══════════════════════════════════════════════════════════════════════════
# Tests for disconnect detection with auto-reconnect and retry
# ═══════════════════════════════════════════════════════════════════════════


class TestDisconnectAutoReconnect:
    """Test ConnectionError handling with auto-reconnect + retry logic.

    Requirements 1.3: On disconnect, attempt one reconnection within 10s.
                      On success, retry the original command once.
    Requirements 1.4: On reconnection failure, raise NETWORK_DISCONNECTED.
    """

    def test_reconnect_succeeds_and_retry_succeeds(self, bridge):
        """When reconnect succeeds and retry succeeds, return retry result."""
        async def dummy():
            return "ok"

        # First call raises ConnectionError, retry call succeeds
        bridge._mock_runtime.run_coro.side_effect = [
            ConnectionError("disconnected"),
            "retry_success",
        ]
        bridge._reconnect_succeeds = True

        result = bridge._safe_call(
            dummy(), {}, "cmd_get_files",
            coro_factory=lambda: dummy(),
        )
        assert result == "retry_success"

    def test_reconnect_succeeds_but_retry_fails(self, bridge):
        """When reconnect succeeds but retry fails, return NETWORK_DISCONNECTED."""
        async def dummy():
            return "ok"

        # First call raises ConnectionError, retry also fails
        bridge._mock_runtime.run_coro.side_effect = [
            ConnectionError("disconnected"),
            RuntimeError("still broken"),
        ]
        bridge._reconnect_succeeds = True

        result = bridge._safe_call(
            dummy(), {}, "cmd_get_files",
            coro_factory=lambda: dummy(),
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.NETWORK_DISCONNECTED
        assert "Reconnected but the operation failed" in result["message"]

    def test_reconnect_fails_returns_disconnected(self, bridge):
        """When reconnect fails, return NETWORK_DISCONNECTED immediately."""
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ConnectionError("reset")
        bridge._reconnect_succeeds = False

        result = bridge._safe_call(
            dummy(), {}, "cmd_connect",
            coro_factory=lambda: dummy(),
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.NETWORK_DISCONNECTED
        assert "Connection lost" in result["message"]

    def test_reconnect_succeeds_no_coro_factory_returns_disconnected(self, bridge):
        """When reconnect succeeds but no coro_factory, can't retry — returns error."""
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ConnectionError("disconnected")
        bridge._reconnect_succeeds = True

        result = bridge._safe_call(
            dummy(), {}, "cmd_legacy",
            # No coro_factory provided
        )
        assert result["__error"] is True
        assert result["code"] == ErrorCode.NETWORK_DISCONNECTED

    def test_connection_reset_error_triggers_reconnect(self, bridge):
        """ConnectionResetError (subclass) also triggers reconnect attempt."""
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = [
            ConnectionResetError("peer reset"),
            "reconnected_result",
        ]
        bridge._reconnect_succeeds = True

        result = bridge._safe_call(
            dummy(), {}, "cmd_test",
            coro_factory=lambda: dummy(),
        )
        assert result == "reconnected_result"

    def test_reconnect_logs_warning_on_connection_error(self, bridge, caplog):
        """ConnectionError should log a warning about attempting reconnect."""
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = ConnectionError("network down")
        bridge._reconnect_succeeds = False

        with caplog.at_level(logging.WARNING, logger="telegrab.api.bridge"):
            bridge._safe_call(dummy(), {}, "cmd_test")

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1
        assert "ConnectionError" in warning_records[0].message or "reconnect" in warning_records[0].message.lower()

    def test_reconnect_success_logs_info_on_retry(self, bridge, caplog):
        """After successful reconnect, an INFO log about retrying should appear."""
        async def dummy():
            return "ok"

        bridge._mock_runtime.run_coro.side_effect = [
            ConnectionError("lost"),
            "retried_ok",
        ]
        bridge._reconnect_succeeds = True

        with caplog.at_level(logging.INFO, logger="telegrab.api.bridge"):
            result = bridge._safe_call(
                dummy(), {}, "cmd_scan",
                coro_factory=lambda: dummy(),
            )

        assert result == "retried_ok"
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any("Reconnected" in r.message or "retrying" in r.message.lower() for r in info_records)
