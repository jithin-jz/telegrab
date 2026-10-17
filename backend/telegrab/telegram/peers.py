"""Peer resolution & cache.

`folder_id == None` is the user's own peer (Telegram "Saved Messages"). For
any other id we consult `state.peer_cache` first, then Telethon's session
entity cache (which already knows every peer seen in a dialog listing, so no
network scan is needed), and only as a last resort walk the dialog list.

Cache entries are always stored as `(entity, cached_at)` tuples — use
:func:`remember_peer` to write them — and expire after `PEER_CACHE_TTL`
seconds.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.types import InputPeerSelf, PeerChannel, PeerChat, PeerUser

log = logging.getLogger(__name__)

PEER_CACHE_TTL = 300  # 5 minutes


def remember_peer(state, entity: Any, folder_id: int | None = None) -> None:
    """Cache an entity under its id (or an explicit `folder_id`)."""
    key = folder_id if folder_id is not None else getattr(entity, "id", None)
    if key is not None:
        state.peer_cache[int(key)] = (entity, time.time())


async def resolve_peer(state, client: TelegramClient, folder_id: int | None) -> Any:
    """Return a Telethon entity for a folder_id."""
    if folder_id is None:
        return InputPeerSelf()

    cached = state.peer_cache.get(folder_id)
    if cached is not None:
        entity, cached_at = cached
        if time.time() - cached_at < PEER_CACHE_TTL:
            return entity
        # Expired — remove and continue to resolution
        del state.peer_cache[folder_id]

    # Fast path: the session already stores access hashes for known peers.
    # Folders are channels, so try that type first.
    for peer_type in (PeerChannel, PeerUser, PeerChat):
        try:
            entity = await client.get_entity(peer_type(folder_id))
        except (ValueError, TypeError, RPCError):
            continue
        remember_peer(state, entity, folder_id)
        return entity

    log.debug("Peer %s not in session cache — scanning dialogs", folder_id)
    found = None
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        remember_peer(state, entity)
        if getattr(entity, "id", None) == folder_id:
            found = entity
            break

    if found is None:
        raise ValueError(f"Folder/Chat {folder_id} not found")
    return found


def clear_peer_cache(state) -> None:
    state.peer_cache.clear()
