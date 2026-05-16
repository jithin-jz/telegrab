"""Telegram domain — Telethon client wrapper, peers, transfers, media helpers.

The submodules are organised so that nothing here depends on the bridge or
the FastAPI servers — only `telethon` and `telegrab.config`.

For caller ergonomics we expose state-aware wrappers around the helpers
that take `state` as their first argument: callers can use
`resolve_peer(client, folder_id)` directly without juggling the singleton.
"""

from __future__ import annotations

from typing import Any

from telethon import TelegramClient

from . import client as _client_mod
from . import errors as _errors
from . import media as _media
from . import peers as _peers
from . import transfers as _transfers

# Re-export client lifecycle as-is.
TelegramState = _client_mod.TelegramState
get_state = _client_mod.get_state
ensure_client = _client_mod.ensure_client
logout_and_reset = _client_mod.logout_and_reset


# ──────────────────────── state-bound conveniences ────────────────────────


async def resolve_peer(client: TelegramClient, folder_id: int | None) -> Any:
    return await _peers.resolve_peer(get_state(), client, folder_id)


def clear_peer_cache() -> None:
    _peers.clear_peer_cache(get_state())


def cancel_transfer(transfer_id: str) -> None:
    _transfers.cancel_transfer(get_state(), transfer_id)


def is_cancelled(transfer_id: str) -> bool:
    return _transfers.is_cancelled(get_state(), transfer_id)


def clear_cancellation(transfer_id: str) -> None:
    _transfers.clear_cancellation(get_state(), transfer_id)


# Errors / media helpers — re-exported flat for ergonomic imports.
map_error = _errors.map_error

file_metadata_from_message = _media.file_metadata_from_message
media_total_size = _media.media_total_size
mime_type_from_message = _media.mime_type_from_message
filename_from_message = _media.filename_from_message


__all__ = [
    "TelegramState",
    "get_state",
    "ensure_client",
    "logout_and_reset",
    "resolve_peer",
    "clear_peer_cache",
    "cancel_transfer",
    "is_cancelled",
    "clear_cancellation",
    "map_error",
    "file_metadata_from_message",
    "media_total_size",
    "mime_type_from_message",
    "filename_from_message",
]
