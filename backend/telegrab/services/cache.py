"""Local SQLite metadata cache for file listings."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from ..config import app_data_dir

_db_path: Path | None = None
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn, _db_path
    if _conn is None:
        _db_path = app_data_dir() / "metadata_cache.db"
        _db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_cache() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_cache (
            message_id INTEGER NOT NULL,
            folder_id INTEGER NOT NULL,
            name TEXT,
            size INTEGER,
            created_at TEXT,
            icon_type TEXT,
            PRIMARY KEY (message_id, folder_id)
        );
        CREATE TABLE IF NOT EXISTS cache_meta (
            folder_id INTEGER PRIMARY KEY,
            updated_at REAL
        );
    """)
    conn.commit()


def _folder_key(folder_id: int | None) -> int:
    return folder_id if folder_id is not None else -1


def get_cached_files(folder_id: int | None) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT message_id, folder_id, name, size, created_at, icon_type FROM file_cache WHERE folder_id = ?",
        (_folder_key(folder_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_files(folder_id: int | None, files: list[dict[str, Any]]) -> None:
    conn = _get_conn()
    fk = _folder_key(folder_id)
    conn.executemany(
        "INSERT OR REPLACE INTO file_cache (message_id, folder_id, name, size, created_at, icon_type) VALUES (?, ?, ?, ?, ?, ?)",
        [(f.get("message_id") or f.get("messageId"), fk, f.get("name"), f.get("size"), f.get("created_at") or f.get("createdAt"), f.get("icon_type") or f.get("iconType")) for f in files],
    )
    conn.execute(
        "INSERT OR REPLACE INTO cache_meta (folder_id, updated_at) VALUES (?, ?)",
        (fk, time.time()),
    )
    conn.commit()


def invalidate_folder(folder_id: int | None) -> None:
    conn = _get_conn()
    fk = _folder_key(folder_id)
    conn.execute("DELETE FROM file_cache WHERE folder_id = ?", (fk,))
    conn.execute("DELETE FROM cache_meta WHERE folder_id = ?", (fk,))
    conn.commit()


def get_cache_timestamp(folder_id: int | None) -> float | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT updated_at FROM cache_meta WHERE folder_id = ?",
        (_folder_key(folder_id),),
    ).fetchone()
    return row["updated_at"] if row else None
