"""Pinned Files / Quick Access.

Stores pinned file IDs in the SQLite cache for instant retrieval.
"""

from __future__ import annotations

import sqlite3
import time
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
            CREATE TABLE IF NOT EXISTS pinned_files (
                message_id INTEGER NOT NULL,
                folder_id INTEGER NOT NULL,
                name TEXT,
                size INTEGER,
                pinned_at REAL NOT NULL,
                PRIMARY KEY (message_id, folder_id)
            )
        """)
        _conn.commit()
    return _conn


async def cmd_pin_file(message_id: int, folder_id: int | None, name: str, size: int) -> bool:
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    conn.execute(
        "INSERT OR REPLACE INTO pinned_files (message_id, folder_id, name, size, pinned_at) VALUES (?, ?, ?, ?, ?)",
        (message_id, fk, name, size, time.time()),
    )
    conn.commit()
    return True


async def cmd_unpin_file(message_id: int, folder_id: int | None) -> bool:
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    conn.execute(
        "DELETE FROM pinned_files WHERE message_id = ? AND folder_id = ?",
        (message_id, fk),
    )
    conn.commit()
    return True


async def cmd_get_pinned_files() -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT message_id, folder_id, name, size, pinned_at FROM pinned_files ORDER BY pinned_at DESC"
    ).fetchall()
    return [
        {
            "message_id": r["message_id"],
            "folder_id": r["folder_id"] if r["folder_id"] != -1 else None,
            "name": r["name"],
            "size": r["size"],
            "pinned_at": r["pinned_at"],
        }
        for r in rows
    ]


async def cmd_is_pinned(message_id: int, folder_id: int | None) -> bool:
    conn = _get_conn()
    fk = folder_id if folder_id is not None else -1
    row = conn.execute(
        "SELECT 1 FROM pinned_files WHERE message_id = ? AND folder_id = ?",
        (message_id, fk),
    ).fetchone()
    return row is not None


__all__ = ["cmd_pin_file", "cmd_unpin_file", "cmd_get_pinned_files", "cmd_is_pinned"]
