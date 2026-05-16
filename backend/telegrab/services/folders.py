"""Folder use cases.

Mirrors `src-tauri/src/commands/fs.rs` (folder section).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from telethon import errors as tl_errors
from telethon.tl import functions, types

from .. import telegram as tg

log = logging.getLogger(__name__)

FOLDER_TITLE_TAG = "[TD]"
FOLDER_ABOUT_TAG = "[telegram-drive-folder]"


# ───────────────────────────── create / delete ─────────────────────────────


async def cmd_create_folder(name: str) -> dict[str, Any]:
    state = tg.get_state()
    client = state.client
    if client is None:
        mock_id = int(time.time())
        log.info("[MOCK] create folder '%s' (id=%s)", name, mock_id)
        return {"id": mock_id, "name": name, "parent_id": None}

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

    state.peer_cache[chat_id] = chat
    return {"id": chat_id, "name": name, "parent_id": None}


async def cmd_delete_folder(folder_id: int) -> bool:
    state = tg.get_state()
    client = state.client
    if client is None:
        log.info("[MOCK] delete folder %s", folder_id)
        return True

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
    return True


# ─────────────────────────────── scan / list ───────────────────────────────


async def cmd_scan_folders() -> list[dict[str, Any]]:
    state = tg.get_state()
    client = state.client
    if client is None:
        return []

    folders: list[dict[str, Any]] = []
    log.info("Starting folder scan...")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        if isinstance(entity, types.Channel):
            cid = int(entity.id)
            state.peer_cache[cid] = entity

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
            state.peer_cache[int(entity.id)] = entity

    log.info(
        "Scan complete. %d folders (peer cache: %d entries)",
        len(folders),
        len(state.peer_cache),
    )
    return folders


__all__ = ["cmd_create_folder", "cmd_delete_folder", "cmd_scan_folders"]
