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
import time
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

            input_blob = _DataBlob(
                len(data), ctypes.create_string_buffer(data, len(data))
            )
            output_blob = _DataBlob()
            if ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(input_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(output_blob),
            ):
                encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
                ctypes.windll.kernel32.LocalFree(output_blob.pbData)
                return base64.b64encode(encrypted).decode("ascii")
            # CryptProtectData returned False — DPAPI failed
            log.warning(
                "DPAPI encryption failed (CryptProtectData returned False); "
                "falling back to base64 encoding — full encryption is unavailable"
            )
        except Exception as exc:
            log.warning(
                "DPAPI encryption unavailable (%s); "
                "falling back to base64 encoding — full encryption is unavailable",
                exc,
            )
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
                ctypes.byref(input_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(output_blob),
            ):
                decrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
                ctypes.windll.kernel32.LocalFree(output_blob.pbData)
                return decrypted
        except Exception:
            pass
    # Fallback: raw is the plaintext
    return raw


_permissions_set = False


def _restrict_permissions(path: Path) -> None:
    """Restrict file to current user only."""
    global _permissions_set
    if _permissions_set:
        return
    if sys.platform == "win32":
        try:
            import subprocess

            username = os.environ.get("USERNAME", "")
            if username:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(
                    [
                        "icacls",
                        str(path),
                        "/inheritance:r",
                        "/grant:r",
                        f"{username}:(R,W)",
                    ],
                    capture_output=True,
                    check=False,
                    startupinfo=si,
                )
        except Exception:
            pass
    else:
        with contextlib.suppress(OSError):
            path.chmod(0o600)
    _permissions_set = True


def _validate_permissions(path: Path) -> None:
    """Validate store file permissions on startup and attempt correction if wrong.

    On Unix: checks that file mode is 0o600 (owner read/write only).
    On Windows: runs ``icacls`` to inspect the ACL and logs a warning if the
    output does not indicate single-user access. Attempts correction via
    ``_restrict_permissions``.
    """
    if not path.exists():
        return

    if sys.platform == "win32":
        try:
            import subprocess

            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(
                ["icacls", str(path)],
                capture_output=True,
                text=True,
                check=False,
                startupinfo=si,
            )
            output = result.stdout.strip()
            os.environ.get("USERNAME", "")
            # Heuristic: if output contains entries beyond the current user
            # (e.g. BUILTIN\Users, Everyone, Authenticated Users) the file is
            # too permissive.
            permissive_indicators = [
                "Everyone",
                "BUILTIN\\Users",
                "Authenticated Users",
                "Users",
            ]
            is_permissive = any(
                indicator in output for indicator in permissive_indicators
            )
            if is_permissive:
                log.warning(
                    "Store file permissions are too permissive; "
                    "attempting to restrict to current user only"
                )
                # Reset flag to allow correction
                global _permissions_set
                _permissions_set = False
                _restrict_permissions(path)
        except Exception as exc:
            log.warning("Unable to validate store file permissions on Windows: %s", exc)
    else:
        # Unix: check file mode
        try:
            mode = path.stat().st_mode & 0o777
            if mode != 0o600:
                log.warning(
                    "Store file permissions are %04o (expected 0600); "
                    "attempting to correct",
                    mode,
                )
                try:
                    path.chmod(0o600)
                    log.info("Store file permissions corrected to 0600")
                except OSError as exc:
                    log.warning("Failed to correct store file permissions: %s", exc)
        except OSError as exc:
            log.warning("Unable to validate store file permissions: %s", exc)


class JsonStore:
    def __init__(self) -> None:
        self._path = store_path()
        self._lock = threading.Lock()
        self._timer_lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._save_timer: threading.Timer | None = None
        self._load()
        _restrict_permissions(self._path)
        _validate_permissions(self._path)

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
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            # Store file contains invalid JSON or unreadable content — quarantine and start fresh
            self._quarantine_corrupt_file()
            self._data = {}
        except FileNotFoundError:
            self._data = {}
        except OSError:
            self._data = {}

    def _quarantine_corrupt_file(self) -> None:
        """Rename a corrupted store file with a .corrupt.<timestamp> suffix."""
        try:
            if self._path.exists():
                timestamp = int(time.time())
                corrupt_name = f"{self._path.name}.corrupt.{timestamp}"
                corrupt_path = self._path.parent / corrupt_name
                self._path.rename(corrupt_path)
                log.warning(
                    "Store file corrupted, renamed to %s and reinitialized",
                    corrupt_name,
                )
        except OSError as exc:
            log.warning("Failed to quarantine corrupt store file: %s", exc)

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

    def _schedule_save(self) -> None:
        """Debounce: schedule a save 0.5s from now, cancelling any pending timer."""
        with self._timer_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(0.5, self._debounced_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _debounced_save(self) -> None:
        with self._lock:
            self._save_locked()

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
        self._schedule_save()

    def delete(self, key: str) -> None:
        changed = False
        with self._lock:
            if key in self._data:
                del self._data[key]
                changed = True
        if changed:
            self._schedule_save()

    def entries(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)


_store: JsonStore | None = None


def get_store() -> JsonStore:
    global _store
    if _store is None:
        _store = JsonStore()
    return _store
