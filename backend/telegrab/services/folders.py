"""Folder use cases — each folder is a Telegram channel tagged `[TD]`."""

from __future__ import annotations

import logging
import re
from typing import Any

from telethon import errors as tl_errors
from telethon.tl import functions, types

from .. import telegram as tg
from . import require_client

log = logging.getLogger(__name__)

FOLDER_TITLE_TAG = "[TD]"
FOLDER_ABOUT_TAG = "[telegram-drive-folder]"


# ───────────────────────────── create / delete ─────────────────────────────


async def cmd_create_folder(name: str) -> dict[str, Any]:
    # Validate folder name
    name = (name or "").strip()
    if not name:
        raise RuntimeError("Folder name cannot be empty.")
    if len(name) > 128:
        raise RuntimeError("Folder name too long (max 128 characters).")
    # Reject control characters and path separators
    if re.search(r"[\x00-\x1f/\\]", name):
        raise RuntimeError("Folder name contains invalid characters.")

    state = tg.get_state()
    client = require_client()

    log.info("Creating Telegram channel: %s", name)
    try:
        result = await client(
            functions.channels.CreateChannelRequest(
                title=f"{name} {FOLDER_TITLE_TAG}",
                about=f"Telegram Drive Storage Folder\n{FOLDER_ABOUT_TAG}",
                broadcast=True,
                megagroup=False,
                for_import=False,
                forum=False,
                ttl_period=None,
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(tg.map_error(exc)) from exc

    chat = None
    chats = getattr(result, "chats", []) or []
    if chats:
        chat = chats[0]

    if not isinstance(chat, types.Channel):
        raise RuntimeError("Created chat is not a channel")

    chat_id = int(chat.id)

    try:
        await client(
            functions.messages.SetHistoryTTLRequest(
                peer=types.InputPeerChannel(
                    channel_id=chat.id,
                    access_hash=chat.access_hash or 0,
                ),
                period=0,
            )
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("SetHistoryTTL failed (non-fatal): %s", exc)

    tg.remember_peer(chat)
    state.folder_ids.add(chat_id)
    return {"id": chat_id, "name": name, "parent_id": None}


# ─────────────────────────────────── rename ───────────────────────────────────


async def cmd_rename_folder(folder_id: int, name: str) -> dict[str, Any]:
    """Rename a folder by editing the underlying Telegram channel title.

    The `[TD]` suffix tag is preserved so the folder is still picked up
    by `cmd_scan_folders` on a fresh login.
    """
    new_name = (name or "").strip()
    if not new_name:
        raise RuntimeError("Folder name cannot be empty.")
    if len(new_name) > 128:
        raise RuntimeError("Folder name too long (max 128 characters).")
    if re.search(r"[\x00-\x1f/\\]", new_name):
        raise RuntimeError("Folder name contains invalid characters.")

    client = require_client()

    log.info("Renaming folder %s -> %s", folder_id, new_name)

    entity = await tg.resolve_peer(client, int(folder_id))
    if not isinstance(entity, types.Channel):
        raise RuntimeError("Only channels (folders) can be renamed.")

    try:
        await client(
            functions.channels.EditTitleRequest(
                channel=types.InputChannel(
                    channel_id=entity.id,
                    access_hash=entity.access_hash or 0,
                ),
                title=f"{new_name} {FOLDER_TITLE_TAG}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to rename folder: {exc}") from exc

    # Refresh the cached peer so subsequent calls see the new title.
    entity.title = f"{new_name} {FOLDER_TITLE_TAG}"
    tg.remember_peer(entity, int(folder_id))

    return {"id": int(folder_id), "name": new_name, "parent_id": None}


async def cmd_delete_folder(folder_id: int) -> bool:
    state = tg.get_state()
    client = require_client()

    log.info("Deleting folder/channel: %s", folder_id)

    entity = await tg.resolve_peer(client, int(folder_id))
    if not isinstance(entity, types.Channel):
        raise RuntimeError("Only channels (folders) can be deleted.")

    try:
        await client(
            functions.channels.DeleteChannelRequest(
                channel=types.InputChannel(
                    channel_id=entity.id,
                    access_hash=entity.access_hash or 0,
                )
            )
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to delete channel: {exc}") from exc

    state.peer_cache.pop(int(folder_id), None)
    state.folder_ids.discard(int(folder_id))
    _forget_folder_locally(int(folder_id))
    return True


def _forget_folder_locally(folder_id: int) -> None:
    """Drop pins, fingerprints, vault state and caches of a deleted folder."""
    from ..config import preview_cache_dir, thumbnail_cache_dir
    from . import localdb
    from . import vault as vault_mod

    for cleanup in (localdb.forget_folder, vault_mod.forget_vault):
        try:
            cleanup(folder_id)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Local cleanup for deleted folder %s failed: %s", folder_id, exc
            )
    for cache_dir in (preview_cache_dir(), thumbnail_cache_dir()):
        for cached in cache_dir.glob(f"{folder_id}_*"):
            cached.unlink(missing_ok=True)


# ─────────────────────────────── scan / list ───────────────────────────────


async def cmd_scan_folders() -> list[dict[str, Any]]:
    state = tg.get_state()
    client = require_client()

    folders: list[dict[str, Any]] = []
    log.info("Starting folder scan...")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, types.Channel):
            cid = int(entity.id)
            tg.remember_peer(entity)

            title = entity.title or ""
            tag = FOLDER_TITLE_TAG.lower()
            if tag in title.lower():
                display = (
                    title.replace(" [TD]", "")
                    .replace(" [td]", "")
                    .replace("[TD]", "")
                    .replace("[td]", "")
                    .strip()
                )
                folders.append({"id": cid, "name": display or title, "parent_id": None})
                continue

            # Only check about field for owned/admin channels
            if not getattr(entity, "creator", False):
                continue

            try:
                full = await client(
                    functions.channels.GetFullChannelRequest(
                        channel=types.InputChannel(
                            channel_id=entity.id,
                            access_hash=entity.access_hash or 0,
                        )
                    )
                )
                about = ""
                full_chat = getattr(full, "full_chat", None)
                if full_chat is not None:
                    about = getattr(full_chat, "about", "") or ""
                if FOLDER_ABOUT_TAG in about:
                    folders.append({"id": cid, "name": title, "parent_id": None})
            except tl_errors.RPCError as exc:
                log.debug("GetFullChannel failed for %s: %s", title, exc)
            except Exception as exc:  # noqa: BLE001
                log.debug("GetFullChannel unexpected error %s: %s", title, exc)

        elif isinstance(entity, types.User):
            tg.remember_peer(entity)

    state.folder_ids = {int(f["id"]) for f in folders}
    log.info(
        "Scan complete. %d folders (peer cache: %d entries)",
        len(folders),
        len(state.peer_cache),
    )
    return folders


__all__ = [
    "cmd_create_folder",
    "cmd_rename_folder",
    "cmd_delete_folder",
    "cmd_scan_folders",
]
