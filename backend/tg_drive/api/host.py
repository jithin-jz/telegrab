"""Host-integration commands.

Replaces the Tauri plugins the React frontend depends on:

  cmd_dialog_open            — `@tauri-apps/plugin-dialog` open()
  cmd_dialog_save            — `@tauri-apps/plugin-dialog` save()
  cmd_shell_open             — `@tauri-apps/plugin-shell` open()
  cmd_store_get/set/...      — `@tauri-apps/plugin-store` Store
  cmd_relaunch               — `@tauri-apps/plugin-process` relaunch()
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from typing import Any, Optional

import webview

from ..infra import get_store

log = logging.getLogger(__name__)

# Window reference is set by app.main() once the pywebview window exists.
_window: Optional["webview.Window"] = None


def attach_window(window: "webview.Window") -> None:
    global _window
    _window = window


# ─────────────────────────────── dialogs ───────────────────────────────


def cmd_dialog_open(
    title: str = "Open",
    directory: bool = False,
    multiple: bool = False,
    filters: Optional[list[dict]] = None,
    default_path: Optional[str] = None,
) -> Any:
    if _window is None:
        return None

    dialog_type = webview.FOLDER_DIALOG if directory else webview.OPEN_DIALOG

    file_types = _convert_filters(filters)
    result = _window.create_file_dialog(
        dialog_type,
        directory=default_path or "",
        allow_multiple=multiple,
        file_types=file_types,
    )

    if not result:
        return None
    if multiple or directory:
        return list(result) if multiple else result[0]
    return result[0]


def cmd_dialog_save(
    title: str = "Save",
    default_path: Optional[str] = None,
    filters: Optional[list[dict]] = None,
) -> Optional[str]:
    if _window is None:
        return None
    file_types = _convert_filters(filters)
    save_dir = ""
    save_filename = ""
    if default_path:
        save_dir, save_filename = os.path.split(default_path)
    result = _window.create_file_dialog(
        webview.SAVE_DIALOG,
        directory=save_dir,
        save_filename=save_filename,
        file_types=file_types,
    )
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        return result[0] if result else None
    return result


def _convert_filters(filters: Optional[list[dict]]) -> tuple[str, ...]:
    if not filters:
        return ()
    out: list[str] = []
    for f in filters:
        name = f.get("name") or "Files"
        exts = f.get("extensions") or []
        if not exts:
            continue
        glob = ";".join(f"*.{e.lstrip('.')}" for e in exts)
        out.append(f"{name} ({glob})")
    return tuple(out)


# ──────────────────────────────── shell ────────────────────────────────


def cmd_shell_open(target: str) -> bool:
    """Open a URL or file path with the default OS handler."""
    try:
        if target.startswith(("http://", "https://", "mailto:", "tel:", "tg://")):
            webbrowser.open(target, new=2)
            return True
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", target])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", target])
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("shell open failed: %s", exc)
        return False


# ──────────────────────────────── store ────────────────────────────────


def cmd_store_get(key: str) -> Any:
    return get_store().get(key)


def cmd_store_set(key: str, value: Any) -> bool:
    get_store().set(key, value)
    return True


def cmd_store_delete(key: str) -> bool:
    get_store().delete(key)
    return True


def cmd_store_entries() -> dict:
    return get_store().entries()


# ───────────────────────────── process / app ─────────────────────────────


def cmd_relaunch() -> None:
    def _do() -> None:
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:  # noqa: BLE001
            log.error("Relaunch failed: %s", exc)

    threading.Timer(0.25, _do).start()


__all__ = [
    "attach_window",
    "cmd_dialog_open",
    "cmd_dialog_save",
    "cmd_shell_open",
    "cmd_store_get",
    "cmd_store_set",
    "cmd_store_delete",
    "cmd_store_entries",
    "cmd_relaunch",
]
