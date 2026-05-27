"""pywebview ←→ JS bridge.

Every method on `Bridge` becomes available to JS as
`window.pywebview.api.<method_name>(args)`. The frontend's shim layer
(see `app/src/lib/platform/`) translates `invoke('cmd_x', argsObj)` into
`window.pywebview.api.cmd_x(argsObj)`.

Argument convention
-------------------
Every method accepts a single `args` dict (camelCase keys, mirroring what
Tauri's `invoke` used to send) plus optional positional fallbacks. We
extract individual fields and forward to the async use-case implementations
on the runtime asyncio loop.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from ..infra import get_runtime
from ..infra.logger import _sanitize_args
from ..infra.runtime import DEFAULT_BRIDGE_TIMEOUT
from ..services import (
    auth as auth_cmds,
)
from ..services import (
    files as file_cmds,
)
from ..services import (
    folders as folder_cmds,
)
from ..services import (
    network as network_cmds,
)
from ..services import (
    preview as preview_cmds,
)
from ..services import (
    updater as updater_cmds,
)
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
    return get_runtime().run_coro(coro)


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


class Bridge:
    """JS-facing API surface."""

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
        """Wrap a bridge call with structured error handling.

        1. Validates required fields in *args*, raising a
           :class:`BridgeError` naming every missing field.
        2. Logs the invocation at DEBUG with sanitized args.
        3. Runs *coro* on the runtime loop with *timeout*.
        4. On ConnectionError: attempts auto-reconnect within 10 s, then
           retries the original command once via *coro_factory*.
        5. Maps known exceptions to structured :class:`BridgeError` responses.
        6. Logs unhandled exceptions at ERROR with full traceback; returns
           only the exception type and a generic description to the frontend.

        Parameters
        ----------
        coro_factory : callable, optional
            A zero-argument callable that returns a *new* awaitable for the
            same operation. Used to retry after a successful reconnect.
            If not provided, the command cannot be retried on disconnect.

        Returns
        -------
        Any
            The coroutine's return value on success, or a
            ``BridgeError.to_dict()`` error response on failure.
        """
        # ── 1. Validate required args ──────────────────────────────────────
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

        # ── 2. Log invocation at DEBUG ─────────────────────────────────────
        log.debug("%s args=%s", cmd_name, _sanitize_args(args))

        # ── 3. Execute with error mapping ──────────────────────────────────
        try:
            return get_runtime().run_coro(coro, timeout=timeout)

        except TimeoutError:
            err = BridgeError(
                code=ErrorCode.BRIDGE_TIMEOUT,
                message=f"Operation timed out after {timeout}s. Please try again.",
                detail=f"Command '{cmd_name}' exceeded {timeout}s timeout.",
            )
            return err.to_dict()

        except ConnectionError as exc:
            # ── 4. Attempt auto-reconnect + single retry ───────────────────
            log.warning(
                "ConnectionError in '%s': %s — attempting reconnect",
                cmd_name,
                exc,
            )
            if self._attempt_reconnect():
                # Reconnection succeeded — retry the command once
                if coro_factory is not None:
                    log.info("Reconnected; retrying '%s'", cmd_name)
                    try:
                        return get_runtime().run_coro(coro_factory(), timeout=timeout)
                    except Exception as retry_exc:
                        log.warning(
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
                else:
                    log.info(
                        "Reconnected but no coro_factory for '%s'; cannot retry",
                        cmd_name,
                    )

            # Reconnection failed or no retry possible
            err = BridgeError(
                code=ErrorCode.NETWORK_DISCONNECTED,
                message="Connection lost. Please check your network and try again.",
                detail=f"ConnectionError in '{cmd_name}': {exc}",
            )
            return err.to_dict()

        except Exception as exc:
            # Check for FloodWaitError (Telethon-specific)
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

            # ── Unhandled exception: log full traceback, return safe response ──
            log.error(
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

    # ─────────────────────── reconnection helper ───────────────────────────

    def _attempt_reconnect(self) -> bool:
        """Try to reconnect the Telegram client within 10 seconds.

        Returns True if reconnection succeeded, False otherwise.
        """
        try:
            runtime = get_runtime()
            return runtime.run_coro(
                self._reconnect_client(), timeout=_RECONNECT_TIMEOUT
            )
        except (TimeoutError, Exception) as exc:
            log.warning("Auto-reconnect failed: %s", exc)
            return False

    @staticmethod
    async def _reconnect_client() -> bool:
        """Attempt to reconnect the Telegram client.

        Uses the existing client state (api_id / api_hash) to re-establish
        the connection. Returns True on success, False on failure.
        """
        from ..telegram.client import get_state

        state = get_state()

        # If we have a client instance, try to reconnect it directly
        if state.client is not None:
            try:
                if not state.client.is_connected():
                    await state.client.connect()
                if state.client.is_connected():
                    return True
            except Exception as exc:
                log.warning("Direct client.connect() failed: %s", exc)

        # Fall back to ensure_client which recreates if needed
        if state.api_id is not None and state.api_hash is not None:
            try:
                from ..telegram.client import ensure_client

                client = await ensure_client(state.api_id, state.api_hash)
                return client.is_connected()
            except Exception as exc:
                log.warning("ensure_client reconnect failed: %s", exc)
                return False

        return False

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

    def cmd_get_files(self, args: Any = None) -> list[dict]:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(file_cmds.cmd_get_files(int(fid) if fid is not None else None))

    def cmd_upload_file(self, args: Any = None) -> str:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(
            file_cmds.cmd_upload_file(
                a["path"],
                int(fid) if fid is not None else None,
                a.get("transferId"),
            )
        )

    def cmd_download_file(self, args: Any = None) -> str:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(
            file_cmds.cmd_download_file(
                int(a["messageId"]),
                a["savePath"],
                int(fid) if fid is not None else None,
                a.get("transferId"),
            )
        )

    def cmd_delete_file(self, args: Any = None) -> bool:
        a = _args(args)
        fid = a.get("folderId")
        return _run(
            file_cmds.cmd_delete_file(
                int(a["messageId"]), int(fid) if fid is not None else None
            )
        )

    def cmd_move_files(self, args: Any = None) -> bool:
        a = _args(args)
        src = a.get("sourceFolderId")
        tgt = a.get("targetFolderId")
        return _run(
            file_cmds.cmd_move_files(
                [int(i) for i in a["messageIds"]],
                int(src) if src is not None else None,
                int(tgt) if tgt is not None else None,
            )
        )

    def cmd_search_global(self, args: Any = None) -> list[dict]:
        a = _args(args)
        return _run(file_cmds.cmd_search_global(a["query"]))

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
        return _run(folder_cmds.cmd_scan_folders())

    # ────────────────────────── preview / thumbnails ──────────────────────────

    def cmd_get_preview(self, args: Any = None) -> str:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(
            preview_cmds.cmd_get_preview(
                int(a["messageId"]), int(fid) if fid is not None else None
            )
        )

    def cmd_get_thumbnail(self, args: Any = None) -> str:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(
            preview_cmds.cmd_get_thumbnail(
                int(a["messageId"]), int(fid) if fid is not None else None
            )
        )

    def cmd_clean_cache(self, args: Any = None) -> bool:
        _run(preview_cmds.cmd_clean_cache())
        return True

    # ───────────────────────── network / misc / streaming ─────────────────────────

    def cmd_is_network_available(self, args: Any = None) -> bool:
        return _run(network_cmds.cmd_is_network_available())

    def cmd_log(self, args: Any = None) -> None:
        a = _args(args)
        network_cmds.cmd_log(str(a.get("message", "")))

    def cmd_get_bandwidth(self, args: Any = None) -> dict:
        return network_cmds.cmd_get_bandwidth()

    def cmd_set_bandwidth_limit(self, args: Any = None) -> None:
        """Store the bandwidth limit (MB/s). 0 = unlimited."""
        # Stored in frontend settings; backend reads on-demand if needed.
        pass

    def cmd_get_cache_size(self, args: Any = None) -> int:
        """Return total cache size in bytes."""
        from ..config import preview_cache_dir, thumbnail_cache_dir

        total = 0
        for d in (preview_cache_dir(), thumbnail_cache_dir()):
            if d.exists():
                for f in d.iterdir():
                    if f.is_file():
                        total += f.stat().st_size
        return total

    def cmd_clear_cache(self, args: Any = None) -> None:
        """Delete all cached previews and thumbnails."""
        import shutil

        from ..config import preview_cache_dir, thumbnail_cache_dir

        for d in (preview_cache_dir(), thumbnail_cache_dir()):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                d.mkdir(parents=True, exist_ok=True)

    def cmd_get_stream_info(self, args: Any = None) -> dict:
        return network_cmds.cmd_get_stream_info()

    # ─────────────────────── auto-updater ───────────────────────

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

    # ─────────────────────── auto-updater ───────────────────────

    def cmd_check_for_updates(self, args: Any = None) -> dict | None:
        return updater_cmds.cmd_check_for_updates()

    def cmd_download_and_install_update(self, args: Any = None) -> None:
        a = _args(args)
        url = a["url"]
        sha256 = a.get("sha256", "")
        updater_cmds.cmd_download_and_install_update(url, sha256)

    # ─────────────────────── cached files ───────────────────────

    def cmd_get_files_cached(self, args: Any = None) -> dict:
        a = _args(args)
        fid = a.get("folderId")
        return _run_long(
            file_cmds.cmd_get_files_cached(int(fid) if fid is not None else None)
        )

    # ─────────────────────── tray ───────────────────────

    def cmd_minimize_to_tray(self, args: Any = None) -> None:
        host_cmds.cmd_minimize_to_tray()

    # ─────────────────────── vaults ───────────────────────

    def cmd_create_vault(self, args: Any = None) -> dict:
        from ..services import vault as vault_cmds

        a = _args(args)
        return _run(
            vault_cmds.cmd_create_vault(a["name"], a["password"], int(a["folderId"]))
        )

    def cmd_unlock_vault(self, args: Any = None) -> bool:
        from ..services import vault as vault_cmds

        a = _args(args)
        return _run(vault_cmds.cmd_unlock_vault(int(a["folderId"]), a["password"]))

    def cmd_lock_vault(self, args: Any = None) -> bool:
        from ..services import vault as vault_cmds

        a = _args(args)
        return _run(vault_cmds.cmd_lock_vault(int(a["folderId"])))

    def cmd_list_vaults(self, args: Any = None) -> list:
        from ..services import vault as vault_cmds

        return _run(vault_cmds.cmd_list_vaults())

    def cmd_delete_vault(self, args: Any = None) -> bool:
        from ..services import vault as vault_cmds

        a = _args(args)
        return _run(vault_cmds.cmd_delete_vault(int(a["folderId"])))

    # ─────────────────────── duplicate detection ───────────────────────

    def cmd_check_duplicate(self, args: Any = None) -> dict:
        from ..services import dedup as dedup_cmds

        a = _args(args)
        fid = a.get("folderId")
        return _run(
            dedup_cmds.cmd_check_duplicate(
                a["path"], int(fid) if fid is not None else None
            )
        )

    # ─────────────────────── pinned files ───────────────────────

    def cmd_pin_file(self, args: Any = None) -> bool:
        from ..services import pins as pin_cmds

        a = _args(args)
        fid = a.get("folderId")
        return _run(
            pin_cmds.cmd_pin_file(
                int(a["messageId"]),
                int(fid) if fid is not None else None,
                a["name"],
                int(a["size"]),
            )
        )

    def cmd_unpin_file(self, args: Any = None) -> bool:
        from ..services import pins as pin_cmds

        a = _args(args)
        fid = a.get("folderId")
        return _run(
            pin_cmds.cmd_unpin_file(
                int(a["messageId"]), int(fid) if fid is not None else None
            )
        )

    def cmd_get_pinned_files(self, args: Any = None) -> list:
        from ..services import pins as pin_cmds

        return _run(pin_cmds.cmd_get_pinned_files())
