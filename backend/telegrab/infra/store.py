"""Thread-safe JSON key/value store.

Replaces `@tauri-apps/plugin-store`. The frontend uses it to persist
small amounts of UI state (theme, active folder, API ID/Hash, etc.).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from ..config import store_path

log = logging.getLogger(__name__)


class JsonStore:
    def __init__(self) -> None:
        self._path = store_path()
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def _save_locked(self) -> None:
        # Atomic write: tmp file in same dir, then os.replace.
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".store-", suffix=".tmp", dir=str(self._path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh)
                Path(tmp_path).replace(self._path)
            finally:
                p = Path(tmp_path)
                if p.exists():
                    with contextlib.suppress(OSError):
                        p.unlink()
        except OSError as exc:
            log.warning("Store save failed: %s", exc)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save_locked()

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self._save_locked()

    def entries(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)


_store: JsonStore | None = None


def get_store() -> JsonStore:
    global _store
    if _store is None:
        _store = JsonStore()
    return _store
