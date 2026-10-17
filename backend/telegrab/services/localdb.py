"""Shared local SQLite database (``metadata_cache.db``).

Holds per-account local state that doesn't live on Telegram: upload
fingerprints for duplicate detection and pinned files. A single connection
guarded by a lock is shared by every service so writes from the asyncio loop
and bridge threads never interleave.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from typing import Any

from ..config import app_data_dir
from . import folder_key

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_hashes (
    hash TEXT NOT NULL,
    folder_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    name TEXT,
    size INTEGER,
    PRIMARY KEY (hash, folder_id)
);
CREATE TABLE IF NOT EXISTS pinned_files (
    message_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    name TEXT,
    size INTEGER,
    pinned_at REAL NOT NULL,
    PRIMARY KEY (message_id, folder_id)
);
"""

# Tables that hold account-specific rows and must be wiped on logout.
_ACCOUNT_TABLES = ("file_hashes", "pinned_files")


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        conn = sqlite3.connect(
            str(app_data_dir() / "metadata_cache.db"), check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        conn.commit()
        _conn = conn
    return _conn


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with _lock:
        return _get_conn().execute(sql, tuple(params)).fetchall()


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    with _lock:
        conn = _get_conn()
        conn.execute(sql, tuple(params))
        conn.commit()


def forget_folder(folder_id: int | None) -> None:
    """Drop every local row that belongs to a (deleted) folder."""
    fk = folder_key(folder_id)
    with _lock:
        conn = _get_conn()
        for table in _ACCOUNT_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE folder_id = ?", (fk,))
        conn.commit()


def forget_messages(folder_id: int | None, message_ids: Iterable[int]) -> None:
    """Drop pins and fingerprints for messages that no longer exist."""
    fk = folder_key(folder_id)
    ids = [(int(m), fk) for m in message_ids]
    with _lock:
        conn = _get_conn()
        for table in _ACCOUNT_TABLES:
            conn.executemany(
                f"DELETE FROM {table} WHERE message_id = ? AND folder_id = ?",
                ids,
            )
        conn.commit()


def wipe_account_data() -> None:
    """Remove all account-specific rows (called on logout)."""
    with _lock:
        conn = _get_conn()
        for table in _ACCOUNT_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()


def reset_for_tests() -> None:
    """Close the shared connection so tests can point at a fresh data dir."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
