"""Encrypted Vaults — AES-256-GCM client-side encryption.

Files are encrypted before upload and decrypted after download.
The master password derives a key via PBKDF2. Telegram never sees plaintext.
Vault metadata (salt, folder_id) is stored locally in the SQLite cache.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from ..config import app_data_dir

log = logging.getLogger(__name__)

_VAULT_DB: sqlite3.Connection | None = None
_PBKDF2_ITERATIONS = 600_000
_HEADER_MAGIC = b"TGVAULT1"  # 8 bytes magic header


def _get_vault_db() -> sqlite3.Connection:
    global _VAULT_DB
    if _VAULT_DB is None:
        path = app_data_dir() / "vaults.db"
        _VAULT_DB = sqlite3.connect(str(path), check_same_thread=False)
        _VAULT_DB.row_factory = sqlite3.Row
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
    return _VAULT_DB


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password + salt using PBKDF2-SHA256."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)


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
    payload = data[len(_HEADER_MAGIC):]
    nonce = payload[:12]
    ct = payload[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, None)


# ─────────────────────── Session key store ───────────────────────
# Unlocked vault keys are held in memory only for the session.
_session_keys: dict[int, bytes] = {}


def _vault_folder_key(folder_id: int | None) -> int:
    return folder_id if folder_id is not None else -1


# ─────────────────────── Public API ───────────────────────


async def cmd_create_vault(name: str, password: str, folder_id: int) -> dict[str, Any]:
    """Create a new encrypted vault linked to a Telegram folder."""
    db = _get_vault_db()
    existing = db.execute("SELECT 1 FROM vaults WHERE folder_id = ?", (folder_id,)).fetchone()
    if existing:
        raise RuntimeError("This folder is already a vault")

    salt = secrets.token_bytes(32)
    key = _derive_key(password, salt)
    # Store a known plaintext encrypted as key_check for password verification
    key_check = _encrypt_bytes(b"TELEGRAB_VAULT_OK", key)

    import time
    db.execute(
        "INSERT INTO vaults (folder_id, name, salt, key_check, created_at) VALUES (?, ?, ?, ?, ?)",
        (folder_id, name, salt, key_check, time.time()),
    )
    db.commit()

    # Auto-unlock for this session
    _session_keys[folder_id] = key
    log.info("Vault created: %s (folder_id=%s)", name, folder_id)
    return {"folder_id": folder_id, "name": name, "locked": False}


async def cmd_unlock_vault(folder_id: int, password: str) -> bool:
    """Unlock a vault for this session by verifying the password."""
    db = _get_vault_db()
    row = db.execute("SELECT salt, key_check FROM vaults WHERE folder_id = ?", (folder_id,)).fetchone()
    if not row:
        raise RuntimeError("Not a vault")

    key = _derive_key(password, bytes(row["salt"]))
    try:
        _decrypt_bytes(bytes(row["key_check"]), key)
    except Exception:
        raise RuntimeError("Incorrect password") from None

    _session_keys[folder_id] = key
    return True


async def cmd_lock_vault(folder_id: int) -> bool:
    """Lock a vault (clear session key)."""
    _session_keys.pop(folder_id, None)
    return True


async def cmd_list_vaults() -> list[dict[str, Any]]:
    """List all vaults with their lock status."""
    db = _get_vault_db()
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
    db = _get_vault_db()
    db.execute("DELETE FROM vaults WHERE folder_id = ?", (folder_id,))
    db.commit()
    _session_keys.pop(folder_id, None)
    return True


def is_vault(folder_id: int | None) -> bool:
    """Check if a folder is a vault."""
    if folder_id is None:
        return False
    db = _get_vault_db()
    return db.execute("SELECT 1 FROM vaults WHERE folder_id = ?", (folder_id,)).fetchone() is not None


def is_unlocked(folder_id: int | None) -> bool:
    """Check if a vault is unlocked for this session."""
    if folder_id is None:
        return False
    return folder_id in _session_keys


def encrypt_file(path: str, folder_id: int) -> str:
    """Encrypt a file for vault upload. Returns path to encrypted temp file."""
    key = _session_keys.get(folder_id)
    if not key:
        raise RuntimeError("Vault is locked")

    data = Path(path).read_bytes()
    encrypted = _encrypt_bytes(data, key)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".enc")  # noqa: SIM115
    tmp.write(encrypted)
    tmp.close()
    return tmp.name


def decrypt_file(path: str, folder_id: int) -> str:
    """Decrypt a vault file after download. Returns path to decrypted temp file."""
    key = _session_keys.get(folder_id)
    if not key:
        raise RuntimeError("Vault is locked")

    data = Path(path).read_bytes()
    decrypted = _decrypt_bytes(data, key)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dec")  # noqa: SIM115
    tmp.write(decrypted)
    tmp.close()
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
]
