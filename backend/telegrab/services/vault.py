"""Encrypted Vaults — AES-256-GCM client-side encryption.

Files are encrypted before upload and decrypted after download.
The master password derives a key via PBKDF2. Telegram never sees plaintext.
Vault metadata (salt, folder_id) is stored locally in the SQLite cache.
"""

from __future__ import annotations

import atexit
import ctypes
import hashlib
import logging
import os
import secrets
import sqlite3
import struct
import tempfile
import threading
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from ..api.errors import BridgeError, ErrorCode
from ..config import app_data_dir

log = logging.getLogger(__name__)

_VAULT_DB: sqlite3.Connection | None = None
_PBKDF2_ITERATIONS = 600_000
_HEADER_MAGIC = b"TGVAULT1"  # 8 bytes magic header
_CHUNKED_MAGIC = b"TGVLTCHK"  # 8 bytes magic for chunked format
_CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks for large files

# Flag indicating vault DB integrity status. Set to False if integrity check fails.
_vault_db_healthy: bool = True

_vault_db_lock = threading.Lock()


def _check_db_integrity() -> bool:
    """Run PRAGMA integrity_check on the vault database.

    Returns True if the database passes integrity check, False otherwise.
    Sets the global _vault_db_healthy flag accordingly.
    """
    global _vault_db_healthy
    try:
        if _VAULT_DB is None:
            _vault_db_healthy = False
            return False
        result = _VAULT_DB.execute("PRAGMA integrity_check").fetchone()
        if result and result[0] == "ok":
            _vault_db_healthy = True
            log.debug("Vault database integrity check passed")
            return True
        _vault_db_healthy = False
        detail = str(result[0]) if result else "unknown error"
        log.error("Vault database integrity check failed: %s", detail)
        return False
    except Exception as exc:
        _vault_db_healthy = False
        log.error("Vault database integrity check error: %s", exc)
        return False


def _require_healthy_db() -> None:
    """Raise an error if the vault database failed integrity check."""
    if not _vault_db_healthy:
        raise BridgeError(
            code=ErrorCode.VAULT_DB_CORRUPT,
            message="Vault database is corrupted. Please re-initialize the vault.",
            detail="SQLite integrity_check failed on startup. Vault operations are disabled until re-initialization.",
        )


def _get_vault_db() -> sqlite3.Connection:
    global _VAULT_DB, _vault_db_healthy
    with _vault_db_lock:
        if _VAULT_DB is None:
            path = app_data_dir() / "vaults.db"
            try:
                _VAULT_DB = sqlite3.connect(str(path), check_same_thread=False)
            except Exception as exc:
                _vault_db_healthy = False
                log.error("Failed to open vault database: %s", exc)
                raise BridgeError(
                    code=ErrorCode.VAULT_DB_CORRUPT,
                    message="Vault database cannot be opened. Please re-initialize the vault.",
                    detail=f"Failed to open vault database at {path}: {exc}",
                ) from exc
            _VAULT_DB.row_factory = sqlite3.Row
            try:
                _VAULT_DB.executescript("""
                    CREATE TABLE IF NOT EXISTS vaults (
                        folder_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        salt BLOB NOT NULL,
                        key_check BLOB NOT NULL,
                        created_at REAL NOT NULL
                    );
                """)
                _VAULT_DB.commit()
            except Exception as exc:
                _vault_db_healthy = False
                _VAULT_DB = None
                log.error("Vault database schema creation failed: %s", exc)
                raise BridgeError(
                    code=ErrorCode.VAULT_DB_CORRUPT,
                    message="Vault database is corrupted. Please re-initialize the vault.",
                    detail=f"Failed to initialize vault database schema at {path}: {exc}",
                ) from exc
            # Run integrity check on first initialization
            _check_db_integrity()
    return _VAULT_DB


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password + salt using PBKDF2-SHA256."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )


def _encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Encrypt data with AES-256-GCM. Returns: magic + nonce(12) + tag(16) + ciphertext."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, data, None)
    # ct includes the 16-byte tag appended by cryptography lib
    return _HEADER_MAGIC + nonce + ct


def _decrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Decrypt data encrypted by _encrypt_bytes."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not data.startswith(_HEADER_MAGIC):
        raise ValueError("Not a vault-encrypted file")
    payload = data[len(_HEADER_MAGIC) :]
    nonce = payload[:12]
    ct = payload[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ─────────────────────── Session key store ───────────────────────
# Unlocked vault keys are held in memory only for the session.
_session_keys: dict[int, bytearray] = {}

# ─────────────────────── Key zeroization ───────────────────────


def _zeroize_key(key: bytearray | bytes) -> None:
    """Overwrite key bytes with zeros in memory using ctypes.memset."""
    if not key:
        return
    if isinstance(key, bytearray):
        buf = (ctypes.c_char * len(key)).from_buffer(key)
        ctypes.memset(buf, 0, len(key))
    else:
        # For immutable bytes, we can't zero in place but attempt via mutable copy
        # This case shouldn't occur since we store bytearray, but handle defensively
        pass


def _zeroize_all_keys() -> None:
    """Zeroize all held vault session keys. Called on shutdown."""
    for folder_id in list(_session_keys.keys()):
        key = _session_keys.pop(folder_id, None)
        if key is not None:
            _zeroize_key(key)
    log.debug("All vault session keys zeroized on shutdown")


# Register the atexit handler to zeroize keys on application exit
atexit.register(_zeroize_all_keys)

# ─────────────────────── Inactivity auto-lock ───────────────────────

_AUTO_LOCK_MINUTES: int = 30  # Default: 30 minutes
_AUTO_LOCK_MIN: int = 1
_AUTO_LOCK_MAX: int = 1440
_inactivity_timers: dict[int, threading.Timer] = {}
_timer_lock = threading.Lock()


def set_auto_lock_timeout(minutes: int) -> None:
    """Configure the vault auto-lock timeout in minutes (1-1440)."""
    global _AUTO_LOCK_MINUTES
    if minutes < _AUTO_LOCK_MIN or minutes > _AUTO_LOCK_MAX:
        raise ValueError(
            f"Auto-lock timeout must be between {_AUTO_LOCK_MIN} and {_AUTO_LOCK_MAX} minutes"
        )
    _AUTO_LOCK_MINUTES = minutes
    log.info("Vault auto-lock timeout set to %d minutes", minutes)


def get_auto_lock_timeout() -> int:
    """Return the current auto-lock timeout in minutes."""
    return _AUTO_LOCK_MINUTES


def _on_inactivity_timeout(folder_id: int) -> None:
    """Called when the inactivity timer expires. Zeroizes key and reports vault as locked."""
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)
        log.info("Vault auto-locked due to inactivity (folder_id=%s)", folder_id)

    with _timer_lock:
        _inactivity_timers.pop(folder_id, None)


def _reset_inactivity_timer(folder_id: int) -> None:
    """Reset (or start) the inactivity auto-lock timer for a vault."""
    with _timer_lock:
        # Cancel existing timer if any
        existing = _inactivity_timers.pop(folder_id, None)
        if existing is not None:
            existing.cancel()

        # Start a new timer
        timeout_seconds = _AUTO_LOCK_MINUTES * 60
        timer = threading.Timer(
            timeout_seconds, _on_inactivity_timeout, args=(folder_id,)
        )
        timer.daemon = True
        timer.start()
        _inactivity_timers[folder_id] = timer


def _cancel_inactivity_timer(folder_id: int) -> None:
    """Cancel the inactivity timer for a vault (e.g., on explicit lock)."""
    with _timer_lock:
        timer = _inactivity_timers.pop(folder_id, None)
        if timer is not None:
            timer.cancel()


def _vault_folder_key(folder_id: int | None) -> int:
    return folder_id if folder_id is not None else -1


# ─────────────────────── Public API ───────────────────────


async def cmd_create_vault(name: str, password: str, folder_id: int) -> dict[str, Any]:
    """Create a new encrypted vault linked to a Telegram folder."""
    _require_healthy_db()
    db = _get_vault_db()
    with _vault_db_lock:
        existing = db.execute(
            "SELECT 1 FROM vaults WHERE folder_id = ?", (folder_id,)
        ).fetchone()
    if existing:
        raise RuntimeError("This folder is already a vault")

    salt = secrets.token_bytes(32)
    key = _derive_key(password, salt)
    # Store a known plaintext encrypted as key_check for password verification
    key_check = _encrypt_bytes(b"TELEGRAB_VAULT_OK", key)

    import time

    with _vault_db_lock:
        db.execute(
            "INSERT INTO vaults (folder_id, name, salt, key_check, created_at) VALUES (?, ?, ?, ?, ?)",
            (folder_id, name, salt, key_check, time.time()),
        )
        db.commit()

    # Auto-unlock for this session
    _session_keys[folder_id] = bytearray(key)
    _reset_inactivity_timer(folder_id)
    log.info("Vault created: %s (folder_id=%s)", name, folder_id)
    return {"folder_id": folder_id, "name": name, "locked": False}


async def cmd_unlock_vault(folder_id: int, password: str) -> bool:
    """Unlock a vault for this session by verifying the password."""
    _require_healthy_db()
    db = _get_vault_db()
    with _vault_db_lock:
        row = db.execute(
            "SELECT salt, key_check FROM vaults WHERE folder_id = ?", (folder_id,)
        ).fetchone()
    if not row:
        raise RuntimeError("Not a vault")

    key = _derive_key(password, bytes(row["salt"]))
    try:
        _decrypt_bytes(bytes(row["key_check"]), key)
    except Exception:
        raise RuntimeError("Incorrect password") from None

    _session_keys[folder_id] = bytearray(key)
    _reset_inactivity_timer(folder_id)
    return True


async def cmd_lock_vault(folder_id: int) -> bool:
    """Lock a vault (zeroize and clear session key)."""
    _cancel_inactivity_timer(folder_id)
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)
    return True


async def cmd_list_vaults() -> list[dict[str, Any]]:
    """List all vaults with their lock status."""
    _require_healthy_db()
    db = _get_vault_db()
    with _vault_db_lock:
        rows = db.execute("SELECT folder_id, name, created_at FROM vaults").fetchall()
    return [
        {
            "folder_id": r["folder_id"],
            "name": r["name"],
            "created_at": r["created_at"],
            "locked": r["folder_id"] not in _session_keys,
        }
        for r in rows
    ]


async def cmd_delete_vault(folder_id: int) -> bool:
    """Remove vault encryption metadata (files remain encrypted on Telegram)."""
    _require_healthy_db()
    db = _get_vault_db()
    with _vault_db_lock:
        db.execute("DELETE FROM vaults WHERE folder_id = ?", (folder_id,))
        db.commit()
    _cancel_inactivity_timer(folder_id)
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)
    return True


def is_vault(folder_id: int | None) -> bool:
    """Check if a folder is a vault."""
    if folder_id is None:
        return False
    db = _get_vault_db()
    with _vault_db_lock:
        return (
            db.execute(
                "SELECT 1 FROM vaults WHERE folder_id = ?", (folder_id,)
            ).fetchone()
            is not None
        )


def is_unlocked(folder_id: int | None) -> bool:
    """Check if a vault is unlocked for this session."""
    if folder_id is None:
        return False
    return folder_id in _session_keys


def encrypt_file(path: str, folder_id: int) -> str:
    """Encrypt a file for vault upload. Returns path to encrypted temp file.

    Files <= 64MB use simple AES-GCM. Larger files use chunked AES-GCM
    to avoid loading the entire file into memory.
    """
    _require_healthy_db()

    key = _session_keys.get(folder_id)
    if not key:
        raise RuntimeError("Vault is locked")

    # Reset inactivity timer on vault operation
    _reset_inactivity_timer(folder_id)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    file_size = Path(path).stat().st_size
    max_simple = 64 * 1024 * 1024

    if file_size <= max_simple:
        data = Path(path).read_bytes()
        encrypted = _encrypt_bytes(data, key)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".enc")  # noqa: SIM115
        tmp.write(encrypted)
        tmp.close()
        return tmp.name

    # Large file: chunked AES-GCM encryption
    # Format: _CHUNKED_MAGIC(8) + base_nonce(12) + num_chunks(4, big-endian)
    #   then per chunk: chunk_ct_len(4, big-endian) + encrypted_chunk (includes 16-byte GCM tag)
    base_nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    num_chunks = (file_size + _CHUNK_SIZE - 1) // _CHUNK_SIZE

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".enc")  # noqa: SIM115
    try:
        tmp.write(_CHUNKED_MAGIC)
        tmp.write(base_nonce)
        tmp.write(struct.pack(">I", num_chunks))

        with Path(path).open("rb") as f:
            for i in range(num_chunks):
                chunk = f.read(_CHUNK_SIZE)
                # Derive per-chunk nonce: base_nonce XOR chunk_index
                nonce = int.from_bytes(base_nonce, "big") ^ i
                chunk_nonce = nonce.to_bytes(12, "big")
                ct = aesgcm.encrypt(chunk_nonce, chunk, None)
                tmp.write(struct.pack(">I", len(ct)))
                tmp.write(ct)

        tmp.close()
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    return tmp.name


def decrypt_file(path: str, folder_id: int) -> str:
    """Decrypt a vault file after download. Returns path to decrypted temp file.

    Supports both simple (small file) and chunked (large file) formats.
    On authentication tag mismatch (corrupted ciphertext), returns a
    VAULT_DECRYPTION_FAILED error, discards temp output, and preserves
    the encrypted file unchanged on disk.
    """
    _require_healthy_db()

    key = _session_keys.get(folder_id)
    if not key:
        raise RuntimeError("Vault is locked")

    # Reset inactivity timer on vault operation
    _reset_inactivity_timer(folder_id)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dec")  # noqa: SIM115
    try:
        with Path(path).open("rb") as f:
            magic = f.read(8)

            if magic == _CHUNKED_MAGIC:
                # Chunked format: stream decryption
                base_nonce = f.read(12)
                num_chunks = struct.unpack(">I", f.read(4))[0]
                aesgcm = AESGCM(key)

                for i in range(num_chunks):
                    ct_len = struct.unpack(">I", f.read(4))[0]
                    ct = f.read(ct_len)
                    nonce = int.from_bytes(base_nonce, "big") ^ i
                    chunk_nonce = nonce.to_bytes(12, "big")
                    plaintext = aesgcm.decrypt(chunk_nonce, ct, None)
                    tmp.write(plaintext)

            elif magic == _HEADER_MAGIC:
                # Simple format: nonce(12) + ciphertext (with tag)
                nonce = f.read(12)
                ct = f.read()
                aesgcm = AESGCM(key)
                plaintext = aesgcm.decrypt(nonce, ct, None)
                tmp.write(plaintext)
            else:
                raise ValueError("Not a vault-encrypted file")

        tmp.close()
    except InvalidTag as exc:
        # Authentication tag mismatch — corrupted or tampered ciphertext
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        log.warning(
            "Vault decryption failed: authentication tag mismatch (folder_id=%s, file=%s)",
            folder_id,
            path,
        )
        raise BridgeError(
            code=ErrorCode.VAULT_DECRYPTION_FAILED,
            message="Decryption failed: the encrypted file is corrupted or has been tampered with.",
            detail=f"AES-GCM authentication tag mismatch for file: {Path(path).name}. "
            "The encrypted file has been preserved unchanged on disk.",
        ) from exc
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    return tmp.name


__all__ = [
    "cmd_create_vault",
    "cmd_unlock_vault",
    "cmd_lock_vault",
    "cmd_list_vaults",
    "cmd_delete_vault",
    "is_vault",
    "is_unlocked",
    "encrypt_file",
    "decrypt_file",
    "set_auto_lock_timeout",
    "get_auto_lock_timeout",
]
