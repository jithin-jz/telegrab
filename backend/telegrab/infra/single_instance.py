"""Single-instance enforcement using a Windows named mutex.

On non-Windows platforms, uses a lock file with PID checking.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)

_MUTEX_NAME = "TelegrabSingleInstance_B8F3A2E1"
_mutex_handle = None


def ensure_single_instance() -> bool:
    """Return True if this is the only running instance. Exit otherwise."""
    if sys.platform == "win32":
        return _win32_ensure()
    return _posix_ensure()


def _win32_ensure() -> bool:
    global _mutex_handle
    import ctypes

    kernel32 = ctypes.windll.kernel32
    error_already_exists = 183

    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == error_already_exists:
        log.info("Another instance is already running. Exiting.")
        # Try to bring existing window to front
        _bring_existing_to_front()
        return False

    return True


def _bring_existing_to_front() -> None:
    """Find the existing Telegrab window and bring it to the foreground."""
    import ctypes

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Telegrab")
    if hwnd:
        sw_restore = 9
        user32.ShowWindow(hwnd, sw_restore)
        user32.SetForegroundWindow(hwnd)


def _posix_ensure() -> bool:
    import fcntl
    from pathlib import Path

    lock_path = Path.home() / ".telegrab.lock"
    try:
        lock_file = lock_path.open("w")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(__import__("os").getpid()))
        lock_file.flush()
        # Keep file open for lifetime of process
        _posix_ensure._lock_file = lock_file  # type: ignore[attr-defined]
        return True
    except OSError:
        log.info("Another instance is already running. Exiting.")
        return False
