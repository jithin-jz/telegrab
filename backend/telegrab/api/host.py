"""Host-integration commands.

Replaces the Tauri plugins the React frontend depends on:

  cmd_dialog_open            — `@tauri-apps/plugin-dialog` open()
  cmd_dialog_save            — `@tauri-apps/plugin-dialog` save()
  cmd_shell_open             — `@tauri-apps/plugin-shell` open()
  cmd_store_get/set/...      — `@tauri-apps/plugin-store` Store
  cmd_relaunch               — `@tauri-apps/plugin-process` relaunch()
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

import webview

from ..infra import bus, get_store

log = logging.getLogger(__name__)

# Window reference is set by app.main() once the pywebview window exists.
_window: webview.Window | None = None


# ───────────────── Win32 maximize / taskbar handling ─────────────────
#
# pywebview creates a `frameless=True` window. When such a window is
# maximized via the OS (ShowWindow(SW_MAXIMIZE) / Form.WindowState =
# Maximized), Windows uses the *full monitor* rectangle, so the window
# covers the taskbar.
#
# Fix: bypass the OS maximize entirely. When the user clicks our custom
# maximize button we manually size the window to the monitor's work
# area (rcWork) — that's the rectangle that explicitly excludes the
# taskbar. On restore we put the window back where it was.

_GWL_STYLE = -16
_MONITOR_DEFAULTTONEAREST = 2

# Style bits we want re-enabled on the frameless window so the OS draws
# a resize border and the taskbar treats us like a normal app.
_WS_THICKFRAME = 0x00040000
_WS_SYSMENU = 0x00080000
_WS_MAXIMIZEBOX = 0x00010000
_WS_MINIMIZEBOX = 0x00020000

# SetWindowPos flags
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001

# ShowWindow commands
_SW_RESTORE = 9
_SW_MINIMIZE = 6


# Tracks whether we've manually maximized the window, plus the rect to
# restore to. We can't rely on the OS WindowState because we deliberately
# never transition it to Maximized — we just resize the window ourselves.
_max_state: dict[str, Any] = {"maximized": False, "saved_rect": None}


def _configure_user32() -> None:
    """Set ctypes argtypes/restypes for handle-returning APIs so they
    aren't truncated to 32 bits on 64-bit Python."""
    user32 = ctypes.windll.user32
    user32.MonitorFromWindow.restype = ctypes.c_void_p
    user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetMonitorInfoW.restype = ctypes.c_int
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    user32.SetWindowPos.restype = ctypes.c_int
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.ShowWindow.restype = ctypes.c_int
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.GetWindowRect.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.IsIconic.restype = ctypes.c_int
    user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.IsZoomed.restype = ctypes.c_int
    user32.IsZoomed.argtypes = [ctypes.c_void_p]


_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        _configure_user32()
        _configured = True


def attach_window(window: webview.Window) -> None:
    global _window
    _window = window

    if sys.platform == "win32":
        threading.Thread(target=_apply_native_styles, daemon=True).start()


def _apply_native_styles() -> None:
    """Re-add resize / sysmenu style bits on the frameless window."""
    time.sleep(0.5)
    try:
        _ensure_configured()
        user32 = ctypes.windll.user32
        hwnd = getattr(_window, 'hwnd', None)
        if not hwnd:
            hwnd = user32.FindWindowW(None, "Telegrab")
        if not hwnd:
            log.warning("Telegrab window not found; skipping native styles.")
            return

        style = user32.GetWindowLongW(hwnd, _GWL_STYLE)
        style |= _WS_THICKFRAME | _WS_SYSMENU | _WS_MAXIMIZEBOX | _WS_MINIMIZEBOX
        user32.SetWindowLongW(hwnd, _GWL_STYLE, style)

        # Force the OS to re-evaluate the non-client area.
        user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            _SWP_FRAMECHANGED | _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to apply native styles: %s", exc)


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
    if multiple or directory:
        return list(result) if multiple else result[0]
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
    return any(
        resolved == safe_dir or str(resolved).startswith(str(safe_dir) + os.sep)
        for safe_dir in safe_dirs
    )


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


def cmd_window_minimize() -> None:
    log.info("Minimizing window...")
    if not _window:
        return

    if sys.platform == "win32":
        try:
            _ensure_configured()
            # Use pywebview's native handle if available, fall back to FindWindowW
            hwnd = getattr(_window, 'hwnd', None)
            if not hwnd:
                hwnd = ctypes.windll.user32.FindWindowW(None, "Telegrab")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, _SW_MINIMIZE)
                return
        except Exception as exc:  # noqa: BLE001
            log.warning("Native minimize failed: %s", exc)

    _window.minimize()


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


def _get_work_area(hwnd: int) -> RECT | None:
    """Return the work area (excludes taskbar) of the monitor the window
    is on, or None on failure."""
    user32 = ctypes.windll.user32
    try:
        hmon = user32.MonitorFromWindow(hwnd, _MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return mi.rcWork
    except Exception as exc:  # noqa: BLE001
        log.warning("GetMonitorInfo failed: %s", exc)
    return None


def cmd_window_maximize() -> None:
    """Pseudo-maximize: resize the window to the monitor's work area
    (which excludes the taskbar) instead of letting the OS maximize it.

    A genuine OS maximize on a frameless window covers the taskbar; this
    approach lets the taskbar show through underneath, matching the
    behaviour of native apps like Chrome/Edge/ChatGPT desktop.
    """
    log.info("Maximizing window...")
    if not _window:
        return

    if sys.platform == "darwin":
        # macOS: pywebview's maximize works correctly with the dock
        _window.maximize()
        bus.emit("window-maximized", True)
        return

    if sys.platform == "win32":
        try:
            _ensure_configured()
            user32 = ctypes.windll.user32
            hwnd = getattr(_window, 'hwnd', None)
            if not hwnd:
                hwnd = user32.FindWindowW(None, "Telegrab")
            if hwnd:
                # If the OS thinks we're minimized/maximized, normalise first
                # so SetWindowPos lands us in the right place.
                if user32.IsIconic(hwnd) or user32.IsZoomed(hwnd):
                    user32.ShowWindow(hwnd, _SW_RESTORE)

                # Snapshot the current bounds so cmd_window_restore can
                # put the window back where the user had it.
                if not _max_state["maximized"]:
                    rect = RECT()
                    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                        _max_state["saved_rect"] = (
                            rect.left,
                            rect.top,
                            rect.right - rect.left,
                            rect.bottom - rect.top,
                        )

                work = _get_work_area(hwnd)
                if work is not None:
                    user32.SetWindowPos(
                        hwnd,
                        0,
                        work.left,
                        work.top,
                        work.right - work.left,
                        work.bottom - work.top,
                        _SWP_NOZORDER,
                    )
                    _max_state["maximized"] = True
                    bus.emit("window-maximized", True)
                    return
        except Exception as exc:  # noqa: BLE001
            log.warning("Native maximize failed: %s", exc)

    # Fallback: pywebview's own maximize. Won't respect the taskbar on
    # frameless windows, but better than nothing.
    _window.maximize()
    bus.emit("window-maximized", True)


def cmd_window_restore() -> None:
    """Restore from a manual-maximize back to the previous bounds."""
    log.info("Restoring window...")
    if not _window:
        return

    if sys.platform == "darwin":
        _window.restore()
        bus.emit("window-maximized", False)
        return

    if sys.platform == "win32":
        try:
            _ensure_configured()
            user32 = ctypes.windll.user32
            hwnd = getattr(_window, 'hwnd', None)
            if not hwnd:
                hwnd = user32.FindWindowW(None, "Telegrab")
            if hwnd:
                if _max_state["maximized"] and _max_state["saved_rect"]:
                    x, y, w, h = _max_state["saved_rect"]
                    user32.SetWindowPos(hwnd, 0, x, y, w, h, _SWP_NOZORDER)
                    _max_state["maximized"] = False
                    bus.emit("window-maximized", False)
                    return

                # Not in our manual-maximize state — defer to the OS.
                user32.ShowWindow(hwnd, _SW_RESTORE)
                _max_state["maximized"] = False
                bus.emit("window-maximized", False)
                return
        except Exception as exc:  # noqa: BLE001
            log.warning("Native restore failed: %s", exc)

    _window.restore()
    bus.emit("window-maximized", False)


def cmd_window_close() -> None:
    if _window:
        _window.destroy()


def cmd_minimize_to_tray() -> None:
    if _window:
        _window.hide()


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
    "cmd_window_minimize",
    "cmd_window_maximize",
    "cmd_window_restore",
    "cmd_window_close",
    "cmd_minimize_to_tray",
]
