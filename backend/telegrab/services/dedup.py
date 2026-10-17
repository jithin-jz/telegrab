"""Duplicate detection — hash-based file deduplication on upload.

Computes SHA-256 over head/middle/tail samples plus the size as a
fingerprint, and stores fingerprints in the shared local DB for lookup.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from . import folder_from_key, folder_key, localdb


def compute_file_hash(path: str) -> str:
    """Compute fingerprint: SHA-256 of head + middle + tail samples + size.

    Sampling three regions (instead of just the head) makes collisions
    vanishingly unlikely for distinct files that happen to share the same
    leading bytes and size — e.g. re-encodes, padded archives, or files
    differing only in their tail. Cost stays constant (~3 MB read) regardless
    of file size.
    """
    p = Path(path)
    size = p.stat().st_size
    sample = 1024 * 1024  # 1 MB per region
    h = hashlib.sha256()
    with p.open("rb") as f:
        h.update(f.read(sample))  # head
        if size > 2 * sample:
            f.seek(size // 2)
            h.update(f.read(sample))  # middle
        if size > sample:
            f.seek(max(0, size - sample))
            h.update(f.read(sample))  # tail
    h.update(str(size).encode())
    return h.hexdigest()


def store_hash(
    file_hash: str, folder_id: int | None, message_id: int, name: str, size: int
) -> None:
    """Store a file hash after successful upload."""
    localdb.execute(
        "INSERT OR REPLACE INTO file_hashes (hash, folder_id, message_id, name, size) "
        "VALUES (?, ?, ?, ?, ?)",
        (file_hash, folder_key(folder_id), message_id, name, size),
    )


def find_duplicate(file_hash: str, folder_id: int | None) -> dict[str, Any] | None:
    """Check if a file with this hash already exists in the folder."""
    rows = localdb.query(
        "SELECT message_id, name, size FROM file_hashes WHERE hash = ? AND folder_id = ?",
        (file_hash, folder_key(folder_id)),
    )
    if rows:
        row = rows[0]
        return {
            "message_id": row["message_id"],
            "name": row["name"],
            "size": row["size"],
        }
    return None


def find_duplicate_any_folder(file_hash: str) -> dict[str, Any] | None:
    """Check if a file with this hash exists in ANY folder."""
    rows = localdb.query(
        "SELECT message_id, folder_id, name, size FROM file_hashes WHERE hash = ?",
        (file_hash,),
    )
    if rows:
        row = rows[0]
        return {
            "message_id": row["message_id"],
            "folder_id": folder_from_key(row["folder_id"]),
            "name": row["name"],
            "size": row["size"],
        }
    return None


def remove_hash(message_id: int, folder_id: int | None) -> None:
    """Remove hash entry when a file is deleted."""
    localdb.execute(
        "DELETE FROM file_hashes WHERE message_id = ? AND folder_id = ?",
        (message_id, folder_key(folder_id)),
    )


def move_hash(
    message_id: int,
    source_folder_id: int | None,
    new_message_id: int,
    target_folder_id: int | None,
) -> None:
    """Re-point a fingerprint after a file was moved to another folder."""
    localdb.execute(
        "UPDATE OR REPLACE file_hashes SET folder_id = ?, message_id = ? "
        "WHERE message_id = ? AND folder_id = ?",
        (
            folder_key(target_folder_id),
            new_message_id,
            message_id,
            folder_key(source_folder_id),
        ),
    )


async def cmd_check_duplicate(path: str, folder_id: int | None) -> dict[str, Any]:
    """Check if a file is a duplicate before upload.

    Returns: {"duplicate": bool, "hash": str, "existing": {...} | null}
    """
    # Disk I/O — keep it off the event loop.
    file_hash = await asyncio.to_thread(compute_file_hash, path)
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
    "move_hash",
]
