"""Tests for the bridge's error contract.

Every ``cmd_*`` method on the real :class:`Bridge` must return a structured
``{"__error": True, ...}`` dict instead of letting an exception (and its
traceback) cross into the webview.
"""

from __future__ import annotations

import logging

import pytest

from telegrab.api import bridge as bridge_mod
from telegrab.api.bridge import Bridge, error_response
from telegrab.api.errors import BridgeError, ErrorCode
from telegrab.services import NotConnectedError


def _code(result) -> str:
    assert isinstance(result, dict) and result.get("__error") is True, result
    return result["code"]


class TestErrorResponse:
    def test_bridge_error_passes_through(self):
        err = BridgeError(ErrorCode.VAULT_WRONG_PASSWORD, "Incorrect password", "d")
        assert error_response(err, "cmd_x") == err.to_dict()

    def test_not_connected(self):
        result = error_response(NotConnectedError("offline"), "cmd_x")
        assert _code(result) == ErrorCode.TELEGRAM_NOT_CONNECTED
        assert result["message"] == "offline"

    def test_timeout(self):
        assert _code(error_response(TimeoutError(), "cmd_x")) == ErrorCode.BRIDGE_TIMEOUT

    def test_flood_wait_keeps_sentinel(self):
        from telethon.errors import FloodWaitError

        exc = FloodWaitError(request=None, capture=42)
        result = error_response(exc, "cmd_x")
        assert _code(result) == ErrorCode.NETWORK_FLOOD_WAIT
        assert "FLOOD_WAIT_42" in result["message"]

    def test_connection_error_attempts_reconnect(self, monkeypatch):
        calls = []
        monkeypatch.setattr(bridge_mod, "_attempt_reconnect", lambda: calls.append(1) or False)
        result = error_response(ConnectionError("reset"), "cmd_x")
        assert _code(result) == ErrorCode.NETWORK_DISCONNECTED
        assert calls == [1]

    def test_missing_field(self):
        result = error_response(KeyError("apiId"), "cmd_connect")
        assert _code(result) == ErrorCode.VALIDATION_MISSING_FIELD
        assert "apiId" in result["message"]

    def test_user_facing_messages_preserved(self):
        result = error_response(RuntimeError("Vault is locked. Unlock it first."), "cmd_x")
        assert _code(result) == ErrorCode.COMMAND_FAILED
        assert result["message"] == "Vault is locked. Unlock it first."

    def test_unexpected_error_is_generic_and_logged(self, caplog):
        with caplog.at_level(logging.ERROR, logger="telegrab.api.bridge"):
            result = error_response(ZeroDivisionError("secret detail"), "cmd_x")
        assert _code(result) == ErrorCode.BRIDGE_INTERNAL_ERROR
        assert "secret detail" not in result["message"]
        assert "Traceback" in caplog.text or "ZeroDivisionError" in caplog.text

    def test_bridge_error_str_is_message(self):
        assert str(BridgeError(ErrorCode.COMMAND_FAILED, "boom", "d")) == "boom"


class TestBridgeCommands:
    def test_every_command_is_wrapped(self):
        names = [n for n in vars(Bridge) if n.startswith("cmd_")]
        assert names
        for name in names:
            assert getattr(getattr(Bridge, name), "__bridge_command__", False), name

    def test_missing_arg_returns_structured_error(self):
        result = Bridge().cmd_connect({})
        assert _code(result) == ErrorCode.VALIDATION_MISSING_FIELD

    def test_service_error_returns_structured_error(self, monkeypatch):
        async def boom(*a, **kw):
            raise RuntimeError("Folder name cannot be empty.")

        monkeypatch.setattr(bridge_mod.folder_cmds, "cmd_create_folder", boom)
        result = Bridge().cmd_create_folder({"name": ""})
        assert _code(result) == ErrorCode.COMMAND_FAILED
        assert result["message"] == "Folder name cannot be empty."

    def test_get_files_forwards_pagination_args(self, monkeypatch):
        seen = {}

        async def fake_get_files(folder_id, limit=100, offset_id=0):
            seen.update(folder_id=folder_id, limit=limit, offset_id=offset_id)
            return {"files": [], "next_offset_id": 0}

        monkeypatch.setattr(bridge_mod.file_cmds, "cmd_get_files", fake_get_files)
        Bridge().cmd_get_files({"folderId": 42, "offsetId": 9999, "limit": 100})
        assert seen == {"folder_id": 42, "limit": 100, "offset_id": 9999}

    def test_update_install_ignores_js_supplied_url(self, monkeypatch):
        called = []
        monkeypatch.setattr(
            bridge_mod.updater_cmds,
            "cmd_download_and_install_update",
            lambda *a, **kw: called.append((a, kw)),
        )
        Bridge().cmd_download_and_install_update(
            {"url": "https://github.com/evil/x/releases/download/v9/x.exe", "sha256": "a" * 64}
        )
        assert called == [((), {})]

    @pytest.mark.parametrize("value", [None, "", 0])
    def test_get_files_defaults(self, monkeypatch, value):
        seen = {}

        async def fake_get_files(folder_id, limit=100, offset_id=0):
            seen.update(limit=limit, offset_id=offset_id)
            return {"files": [], "next_offset_id": 0}

        monkeypatch.setattr(bridge_mod.file_cmds, "cmd_get_files", fake_get_files)
        Bridge().cmd_get_files({"folderId": None, "offsetId": value, "limit": value})
        assert seen == {"limit": 100, "offset_id": 0}
