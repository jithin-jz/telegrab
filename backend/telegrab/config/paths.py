"""App data / cache directory resolution.

Mirrors Tauri's `app.path().app_data_dir()` and `app_cache_dir()` semantics so
existing on-disk artefacts (session, settings, thumbnails) live in a location
that matches the OS conventions per platform.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Identifier — keep stable across versions so the data directory is reused.
APP_NAME = "TelegramDrive"


def app_data_dir() -> Path:
    """Per-user writable data directory.

    Windows : %APPDATA%\\TelegramDrive
    macOS   : ~/Library/Application Support/TelegramDrive
    Linux   : ~/.local/share/TelegramDrive (XDG_DATA_HOME if set)
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")

    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_cache_dir() -> Path:
    """Per-user cache directory (safe to delete)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")

    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_path() -> Path:
    """Telethon session file (SQLite)."""
    return app_data_dir() / "telegram.session"


def bandwidth_path() -> Path:
    return app_data_dir() / "bandwidth.json"


def api_settings_path() -> Path:
    return app_data_dir() / "api_settings.json"


def store_path() -> Path:
    """Replacement for `@tauri-apps/plugin-store`'s `.app_settings.dat`."""
    return app_data_dir() / "store.json"


def preview_cache_dir() -> Path:
    p = app_cache_dir() / "previews"
    p.mkdir(parents=True, exist_ok=True)
    return p


def thumbnail_cache_dir() -> Path:
    p = app_data_dir() / "thumbnails"
    p.mkdir(parents=True, exist_ok=True)
    return p
