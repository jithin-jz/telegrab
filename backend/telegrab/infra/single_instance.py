"""Single-instance enforcement.

Windows uses a named mutex; other platforms use an exclusive lock file.
When the app relaunches itself the new process is started with
``TELEGRAB_RELAUNCHED`` set and waits (up to `_RELAUNCH_WAIT_SECS`) for the
old instance to exit instead of bailing out immediately.
"""

from __future__ import annotations

import logging
import os
import sys
import time

log = logging.getLogger(__name__)

_MUTEX_NAME = "TelegrabSingleInstance_B8F3A2E1"
_RELAUNCH_ENV = "TELEGRAB_RELAUNCHED"
_RELAUNCH_WAIT_SECS = 15.0
_mutex_handle = None


def ensure_single_instance() -> bool:
    """Return True if this is the only running instance."""
    deadline = time.monotonic() + (
        _RELAUNCH_WAIT_SECS if os.environ.pop(_RELAUNCH_ENV, None) else 0.0
    )
    acquire = _win32_acquire if sys.platform == "win32" else _posix_acquire
    while True:
        if acquire():
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)

    log.info("Another instance is already running. Exiting.")
    _bring_existing_to_front()
    return False


def _win32_acquire() -> bool:
    global _mutex_handle
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    error_already_exists = 183

    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == error_already_exists:
        if handle:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        return False
    _mutex_handle = handle
    return True


def _bring_existing_to_front() -> None:
    """Find the existing Telegrab window and bring it to the foreground."""
    if sys.platform != "win32":
        return
    import ctypes

    from ..api.host import find_app_window

    hwnd = find_app_window()
    if hwnd:
        user32 = ctypes.windll.user32
        sw_show, sw_restore = 5, 9
        user32.ShowWindow(ctypes.c_void_p(hwnd), sw_show)  # in case it's in the tray
        user32.ShowWindow(ctypes.c_void_p(hwnd), sw_restore)
        user32.SetForegroundWindow(ctypes.c_void_p(hwnd))


def _posix_acquire() -> bool:
    import fcntl

    from ..config import app_data_dir

    lock_path = app_data_dir() / "instance.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return False
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    # Keep file open for lifetime of process
    _posix_acquire._lock_file = lock_file  # type: ignore[attr-defined]
    return True
