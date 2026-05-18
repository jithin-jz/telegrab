"""Thread-safe JSON key/value store.

Replaces `@tauri-apps/plugin-store`. The frontend uses it to persist
small amounts of UI state (theme, active folder, API ID/Hash, etc.).

Sensitive keys (api_id, api_hash) are encrypted at rest using Windows DPAPI
(or base64 on non-Windows as a placeholder until keyring integration).
File permissions are restricted to the current user.
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from ..config import store_path

log = logging.getLogger(__name__)

# Keys that should be encrypted at rest
_SENSITIVE_KEYS = {"api_id", "api_hash", "apiId", "apiHash"}


def _encrypt(data: bytes) -> str:
    """Encrypt bytes using OS-level protection. Returns base64 string."""
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            class _DataBlob(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            input_blob = _DataBlob(len(data), ctypes.create_string_buffer(data, len(data)))
            output_blob = _DataBlob()
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(input_blob), None, None, None, None, 0,
                ctypes.byref(output_blob),
            ):
                encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
                ctypes.windll.kernel32.LocalFree(output_blob.pbData)
                return base64.b64encode(encrypted).decode("ascii")
        except Exception:
            pass
    # Fallback: base64 (not secure, but better than plaintext for casual inspection)
    return base64.b64encode(data).decode("ascii")


def _decrypt(encoded: str) -> bytes:
    """Decrypt a string produced by _encrypt."""
    raw = base64.b64decode(encoded)
    if sys.platform == "win32":
        try:
            import ctypes
            import ctypes.wintypes

            class _DataBlob(ctypes.Structure):
                _fields_ = [
                    ("cbData", ctypes.wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            input_blob = _DataBlob(len(raw), ctypes.create_string_buffer(raw, len(raw)))
            output_blob = _DataBlob()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None, 0,
                ctypes.byref(output_blob),
            ):
                decrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
                ctypes.windll.kernel32.LocalFree(output_blob.pbData)
                return decrypted
        except Exception:
            pass
    # Fallback: raw is the plaintext
    return raw


def _restrict_permissions(path: Path) -> None:
    """Restrict file to current user only."""
    if sys.platform == "win32":
        try:
            import subprocess
            username = os.environ.get("USERNAME", "")
            if username:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r",
                     "/grant:r", f"{username}:(R,W)"],
                    capture_output=True, check=False,
                    startupinfo=si,
                )
        except Exception:
            pass
    else:
        with contextlib.suppress(OSError):
            path.chmod(0o600)


class JsonStore:
    def __init__(self) -> None:
        self._path = store_path()
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._load()
        _restrict_permissions(self._path)

    def _load(self) -> None:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            # Decrypt sensitive keys
            self._data = {}
            for k, v in raw.items():
                if k in _SENSITIVE_KEYS and isinstance(v, str) and v.startswith("ENC:"):
                    try:
                        self._data[k] = json.loads(_decrypt(v[4:]).decode("utf-8"))
                    except Exception:
                        self._data[k] = v  # keep as-is if decryption fails
                else:
                    self._data[k] = v
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}

    def _save_locked(self) -> None:
        # Build serializable dict with sensitive keys encrypted
        out: dict[str, Any] = {}
        for k, v in self._data.items():
            if k in _SENSITIVE_KEYS:
                payload = json.dumps(v).encode("utf-8")
                out[k] = "ENC:" + _encrypt(payload)
            else:
                out[k] = v

        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".store-", suffix=".tmp", dir=str(self._path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(out, fh)
                Path(tmp_path).replace(self._path)
                _restrict_permissions(self._path)
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
