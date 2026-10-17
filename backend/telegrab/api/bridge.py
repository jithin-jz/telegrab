"""pywebview ←→ JS bridge.

Every public ``cmd_*`` method on `Bridge` becomes available to JS as
`window.pywebview.api.<method_name>(args)`. The frontend's shim layer
(see `frontend/src/lib/platform/`) translates `invoke('cmd_x', argsObj)`
into `window.pywebview.api.cmd_x(argsObj)`.

Argument convention
-------------------
Every method accepts a single `args` dict (camelCase keys). We extract the
fields and forward to the async use-case implementations on the runtime
asyncio loop.

Error convention
----------------
No exception ever crosses the bridge. Each command is wrapped by
:func:`_bridge_command`, which converts failures into a structured
``BridgeError.to_dict()`` (``{"__error": true, code, message, detail}``)
that the frontend's ``invoke`` turns back into a thrown error. Unexpected
exceptions are logged with a full traceback here and reach the UI only as a
generic message — Python tracebacks are never sent to the webview.
"""

from __future__ import annotations

import functools
import logging
import traceback
from collections.abc import Callable
from typing import Any

from ..infra import get_runtime
from ..infra.logger import _sanitize_args
from ..infra.runtime import DEFAULT_BRIDGE_TIMEOUT
from ..services import NotConnectedError
from ..services import auth as auth_cmds
from ..services import dedup as dedup_cmds
from ..services import files as file_cmds
from ..services import folders as folder_cmds
from ..services import network as network_cmds
from ..services import pins as pin_cmds
from ..services import preview as preview_cmds
from ..services import updater as updater_cmds
from ..services import vault as vault_cmds
from . import host as host_cmds
from .errors import BridgeError, ErrorCode

log = logging.getLogger(__name__)

# Timeout for the auto-reconnect attempt on disconnect (seconds).
_RECONNECT_TIMEOUT = 10.0


def _run(coro):
    """Run an async coroutine on the runtime loop and return its result.

    Uses the runtime's default short timeout — suitable for routine RPCs
    (auth, listing, metadata, etc.). Long-running calls should use
    :func:`_run_long` instead.
    """
    return get_runtime().run_coro(coro, timeout=DEFAULT_BRIDGE_TIMEOUT)


def _run_long(coro):
    """Run a coroutine without a timeout — for file transfers, streaming
    info that may include large I/O, or long-running cancellable jobs.
    """
    return get_runtime().run_coro(coro, timeout=None)


def _args(maybe_args: Any) -> dict:
    """Normalise the single-argument payload from JS into a dict."""
    if maybe_args is None:
        return {}
    if isinstance(maybe_args, dict):
        return maybe_args
    return {"_value": maybe_args}


def _opt_int(value: Any) -> int | None:
    return int(value) if value is not None else None


# ─────────────────────────────── error mapping ───────────────────────────────


def _attempt_reconnect() -> bool:
    """Try to reconnect the Telegram client within 10 seconds."""
    from ..telegram.client import ensure_client, get_state

    async def _reconnect() -> bool:
        state = get_state()
        if state.api_id is None or not state.api_hash:
            return False
        client = await ensure_client(state.api_id, state.api_hash)
        return client.is_connected()

    try:
        return get_runtime().run_coro(_reconnect(), timeout=_RECONNECT_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        log.warning("Auto-reconnect failed: %s", exc)
        return False


def error_response(exc: BaseException, cmd_name: str) -> dict:
    """Map an exception raised by a command to a structured error dict."""
    if isinstance(exc, BridgeError):
        return exc.to_dict()

    from telethon.errors import FloodWaitError, RPCError

    from ..telegram.errors import map_error

    if isinstance(exc, NotConnectedError):
        err = BridgeError(ErrorCode.TELEGRAM_NOT_CONNECTED, str(exc), cmd_name)
    elif isinstance(exc, TimeoutError):
        err = BridgeError(
            ErrorCode.BRIDGE_TIMEOUT,
            "The operation timed out. Please try again.",
            f"Command '{cmd_name}' timed out",
        )
    elif isinstance(exc, FloodWaitError):
        # Keep the FLOOD_WAIT_<n> sentinel: the auth UI parses it.
        err = BridgeError(
            ErrorCode.NETWORK_FLOOD_WAIT,
            f"{map_error(exc)}: Telegram rate limit, please wait {exc.seconds}s.",
            f"FloodWaitError in '{cmd_name}': wait {exc.seconds}s",
        )
    elif isinstance(exc, ConnectionError):
        log.warning("ConnectionError in '%s': %s — attempting reconnect", cmd_name, exc)
        reconnected = _attempt_reconnect()
        err = BridgeError(
            ErrorCode.NETWORK_DISCONNECTED,
            "Connection was interrupted. Please try again."
            if reconnected
            else "Connection lost. Please check your network and try again.",
            f"ConnectionError in '{cmd_name}': {exc}",
        )
    elif isinstance(exc, KeyError):
        err = BridgeError(
            ErrorCode.VALIDATION_MISSING_FIELD,
            f"Missing required field: {exc.args[0] if exc.args else '?'}",
            f"Command '{cmd_name}' was called without a required field",
        )
    elif isinstance(exc, RPCError):
        err = BridgeError(ErrorCode.TELEGRAM_RPC_ERROR, map_error(exc), cmd_name)
    elif isinstance(exc, RuntimeError | ValueError):
        # Services raise these with user-facing messages.
        err = BridgeError(
            ErrorCode.COMMAND_FAILED, str(exc) or "Operation failed", cmd_name
        )
    else:
        log.error(
            "Unhandled %s in %s:\n%s",
            type(exc).__name__,
            cmd_name,
            "".join(traceback.format_exception(exc)),
        )
        err = BridgeError(
            ErrorCode.BRIDGE_INTERNAL_ERROR,
            f"An unexpected error occurred ({type(exc).__name__}).",
            f"{type(exc).__name__} in '{cmd_name}'",
        )
    return err.to_dict()


def _bridge_command(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a bridge method so failures become structured error responses."""

    @functools.wraps(fn)
    def wrapper(self: Bridge, args: Any = None) -> Any:
        log.debug("%s args=%s", fn.__name__, _sanitize_args(_args(args)))
        try:
            return fn(self, args)
        except Exception as exc:  # noqa: BLE001
            if not isinstance(exc, BridgeError | RuntimeError | ValueError):
                log.warning("%s failed: %s: %s", fn.__name__, type(exc).__name__, exc)
            return error_response(exc, fn.__name__)

    wrapper.__bridge_command__ = True  # type: ignore[attr-defined]
    return wrapper


def _wrap_commands(cls: type) -> type:
    for name, value in list(vars(cls).items()):
        if name.startswith("cmd_") and callable(value):
            setattr(cls, name, _bridge_command(value))
    return cls


@_wrap_commands
class Bridge:
    """JS-facing API surface."""

    # ─────────────────────────── auth / connection ───────────────────────────

    def cmd_connect(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(auth_cmds.cmd_connect(int(a["apiId"]), a.get("apiHash")))

    def cmd_check_connection(self, args: Any = None) -> bool:
        return _run(auth_cmds.cmd_check_connection())

    def cmd_logout(self, args: Any = None) -> bool:
        return _run(auth_cmds.cmd_logout())

    def cmd_auth_request_code(self, args: Any = None) -> str:
        a = _args(args)
        return _run(
            auth_cmds.cmd_auth_request_code(a["phone"], int(a["apiId"]), a["apiHash"])
        )

    def cmd_auth_sign_in(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(auth_cmds.cmd_auth_sign_in(a["code"]))

    def cmd_auth_check_password(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(auth_cmds.cmd_auth_check_password(a["password"]))

    def cmd_auth_qr_login(self, args: Any = None) -> str:
        a = _args(args)
        return _run(auth_cmds.cmd_auth_qr_login(int(a["apiId"]), a["apiHash"]))

    def cmd_auth_qr_poll(self, args: Any = None) -> dict:
        return _run(auth_cmds.cmd_auth_qr_poll())

    # ──────────────────────────────── files ────────────────────────────────

    def cmd_get_files(self, args: Any = None) -> dict:
        a = _args(args)
        return _run_long(
            file_cmds.cmd_get_files(
                _opt_int(a.get("folderId")),
                limit=int(a.get("limit") or file_cmds.DEFAULT_PAGE_SIZE),
                offset_id=int(a.get("offsetId") or 0),
            )
        )

    def cmd_upload_file(self, args: Any = None) -> str:
        a = _args(args)
        return _run_long(
            file_cmds.cmd_upload_file(
                a["path"], _opt_int(a.get("folderId")), a.get("transferId")
            )
        )

    def cmd_download_file(self, args: Any = None) -> str:
        a = _args(args)
        return _run_long(
            file_cmds.cmd_download_file(
                int(a["messageId"]),
                a.get("savePath"),
                _opt_int(a.get("folderId")),
                a.get("transferId"),
                dir_path=a.get("dirPath"),
                file_name=a.get("fileName"),
            )
        )

    def cmd_delete_file(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(
            file_cmds.cmd_delete_file(int(a["messageId"]), _opt_int(a.get("folderId")))
        )

    def cmd_move_files(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(
            file_cmds.cmd_move_files(
                [int(i) for i in a["messageIds"]],
                _opt_int(a.get("sourceFolderId")),
                _opt_int(a.get("targetFolderId")),
            )
        )

    def cmd_search_global(self, args: Any = None) -> list[dict]:
        a = _args(args)
        folder_ids = a.get("folderIds")
        return _run(
            file_cmds.cmd_search_global(
                str(a["query"]),
                [int(i) for i in folder_ids] if folder_ids is not None else None,
            )
        )

    def cmd_cancel_transfer(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(file_cmds.cmd_cancel_transfer(a["transferId"]))

    # ─────────────────────────────── folders ───────────────────────────────

    def cmd_create_folder(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(folder_cmds.cmd_create_folder(a["name"]))

    def cmd_rename_folder(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(folder_cmds.cmd_rename_folder(int(a["folderId"]), str(a["name"])))

    def cmd_delete_folder(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(folder_cmds.cmd_delete_folder(int(a["folderId"])))

    def cmd_scan_folders(self, args: Any = None) -> list[dict]:
        return _run_long(folder_cmds.cmd_scan_folders())

    # ────────────────────────── preview / thumbnails ──────────────────────────

    def cmd_get_preview(self, args: Any = None) -> str:
        a = _args(args)
        return _run_long(
            preview_cmds.cmd_get_preview(
                int(a["messageId"]), _opt_int(a.get("folderId"))
            )
        )

    def cmd_get_thumbnail(self, args: Any = None) -> str:
        a = _args(args)
        return _run_long(
            preview_cmds.cmd_get_thumbnail(
                int(a["messageId"]), _opt_int(a.get("folderId"))
            )
        )

    def cmd_clean_cache(self, args: Any = None) -> bool:
        _run(preview_cmds.cmd_clean_cache())
        return True

    def cmd_get_cache_size(self, args: Any = None) -> int:
        """Return total cache size in bytes."""
        return preview_cmds.cache_size_bytes()

    def cmd_clear_cache(self, args: Any = None) -> None:
        """Delete all cached previews and thumbnails."""
        preview_cmds.clear_cache_dirs()

    # ───────────────────────── network / misc / streaming ─────────────────────────

    def cmd_is_network_available(self, args: Any = None) -> bool:
        return _run(network_cmds.cmd_is_network_available())

    def cmd_get_proxy(self, args: Any = None) -> dict:
        return network_cmds.cmd_get_proxy()

    def cmd_set_proxy(self, args: Any = None) -> bool:
        return _run(network_cmds.cmd_set_proxy(_args(args)))

    def cmd_log(self, args: Any = None) -> None:
        a = _args(args)
        network_cmds.cmd_log(str(a.get("message", "")))

    def cmd_get_bandwidth(self, args: Any = None) -> dict:
        return network_cmds.cmd_get_bandwidth()

    def cmd_get_stream_info(self, args: Any = None) -> dict:
        return network_cmds.cmd_get_stream_info()

    # ─────────────────────── host integration ───────────────────────

    def cmd_dialog_open(self, args: Any = None) -> Any:
        a = _args(args)
        return host_cmds.cmd_dialog_open(
            title=str(a.get("title", "Open")),
            directory=bool(a.get("directory", False)),
            multiple=bool(a.get("multiple", False)),
            filters=a.get("filters"),
            default_path=a.get("defaultPath"),
        )

    def cmd_dialog_save(self, args: Any = None) -> str | None:
        a = _args(args)
        return host_cmds.cmd_dialog_save(
            title=str(a.get("title", "Save")),
            default_path=a.get("defaultPath"),
            filters=a.get("filters"),
        )

    def cmd_shell_open(self, args: Any = None) -> bool:
        a = _args(args)
        return host_cmds.cmd_shell_open(str(a["target"]))

    def cmd_store_get(self, args: Any = None) -> Any:
        a = _args(args)
        return host_cmds.cmd_store_get(str(a["key"]))

    def cmd_store_set(self, args: Any = None) -> bool:
        a = _args(args)
        return host_cmds.cmd_store_set(str(a["key"]), a.get("value"))

    def cmd_store_delete(self, args: Any = None) -> bool:
        a = _args(args)
        return host_cmds.cmd_store_delete(str(a["key"]))

    def cmd_store_entries(self, args: Any = None) -> dict:
        return host_cmds.cmd_store_entries()

    def cmd_relaunch(self, args: Any = None) -> None:
        host_cmds.cmd_relaunch()

    def cmd_window_minimize(self, args: Any = None) -> None:
        host_cmds.cmd_window_minimize()

    def cmd_window_maximize(self, args: Any = None) -> None:
        host_cmds.cmd_window_maximize()

    def cmd_window_restore(self, args: Any = None) -> None:
        host_cmds.cmd_window_restore()

    def cmd_window_close(self, args: Any = None) -> None:
        host_cmds.cmd_window_close()

    def cmd_set_titlebar_dark(self, args: Any = None) -> None:
        a = _args(args)
        host_cmds.cmd_set_titlebar_dark(bool(a.get("dark", True)))

    def cmd_minimize_to_tray(self, args: Any = None) -> None:
        host_cmds.cmd_minimize_to_tray()

    def cmd_notify(self, args: Any = None) -> bool:
        a = _args(args)
        return host_cmds.cmd_notify(
            str(a.get("title", "Telegrab")), str(a.get("message", ""))
        )

    # ─────────────────────── auto-updater ───────────────────────

    def cmd_check_for_updates(self, args: Any = None) -> dict | None:
        return updater_cmds.cmd_check_for_updates()

    def cmd_download_and_install_update(self, args: Any = None) -> None:
        # The URL and checksum are deliberately NOT taken from JS: the updater
        # installs only the release it resolved and verified itself.
        updater_cmds.cmd_download_and_install_update()

    # ─────────────────────── vaults ───────────────────────

    def cmd_create_vault(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(
            vault_cmds.cmd_create_vault(a["name"], a["password"], int(a["folderId"]))
        )

    def cmd_unlock_vault(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(vault_cmds.cmd_unlock_vault(int(a["folderId"]), a["password"]))

    def cmd_lock_vault(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(vault_cmds.cmd_lock_vault(int(a["folderId"])))

    def cmd_list_vaults(self, args: Any = None) -> list:
        return _run(vault_cmds.cmd_list_vaults())

    def cmd_get_vault_status(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(vault_cmds.cmd_get_vault_status(_opt_int(a.get("folderId"))))

    def cmd_delete_vault(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(vault_cmds.cmd_delete_vault(int(a["folderId"])))

    # ─────────────────────── duplicate detection ───────────────────────

    def cmd_check_duplicate(self, args: Any = None) -> dict:
        a = _args(args)
        return _run(
            dedup_cmds.cmd_check_duplicate(a["path"], _opt_int(a.get("folderId")))
        )

    # ─────────────────────── pinned files ───────────────────────

    def cmd_pin_file(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(
            pin_cmds.cmd_pin_file(
                int(a["messageId"]),
                _opt_int(a.get("folderId")),
                a["name"],
                int(a["size"]),
            )
        )

    def cmd_unpin_file(self, args: Any = None) -> bool:
        a = _args(args)
        return _run(
            pin_cmds.cmd_unpin_file(int(a["messageId"]), _opt_int(a.get("folderId")))
        )

    def cmd_get_pinned_files(self, args: Any = None) -> list:
        return _run(pin_cmds.cmd_get_pinned_files())
