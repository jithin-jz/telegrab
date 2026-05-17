"""File-operation use cases.

Mirrors `src-tauri/src/commands/fs.rs` (file section).

Progress events fire through `telegrab.infra.events.bus` on the
`upload-progress` / `download-progress` channels. Cancellation is
cooperative — the progress callbacks raise `asyncio.CancelledError`
when the user has marked the transfer cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from pathlib import Path
from typing import Any

from telethon.tl import functions, types

from .. import telegram as tg
from ..infra import bus, get_manager

log = logging.getLogger(__name__)

# Throttle progress events so we don't drown the JS bus.
_PROGRESS_INTERVAL_SECS = 0.25


# ─────────────────────────────── listings ───────────────────────────────


async def cmd_get_files(
    folder_id: int | None,
    limit: int = 0,
    offset_id: int = 0,
) -> list[dict[str, Any]]:
    state = tg.get_state()
    client = state.client
    if client is None:
        log.info("[MOCK] cmd_get_files folder=%s", folder_id)
        return []

    peer = await tg.resolve_peer(client, folder_id)
    out: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {}
    if limit > 0:
        kwargs["limit"] = limit
    if offset_id > 0:
        kwargs["offset_id"] = offset_id
    async for msg in client.iter_messages(peer, **kwargs):
        meta = tg.file_metadata_from_message(msg, folder_id)
        if meta is not None:
            out.append(meta)
    return out


async def cmd_search_global(query: str) -> list[dict[str, Any]]:
    state = tg.get_state()
    client = state.client
    if client is None:
        return []

    log.info("Searching global for: %s", query)

    result = await client(
        functions.messages.SearchGlobalRequest(
            q=query,
            filter=types.InputMessagesFilterEmpty(),
            min_date=None,
            max_date=None,
            offset_rate=0,
            offset_peer=types.InputPeerEmpty(),
            offset_id=0,
            limit=50,
            folder_id=None,
            broadcasts_only=False,
            groups_only=False,
            users_only=False,
        )
    )

    out: list[dict[str, Any]] = []
    for msg in getattr(result, "messages", []) or []:
        if not isinstance(msg, types.Message):
            continue
        peer_id = msg.peer_id
        derived_folder: int | None = None
        if isinstance(peer_id, types.PeerChannel):
            derived_folder = peer_id.channel_id
        elif isinstance(peer_id, types.PeerUser):
            derived_folder = peer_id.user_id
        elif isinstance(peer_id, types.PeerChat):
            derived_folder = peer_id.chat_id

        meta = tg.file_metadata_from_message(msg, derived_folder)
        if meta is not None:
            out.append(meta)
    return out


# ─────────────────────────── transfer cancellation ───────────────────────────


async def cmd_cancel_transfer(transfer_id: str) -> bool:
    log.info("Cancelling transfer: %s", transfer_id)
    tg.cancel_transfer(transfer_id)
    return True


# ───────────────────────────────── upload ─────────────────────────────────


async def cmd_upload_file(
    path: str,
    folder_id: int | None,
    transfer_id: str | None,
) -> str:
    from . import dedup as dedup_mod
    from . import vault as vault_mod

    p = Path(path)
    if not p.exists():
        raise RuntimeError(f"File not found: {path}")

    # Vault encryption: encrypt file before upload if folder is an unlocked vault
    encrypted_tmp: str | None = None
    if folder_id and vault_mod.is_vault(folder_id):
        if not vault_mod.is_unlocked(folder_id):
            raise RuntimeError("Vault is locked. Unlock it first.")
        encrypted_tmp = vault_mod.encrypt_file(path, folder_id)
        path = encrypted_tmp
        p = Path(path)

    size = p.stat().st_size
    ok, err = get_manager().can_transfer(size)
    if not ok:
        raise RuntimeError(err or "Bandwidth limit hit")

    tid = transfer_id or ""

    state = tg.get_state()
    client = state.client
    if client is None:
        log.info("[MOCK] uploaded %s → %s", path, folder_id)
        get_manager().add_up(size)
        return "Mock upload successful"

    if tid:
        bus.emit(
            "upload-progress",
            {
                "id": tid,
                "percent": 0,
                "uploaded_bytes": 0,
                "total_bytes": size,
                "speed_bytes_per_sec": 0,
            },
        )

    if tg.is_cancelled(tid):
        tg.clear_cancellation(tid)
        raise RuntimeError("Transfer cancelled")

    last_emit_time = time.monotonic()
    last_emit_bytes = 0

    def progress_cb(uploaded: int, total: int) -> None:
        nonlocal last_emit_time, last_emit_bytes
        if tg.is_cancelled(tid):
            raise asyncio.CancelledError("upload cancelled")

        if not tid:
            return
        now = time.monotonic()
        if now - last_emit_time < _PROGRESS_INTERVAL_SECS and uploaded < total:
            return

        dt = max(now - last_emit_time, 1e-6)
        speed = int((uploaded - last_emit_bytes) / dt)
        percent = min(99, int(uploaded * 100 / total)) if total else 0

        bus.emit(
            "upload-progress",
            {
                "id": tid,
                "percent": percent,
                "uploaded_bytes": uploaded,
                "total_bytes": total,
                "speed_bytes_per_sec": max(speed, 0),
            },
        )
        last_emit_time = now
        last_emit_bytes = uploaded

    peer = await tg.resolve_peer(client, folder_id)
    file_name = Path(path).name

    try:
        await client.send_file(
            peer,
            file=path,
            caption="",
            file_name=file_name,
            force_document=True,
            progress_callback=progress_cb,
        )
    except asyncio.CancelledError:
        tg.clear_cancellation(tid)
        raise RuntimeError("Transfer cancelled") from None
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(tg.map_error(exc)) from exc

    get_manager().add_up(size)

    if tid:
        bus.emit(
            "upload-progress",
            {
                "id": tid,
                "percent": 100,
                "uploaded_bytes": size,
                "total_bytes": size,
                "speed_bytes_per_sec": 0,
            },
        )

    # Store file hash for duplicate detection
    try:
        original_path = encrypted_tmp or path
        # Use the original file path for hashing (not the encrypted one)
        src_path = path if not encrypted_tmp else str(Path(path))
        file_hash = dedup_mod.compute_file_hash(src_path if not encrypted_tmp else original_path)
        dedup_mod.store_hash(file_hash, folder_id, 0, file_name, size)
    except Exception:
        pass  # non-critical

    # Cleanup encrypted temp file
    if encrypted_tmp:
        with contextlib.suppress(OSError):
            Path(encrypted_tmp).unlink()

    return "File uploaded successfully"


# ──────────────────────────────── download ────────────────────────────────


async def cmd_download_file(
    message_id: int,
    save_path: str,
    folder_id: int | None,
    transfer_id: str | None = None,
) -> str:
    tid = transfer_id or ""

    # Sanitize: ensure the resolved save_path doesn't escape its parent directory
    save_p = Path(save_path)
    parent = save_p.parent.resolve()
    # Resolve the full path and verify it's still within the intended parent
    resolved = save_p.resolve()
    if not str(resolved).startswith(str(parent)):
        raise RuntimeError("Invalid save path: path traversal detected")

    state = tg.get_state()
    client = state.client
    if client is None:
        log.info(
            "[MOCK] download msg=%s folder=%s -> %s", message_id, folder_id, save_path
        )
        with Path(save_path).open("wb") as fh:
            fh.write(b"Mock Content")
        return "Download successful"

    peer = await tg.resolve_peer(client, folder_id)

    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        raise RuntimeError("Message not found or has no media")

    total_size = tg.media_total_size(msg)
    if total_size > 0:
        ok, err = get_manager().can_transfer(total_size)
        if not ok:
            raise RuntimeError(err or "Bandwidth limit hit")

    if tid:
        bus.emit(
            "download-progress",
            {
                "id": tid,
                "percent": 0,
                "uploaded_bytes": 0,
                "total_bytes": total_size,
                "speed_bytes_per_sec": 0,
            },
        )

    last_emit_time = time.monotonic()
    last_emit_bytes = 0

    def progress_cb(received: int, total: int) -> None:
        nonlocal last_emit_time, last_emit_bytes
        if tg.is_cancelled(tid):
            raise asyncio.CancelledError("download cancelled")

        if not tid:
            return
        now = time.monotonic()
        if now - last_emit_time < _PROGRESS_INTERVAL_SECS and received < total:
            return
        dt = max(now - last_emit_time, 1e-6)
        speed = int((received - last_emit_bytes) / dt)
        percent = min(100, int(received * 100 / total)) if total else 0
        bus.emit(
            "download-progress",
            {
                "id": tid,
                "percent": percent,
                "uploaded_bytes": received,
                "total_bytes": total,
                "speed_bytes_per_sec": max(speed, 0),
            },
        )
        last_emit_time = now
        last_emit_bytes = received

    try:
        await client.download_media(msg, file=save_path, progress_callback=progress_cb)
    except asyncio.CancelledError:
        tg.clear_cancellation(tid)
        with contextlib.suppress(OSError):
            Path(save_path).unlink()
        raise RuntimeError("Transfer cancelled") from None
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Download chunk error: {exc}") from exc

    if total_size > 0:
        get_manager().add_down(total_size)

    if tid:
        bus.emit(
            "download-progress",
            {
                "id": tid,
                "percent": 100,
                "uploaded_bytes": total_size,
                "total_bytes": total_size,
                "speed_bytes_per_sec": 0,
            },
        )

    # Vault decryption: decrypt file after download if folder is an unlocked vault
    from . import vault as vault_mod
    if folder_id and vault_mod.is_vault(folder_id) and vault_mod.is_unlocked(folder_id):
        try:
            decrypted_tmp = vault_mod.decrypt_file(save_path, folder_id)
            # Replace the encrypted file with the decrypted one
            import shutil
            shutil.move(decrypted_tmp, save_path)
        except Exception as exc:
            log.warning("Vault decryption failed: %s", exc)

    return "Download successful"


# ──────────────────────────────── delete ────────────────────────────────


async def cmd_delete_file(message_id: int, folder_id: int | None) -> bool:
    state = tg.get_state()
    client = state.client
    if client is None:
        log.info("[MOCK] delete msg=%s folder=%s", message_id, folder_id)
        return True

    peer = await tg.resolve_peer(client, folder_id)
    await client.delete_messages(peer, [int(message_id)])
    return True


# ───────────────────────────────── move ─────────────────────────────────


async def cmd_move_files(
    message_ids: list[int],
    source_folder_id: int | None,
    target_folder_id: int | None,
) -> bool:
    if source_folder_id == target_folder_id:
        return True

    state = tg.get_state()
    client = state.client
    if client is None:
        log.info(
            "[MOCK] move %s from %s to %s",
            message_ids,
            source_folder_id,
            target_folder_id,
        )
        return True

    src = await tg.resolve_peer(client, source_folder_id)
    target = await tg.resolve_peer(client, target_folder_id)
    ids = [int(i) for i in message_ids]

    try:
        await client.forward_messages(target, ids, src)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Forward failed: {exc}") from exc

    try:
        await client.delete_messages(src, ids)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Delete original failed: {exc}") from exc

    return True


async def cmd_get_files_cached(
    folder_id: int | None,
    limit: int = 100,
    offset_id: int = 0,
) -> dict[str, Any]:
    from . import cache

    cached = cache.get_cached_files(folder_id)
    if cached:
        return {"files": cached, "next_offset_id": 0, "from_cache": True}

    result = await cmd_get_files(folder_id, limit=limit, offset_id=offset_id)
    if result["files"]:
        cache.upsert_files(folder_id, result["files"])
    result["from_cache"] = False
    return result


__all__ = [
    "cmd_get_files",
    "cmd_get_files_cached",
    "cmd_upload_file",
    "cmd_download_file",
    "cmd_delete_file",
    "cmd_move_files",
    "cmd_search_global",
    "cmd_cancel_transfer",
]
