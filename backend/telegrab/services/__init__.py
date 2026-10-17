"""Application services — use-case layer.

Each module exposes async (or sync, where appropriate) functions matching
the bridge command surface. The bridge in `telegrab.api.bridge` wraps each
one as a sync method that schedules the coroutine on the runtime thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telethon import TelegramClient

# SQLite primary keys can't be NULL, so the root/"no folder" case is stored
# as the sentinel -1. These helpers keep that mapping in one place.
_NO_FOLDER = -1


class NotConnectedError(RuntimeError):
    """Raised when a command needs Telegram but no client is available."""


def require_client() -> TelegramClient:
    """Return the live Telegram client or raise :class:`NotConnectedError`.

    Commands must never pretend to succeed while disconnected — that used to
    silently drop uploads/deletes and overwrite download targets.
    """
    from .. import telegram as tg

    client = tg.get_state().client
    if client is None:
        raise NotConnectedError(
            "Not connected to Telegram. Check your connection and try again."
        )
    return client


def folder_key(folder_id: int | None) -> int:
    """Map an optional folder id to its DB storage key (-1 for root)."""
    return folder_id if folder_id is not None else _NO_FOLDER


def folder_from_key(key: int) -> int | None:
    """Inverse of :func:`folder_key` — map -1 back to None."""
    return None if key == _NO_FOLDER else key
