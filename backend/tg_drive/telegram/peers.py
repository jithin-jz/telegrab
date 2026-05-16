"""Peer resolution & cache.

`folder_id == None` is the user's own peer (Telegram "Saved Messages"). For
any other id, we first consult the `state.peer_cache` populated by the
folder scan; on miss we walk the dialog list once and prime the cache (same
trade-off the Rust version made).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from telethon import TelegramClient
from telethon.tl.types import InputPeerSelf

log = logging.getLogger(__name__)


async def resolve_peer(
    state, client: TelegramClient, folder_id: Optional[int]
) -> Any:
    """Return a Telethon entity for a folder_id."""
    if folder_id is None:
        return InputPeerSelf()

    cached = state.peer_cache.get(folder_id)
    if cached is not None:
        return cached

    log.debug("Peer cache miss for folder_id=%s — scanning dialogs", folder_id)
    found = None
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        eid = getattr(entity, "id", None)
        if eid is not None:
            state.peer_cache[eid] = entity
            if eid == folder_id:
                found = entity
                # keep iterating — warms the cache for future calls

    if found is None:
        # As a last resort, ask Telegram directly.
        try:
            found = await client.get_entity(folder_id)
            state.peer_cache[folder_id] = found
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Folder/Chat {folder_id} not found: {exc}") from exc

    return found


def clear_peer_cache(state) -> None:
    state.peer_cache.clear()
