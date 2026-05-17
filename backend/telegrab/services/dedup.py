"""Duplicate detection — hash-based file deduplication on upload.

Computes SHA-256 of the first 1MB + file size as a fingerprint.
Stores fingerprints in the SQLite cache for fast lookup.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from ..config import app_data_dir

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = app_data_dir() / "metadata_cache.db"
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                hash TEXT NOT NULL,
                folder_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                name TEXT,
                size INTEGER,
                PRIMARY KEY (hash, folder_id)
            )
        """)
        _conn.commit()
    return _conn


def compute_file_hash(path: str) -> str:
    """Compute fingerprint: SHA-256 of first 1MB + file size."""
    p = Path(path)
    size = p.stat().st_size
    h = hashlib.sha256()
    with p.open("rb") as f:
        h.update(f.read(1024 * 1024))  # first 1MB
    h.update(str(size).encode())
    return h.hexdigest()


def store_hash(file_hash: str, folder_id: int | None, message_id: int, name: str, size: int) -> None:
    """Store a file hash after successful upload."""
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    conn.execute(
        "INSERT OR REPLACE INTO file_hashes (hash, folder_id, message_id, name, size) VALUES (?, ?, ?, ?, ?)",
        (file_hash, fk, message_id, name, size),
    )
    conn.commit()


def find_duplicate(file_hash: str, folder_id: int | None) -> dict[str, Any] | None:
    """Check if a file with this hash already exists in the folder."""
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    row = conn.execute(
        "SELECT message_id, name, size FROM file_hashes WHERE hash = ? AND folder_id = ?",
        (file_hash, fk),
    ).fetchone()
    if row:
        return {"message_id": row["message_id"], "name": row["name"], "size": row["size"]}
    return None


def find_duplicate_any_folder(file_hash: str) -> dict[str, Any] | None:
    """Check if a file with this hash exists in ANY folder."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT message_id, folder_id, name, size FROM file_hashes WHERE hash = ?",
        (file_hash,),
    ).fetchone()
    if row:
        return {
            "message_id": row["message_id"],
            "folder_id": row["folder_id"] if row["folder_id"] != -1 else None,
            "name": row["name"],
            "size": row["size"],
        }
    return None


def remove_hash(message_id: int, folder_id: int | None) -> None:
    """Remove hash entry when a file is deleted."""
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    conn.execute(
        "DELETE FROM file_hashes WHERE message_id = ? AND folder_id = ?",
        (message_id, fk),
    )
    conn.commit()


async def cmd_check_duplicate(path: str, folder_id: int | None) -> dict[str, Any]:
    """Check if a file is a duplicate before upload.

    Returns: {"duplicate": bool, "hash": str, "existing": {...} | null}
    """
    file_hash = compute_file_hash(path)
    existing = find_duplicate(file_hash, folder_id)
    if not existing:
        existing = find_duplicate_any_folder(file_hash)
    return {
        "duplicate": existing is not None,
        "hash": file_hash,
        "existing": existing,
    }


__all__ = [
    "cmd_check_duplicate",
    "compute_file_hash",
    "store_hash",
    "find_duplicate",
    "remove_hash",
]
