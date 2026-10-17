"""Host-integration commands: dialogs, shell, key/value store, process and
window control.

  cmd_dialog_open / cmd_dialog_save  — native file dialogs
  cmd_shell_open                     — open a URL or file with the OS
  cmd_store_get/set/...              — persistent UI state (see infra.store)
  cmd_relaunch                       — restart the app
  cmd_window_* / titlebar / tray     — window management
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

import webview

from ..infra import get_store

log = logging.getLogger(__name__)

# Window reference is set by app.main() once the pywebview window exists.
_window: webview.Window | None = None

WINDOW_TITLE = "Telegrab"

# SetWindowPos flags
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001

# ShowWindow commands
_SW_MINIMIZE = 6


def attach_window(window: webview.Window) -> None:
    global _window
    _window = window


# ───────────────────────────── window handle ─────────────────────────────


def find_app_window(pid: int | None = None) -> int | None:
    """Find a top-level Telegrab window, optionally owned by `pid`.

    Matching on the title alone is not enough — an Explorer window on a
    folder called "Telegrab" has the same title — so the window class must
    be the WinForms class pywebview creates.
    """
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd: int, _lparam: int) -> bool:
        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        if title.value != WINDOW_TITLE:
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        if not cls.value.startswith("WindowsForms10"):
            return True
        if pid is not None:
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value != pid:
                return True
        found.append(hwnd)
        return False

    user32.EnumWindows(enum_proc(_callback), 0)
    return found[0] if found else None


def _get_hwnd() -> int | None:
    """Native handle of our own window (Windows only)."""
    if sys.platform != "win32" or _window is None:
        return None
    native = getattr(_window, "native", None)
    if native is not None:
        try:
            return int(native.Handle.ToInt64())
        except Exception:  # noqa: BLE001
            pass
    return find_app_window(os.getpid())


# ─────────────────────────────── dialogs ───────────────────────────────


def cmd_dialog_open(
    title: str = "Open",
    directory: bool = False,
    multiple: bool = False,
    filters: list[dict] | None = None,
    default_path: str | None = None,
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
    if multiple:
        return list(result)
    return result[0]


def cmd_dialog_save(
    title: str = "Save",
    default_path: str | None = None,
    filters: list[dict] | None = None,
) -> str | None:
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
    if isinstance(result, list | tuple):
        return result[0] if result else None
    return result


def _convert_filters(filters: list[dict] | None) -> tuple[str, ...]:
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

_SAFE_SCHEMES = ("http://", "https://", "mailto:", "tel:", "tg://")


def _is_safe_path(target: str) -> bool:
    """Only allow opening paths inside the app cache dir or user Downloads."""
    from ..config import app_cache_dir, app_data_dir

    try:
        resolved = Path(target).resolve()
    except (OSError, ValueError):
        return False

    safe_dirs = [
        app_cache_dir().resolve(),
        app_data_dir().resolve(),
        (Path.home() / "Downloads").resolve(),
    ]
    return any(resolved == d or resolved.is_relative_to(d) for d in safe_dirs)


def cmd_shell_open(target: str) -> bool:
    """Open a URL or file path with the default OS handler.

    Restricted to safe URL schemes and paths within app cache / Downloads.
    """
    try:
        if any(target.startswith(s) for s in _SAFE_SCHEMES):
            webbrowser.open(target, new=2)
            return True

        # File path: only allow safe locations
        if not _is_safe_path(target):
            log.warning("shell_open blocked unsafe path: %s", target)
            return False

        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
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

# Set on the child process so it waits for us to exit instead of treating
# us as "another instance already running".
RELAUNCH_ENV = "TELEGRAB_RELAUNCHED"


def _relaunch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *sys.argv[1:]]
    return [sys.executable, "-m", "telegrab", *sys.argv[1:]]


def cmd_relaunch() -> None:
    """Start a fresh instance, then close this one."""
    try:
        env = dict(os.environ, **{RELAUNCH_ENV: str(os.getpid())})
        subprocess.Popen(_relaunch_command(), env=env, close_fds=True)
    except Exception as exc:  # noqa: BLE001
        log.error("Relaunch failed: %s", exc)
        return
    threading.Timer(0.25, cmd_window_close).start()


def cmd_window_minimize() -> None:
    if not _window:
        return
    hwnd = _get_hwnd()
    if hwnd:
        # The native call works even before the WebView has finished loading,
        # which is when "start minimised" fires.
        ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), _SW_MINIMIZE)
        return
    _window.minimize()


def cmd_window_maximize() -> None:
    if _window:
        _window.maximize()


def cmd_window_restore() -> None:
    if _window:
        _window.restore()


def cmd_window_close() -> None:
    if _window:
        _window.destroy()


def cmd_set_titlebar_dark(dark: bool) -> None:
    """Set the native Windows title bar to dark or light to match the app theme."""
    if sys.platform != "win32" or not _window:
        return
    try:
        hwnd = _get_hwnd()
        if not hwnd:
            return
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        dwm.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        value = ctypes.c_int(1 if dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (19 on older Win10 builds)
        for attr in (20, 19):
            dwm(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
        # Force the title bar to repaint immediately.
        set_pos = ctypes.windll.user32.SetWindowPos
        set_pos.argtypes = (
            [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
        )
        set_pos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            _SWP_FRAMECHANGED | _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Set titlebar theme failed: %s", exc)


def cmd_minimize_to_tray() -> None:
    if _window:
        _window.hide()


def cmd_notify(title: str, message: str) -> bool:
    """Show a native notification (via the tray icon). Returns False if unavailable."""
    from ..services.tray import notify

    return notify(title, message)


__all__ = [
    "attach_window",
    "find_app_window",
    "cmd_dialog_open",
    "cmd_dialog_save",
    "cmd_shell_open",
    "cmd_store_get",
    "cmd_store_set",
    "cmd_store_delete",
    "cmd_store_entries",
    "cmd_relaunch",
    "cmd_window_minimize",
    "cmd_window_maximize",
    "cmd_window_restore",
    "cmd_window_close",
    "cmd_set_titlebar_dark",
    "cmd_minimize_to_tray",
    "cmd_notify",
    "RELAUNCH_ENV",
]
