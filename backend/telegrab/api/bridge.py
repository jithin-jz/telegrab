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
from typing import Any

from ..infra import get_runtime
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

log = logging.getLogger(__name__)


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
        return _run_long(
            file_cmds.cmd_get_files(int(fid) if fid is not None else None)
        )

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
        return _run(
            folder_cmds.cmd_rename_folder(int(a["folderId"]), str(a["name"]))
        )

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
        return _run(vault_cmds.cmd_create_vault(a["name"], a["password"], int(a["folderId"])))

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
        return _run(dedup_cmds.cmd_check_duplicate(a["path"], int(fid) if fid is not None else None))

    # ─────────────────────── pinned files ───────────────────────

    def cmd_pin_file(self, args: Any = None) -> bool:
        from ..services import pins as pin_cmds
        a = _args(args)
        fid = a.get("folderId")
        return _run(pin_cmds.cmd_pin_file(int(a["messageId"]), int(fid) if fid is not None else None, a["name"], int(a["size"])))

    def cmd_unpin_file(self, args: Any = None) -> bool:
        from ..services import pins as pin_cmds
        a = _args(args)
        fid = a.get("folderId")
        return _run(pin_cmds.cmd_unpin_file(int(a["messageId"]), int(fid) if fid is not None else None))

    def cmd_get_pinned_files(self, args: Any = None) -> list:
        from ..services import pins as pin_cmds
        return _run(pin_cmds.cmd_get_pinned_files())
