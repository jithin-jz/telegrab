"""Pinned Files / Quick Access.

Stores pinned file IDs in the shared local DB for instant retrieval.
"""

from __future__ import annotations

import time
from typing import Any

from . import folder_from_key, folder_key, localdb


async def cmd_pin_file(
    message_id: int, folder_id: int | None, name: str, size: int
) -> bool:
    localdb.execute(
        "INSERT OR REPLACE INTO pinned_files (message_id, folder_id, name, size, pinned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (message_id, folder_key(folder_id), name, size, time.time()),
    )
    return True


async def cmd_unpin_file(message_id: int, folder_id: int | None) -> bool:
    localdb.execute(
        "DELETE FROM pinned_files WHERE message_id = ? AND folder_id = ?",
        (message_id, folder_key(folder_id)),
    )
    return True


async def cmd_get_pinned_files() -> list[dict[str, Any]]:
    rows = localdb.query(
        "SELECT message_id, folder_id, name, size, pinned_at FROM pinned_files "
        "ORDER BY pinned_at DESC"
    )
    return [
        {
            "message_id": r["message_id"],
            "folder_id": folder_from_key(r["folder_id"]),
            "name": r["name"],
            "size": r["size"],
            "pinned_at": r["pinned_at"],
        }
        for r in rows
    ]


async def cmd_is_pinned(message_id: int, folder_id: int | None) -> bool:
    rows = localdb.query(
        "SELECT 1 FROM pinned_files WHERE message_id = ? AND folder_id = ?",
        (message_id, folder_key(folder_id)),
    )
    return bool(rows)


__all__ = ["cmd_pin_file", "cmd_unpin_file", "cmd_get_pinned_files", "cmd_is_pinned"]
