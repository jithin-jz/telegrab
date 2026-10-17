"""File-operation use cases.

Progress events fire through `telegrab.infra.events.bus` on the
`upload-progress` / `download-progress` channels. Cancellation is
cooperative — the progress callbacks raise `TransferCancelledError` when the
user has marked the transfer cancelled.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from pathlib import Path
from typing import Any

from telethon.tl import types

from .. import telegram as tg
from ..infra import bus, get_manager
from . import localdb, require_client
from .network import retry_with_backoff

log = logging.getLogger(__name__)

# Throttle progress events so we don't drown the JS bus.
_PROGRESS_INTERVAL_SECS = 0.25

# Messages scanned per page. Not every message is a file (service messages,
# text), so a page may hold fewer files than this.
DEFAULT_PAGE_SIZE = 100
_MAX_PAGE_SIZE = 500

_SEARCH_RESULTS_PER_FOLDER = 50
_SEARCH_CONCURRENCY = 4

_CANCELLED_MSG = "Transfer cancelled"


def _emit_progress(event: str, payload: dict) -> None:
    """Schedule a progress event on the running event loop without blocking.

    bus.emit() posts across the pywebview JS bridge. Deferring it with
    call_soon means the transfer coroutine is never stalled waiting for the
    bridge round-trip to complete.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon(bus.emit, event, payload)
    except RuntimeError:
        # Fallback if called from outside the loop (e.g. tests)
        bus.emit(event, payload)


# ───────────────────────────── filename safety ─────────────────────────────

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MAX_NAME_LEN = 200


def safe_filename(name: str) -> str:
    """Make a Telegram-provided file name safe to create on any OS."""
    cleaned = _INVALID_CHARS.sub("_", name or "").strip().rstrip(". ")
    cleaned = cleaned.replace("..", "_")
    if not cleaned:
        cleaned = "download"
    stem, dot, ext = cleaned.rpartition(".")
    if not dot:
        stem, ext = cleaned, ""
    if stem.upper() in _RESERVED_NAMES:
        stem = f"_{stem}"
    if len(cleaned) > _MAX_NAME_LEN:
        ext = ext[:16]
        stem = stem[: _MAX_NAME_LEN - len(ext) - 1]
    return f"{stem}.{ext}" if ext else stem


def unique_path(path: Path) -> Path:
    """Return `path`, or `name (n).ext` if a file with that name exists."""
    if not path.exists():
        return path
    for n in range(1, 10_000):
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many files named {path.name} in {path.parent}")


def _validate_save_path(save_path: str) -> Path:
    p = Path(save_path)
    if not p.is_absolute():
        raise RuntimeError("Invalid save path: must be absolute")
    if ".." in p.parts:
        raise RuntimeError("Invalid save path: path traversal detected")
    if not p.parent.is_dir():
        raise RuntimeError(f"Folder does not exist: {p.parent}")
    return p


# ─────────────────────────────── listings ───────────────────────────────


async def cmd_get_files(
    folder_id: int | None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset_id: int = 0,
) -> dict[str, Any]:
    """Return one page of files plus the cursor for the next page.

    ``next_offset_id`` is the id of the last *message* scanned (not the last
    file), so pages containing text/service messages don't end pagination
    early. It is 0 when there are no more messages.
    """
    client = require_client()

    if limit <= 0 or limit > _MAX_PAGE_SIZE:
        limit = _MAX_PAGE_SIZE

    peer = await tg.resolve_peer(client, folder_id)
    files: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"limit": limit}
    if offset_id > 0:
        kwargs["offset_id"] = offset_id

    scanned = 0
    last_id = 0
    async for msg in client.iter_messages(peer, **kwargs):
        scanned += 1
        last_id = int(msg.id)
        meta = tg.file_metadata_from_message(msg, folder_id)
        if meta is not None:
            files.append(meta)

    return {"files": files, "next_offset_id": last_id if scanned >= limit else 0}


async def cmd_search_global(
    query: str, folder_ids: list[int] | None = None
) -> list[dict[str, Any]]:
    """Search file names across Saved Messages and the Telegrab folders.

    Only Telegrab storage is searched — never the user's other chats.
    """
    client = require_client()
    query = (query or "").strip()
    if not query:
        return []

    targets: list[int | None] = [None]
    ids = folder_ids if folder_ids is not None else sorted(tg.get_state().folder_ids)
    targets.extend(int(i) for i in ids)

    sem = asyncio.Semaphore(_SEARCH_CONCURRENCY)

    async def _search(folder_id: int | None) -> list[dict[str, Any]]:
        async with sem:
            try:
                peer = await tg.resolve_peer(client, folder_id)
                out = []
                async for msg in client.iter_messages(
                    peer, search=query, limit=_SEARCH_RESULTS_PER_FOLDER
                ):
                    meta = tg.file_metadata_from_message(msg, folder_id)
                    if meta is not None:
                        out.append(meta)
                return out
            except Exception as exc:  # noqa: BLE001
                log.debug("Search in folder %s failed: %s", folder_id, exc)
                return []

    results = await asyncio.gather(*[_search(f) for f in targets])
    merged = [m for chunk in results for m in chunk]
    merged.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return merged


# ─────────────────────────── transfer cancellation ───────────────────────────


async def cmd_cancel_transfer(transfer_id: str) -> bool:
    log.info("Cancelling transfer: %s", transfer_id)
    tg.cancel_transfer(transfer_id)
    return True


class _Progress:
    """Throttled progress reporter shared by uploads and downloads."""

    def __init__(self, event: str, transfer_id: str, total: int) -> None:
        self.event = event
        self.tid = transfer_id
        self.total = total
        self.last_time = time.monotonic()
        self.last_bytes = 0

    def emit(self, done: int, total: int, *, final: bool = False) -> None:
        if not self.tid:
            return
        now = time.monotonic()
        dt = max(now - self.last_time, 1e-6)
        speed = int((done - self.last_bytes) / dt)
        percent = 100 if final else (min(99, int(done * 100 / total)) if total else 0)
        _emit_progress(
            self.event,
            {
                "id": self.tid,
                "percent": percent,
                "uploaded_bytes": done,
                "total_bytes": total,
                "speed_bytes_per_sec": max(speed, 0),
            },
        )
        self.last_time = now
        self.last_bytes = done

    def callback(self, done: int, total: int) -> None:
        if tg.is_cancelled(self.tid):
            raise tg.TransferCancelledError(_CANCELLED_MSG)
        if not self.tid:
            return
        now = time.monotonic()
        if now - self.last_time < _PROGRESS_INTERVAL_SECS and done < total:
            return
        self.emit(done, total)


def _on_flood_wait(seconds: float) -> None:
    """Tell the UI a transfer is paused by a Telegram rate limit."""
    _emit_progress("rate-limited", {"wait_seconds": seconds})


def _emit_transfer_failed(tid: str, bytes_sent: int, reason: str) -> None:
    if tid and bytes_sent > 0:
        bus.emit(
            "transfer-failed",
            {"transferId": tid, "bytesSent": bytes_sent, "reason": reason},
        )


# ───────────────────────────────── upload ─────────────────────────────────


async def cmd_upload_file(
    path: str,
    folder_id: int | None,
    transfer_id: str | None,
) -> str:
    from . import dedup as dedup_mod
    from . import vault as vault_mod

    source = Path(path)
    if not source.is_file():
        raise RuntimeError(f"File not found: {path}")

    client = require_client()
    tid = transfer_id or ""
    # Always the user's original name.
    file_name = source.name
    from ..telegram import fast_transfer

    part_source: fast_transfer.PartSource | None = None

    try:
        if tg.is_cancelled(tid):
            raise tg.TransferCancelledError(_CANCELLED_MSG)

        if await vault_mod.ensure_vault_known(folder_id):
            if not vault_mod.is_unlocked(folder_id):
                raise RuntimeError("Vault is locked. Unlock it first.")
            # Encrypted on the fly as parts are sent — no ciphertext copy on disk.
            part_source = vault_mod.VaultUploadSource(source, folder_id)
        else:
            part_source = fast_transfer.FilePartSource(source)

        size = part_source.size
        ok, err = get_manager().can_transfer(size)
        if not ok:
            raise RuntimeError(err or "Bandwidth limit hit")

        progress = _Progress("upload-progress", tid, size)
        progress.emit(0, size)

        peer = await tg.resolve_peer(client, folder_id)

        async def _do_upload():
            return await fast_transfer.upload_source(
                client,
                part_source,
                file_name,
                progress.callback,
                on_flood_wait=_on_flood_wait,
            )

        try:
            uploaded_file = await retry_with_backoff(
                _do_upload, transfer_id=tid or None
            )

            async def _do_send():
                return await client.send_file(
                    peer,
                    file=uploaded_file,
                    caption="",
                    file_name=file_name,
                    force_document=True,
                )

            sent_msg = await retry_with_backoff(_do_send, transfer_id=tid or None)
        except tg.TransferCancelledError:
            _emit_transfer_failed(tid, progress.last_bytes, "user cancellation")
            raise
        except Exception as exc:
            _emit_transfer_failed(tid, progress.last_bytes, str(exc))
            raise RuntimeError(tg.map_error(exc)) from exc

        get_manager().add_up(size)
        progress.emit(size, size, final=True)
    except tg.TransferCancelledError:
        raise RuntimeError(_CANCELLED_MSG) from None
    finally:
        tg.clear_cancellation(tid)
        if part_source is not None:
            part_source.close()

    # Store file hash for duplicate detection
    try:
        file_hash = await asyncio.to_thread(dedup_mod.compute_file_hash, str(source))
        msg_id = sent_msg.id if sent_msg else 0
        dedup_mod.store_hash(file_hash, folder_id, msg_id, file_name, size)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Dedup hash storage failed for folder_id=%s file=%s: %s",
            folder_id,
            file_name,
            exc,
        )

    return "File uploaded successfully"


# ──────────────────────────────── download ────────────────────────────────


async def cmd_download_file(
    message_id: int,
    save_path: str | None,
    folder_id: int | None,
    transfer_id: str | None = None,
    *,
    dir_path: str | None = None,
    file_name: str | None = None,
) -> str:
    """Download a file and return the path it was saved to.

    Either pass ``save_path`` (a path the user picked in a save dialog —
    overwriting it is intended), or ``dir_path`` + ``file_name``: the name is
    then sanitised and de-duplicated so existing files are never replaced.

    Data is written to ``<target>.part`` and only renamed into place once
    complete (and decrypted, for vaults), so a failed or cancelled download
    never leaves a truncated file that looks real.
    """
    from . import vault as vault_mod

    if save_path:
        target = _validate_save_path(save_path)
        avoid_overwrite = False
    elif dir_path:
        target = _validate_save_path(
            str(Path(dir_path) / safe_filename(file_name or ""))
        )
        avoid_overwrite = True
    else:
        raise RuntimeError("No download destination given")

    client = require_client()
    tid = transfer_id or ""

    is_vault = await vault_mod.ensure_vault_known(folder_id)
    if is_vault and not vault_mod.is_unlocked(folder_id):
        raise RuntimeError("Vault is locked. Unlock it first.")

    peer = await tg.resolve_peer(client, folder_id)
    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        raise RuntimeError("Message not found or has no media")

    total_size = tg.media_total_size(msg)
    if total_size > 0:
        ok, err = get_manager().can_transfer(total_size)
        if not ok:
            raise RuntimeError(err or "Bandwidth limit hit")

    if avoid_overwrite:
        target = unique_path(target)
    partial = target.with_name(target.name + ".part")
    decrypted_partial = target.with_name(target.name + ".dec.part")
    for stale in (partial, decrypted_partial):
        stale.unlink(missing_ok=True)

    progress = _Progress("download-progress", tid, total_size)
    progress.emit(0, total_size)

    try:
        if isinstance(msg.media, types.MessageMediaDocument):
            from ..telegram import fast_transfer

            async def _refetch_document():
                # File references expire; long downloads may outlive them.
                fresh = await client.get_messages(peer, ids=int(message_id))
                if fresh is None or not isinstance(
                    fresh.media, types.MessageMediaDocument
                ):
                    raise RuntimeError("The file was deleted during the download")
                return fresh.media.document

            async def _do_download():
                await fast_transfer.download_file(
                    client,
                    msg.media.document,
                    str(partial),
                    progress.callback,
                    refresh_location=_refetch_document,
                    on_flood_wait=_on_flood_wait,
                )
        else:

            async def _do_download():
                await client.download_media(
                    msg, file=str(partial), progress_callback=progress.callback
                )

        try:
            await retry_with_backoff(_do_download, transfer_id=tid or None)
        except tg.TransferCancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Download failed: {tg.map_error(exc)}") from exc

        if is_vault:
            await asyncio.to_thread(
                vault_mod.decrypt_file, str(partial), folder_id, decrypted_partial
            )
            decrypted_partial.replace(target)
            partial.unlink(missing_ok=True)
        else:
            partial.replace(target)
    except tg.TransferCancelledError:
        raise RuntimeError(_CANCELLED_MSG) from None
    finally:
        tg.clear_cancellation(tid)
        for leftover in (partial, decrypted_partial):
            try:
                leftover.unlink(missing_ok=True)
            except OSError as unlink_err:
                log.warning(
                    "Failed to delete partial file %s: %s", leftover, unlink_err
                )
                if tid:
                    bus.emit(
                        "transfer-failed",
                        {
                            "transferId": tid,
                            "bytesSent": 0,
                            "reason": f"Failed to delete partial file: {unlink_err}",
                        },
                    )

    if total_size > 0:
        get_manager().add_down(total_size)
    progress.emit(total_size, total_size, final=True)
    return str(target)


# ──────────────────────────────── delete ────────────────────────────────


async def cmd_delete_file(message_id: int, folder_id: int | None) -> bool:
    client = require_client()
    peer = await tg.resolve_peer(client, folder_id)
    await client.delete_messages(peer, [int(message_id)])

    # Drop the fingerprint and pin for the deleted file.
    try:
        localdb.forget_messages(folder_id, [int(message_id)])
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to clean local data for deleted file: %s", exc)
    return True


# ───────────────────────────────── move ─────────────────────────────────


async def cmd_move_files(
    message_ids: list[int],
    source_folder_id: int | None,
    target_folder_id: int | None,
) -> bool:
    if source_folder_id == target_folder_id:
        return True

    from . import vault as vault_mod

    client = require_client()
    src_vault = await vault_mod.ensure_vault_known(source_folder_id)
    dst_vault = await vault_mod.ensure_vault_known(target_folder_id)
    if src_vault or dst_vault:
        # Each vault has its own key and normal folders hold plaintext, so a
        # server-side forward would leave files undecryptable or unencrypted.
        raise RuntimeError(
            "Files can't be moved into or out of a vault. "
            "Download them and upload them to the other folder instead."
        )

    src = await tg.resolve_peer(client, source_folder_id)
    target = await tg.resolve_peer(client, target_folder_id)
    ids = [int(i) for i in message_ids]

    try:
        forwarded = await client.forward_messages(target, ids, src)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Forward failed: {tg.map_error(exc)}") from exc

    if not isinstance(forwarded, list):
        forwarded = [forwarded]
    if len([m for m in forwarded if m is not None]) != len(ids):
        # Don't delete originals unless every copy landed.
        raise RuntimeError("Some files could not be copied; originals were kept.")

    try:
        await client.delete_messages(src, ids)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Delete original failed: {tg.map_error(exc)}") from exc

    # Re-point fingerprints at the moved copies; drop the originals' pins.
    from . import dedup as dedup_mod

    for old_id, new_msg in zip(ids, forwarded, strict=False):
        with contextlib.suppress(Exception):
            dedup_mod.move_hash(
                old_id, source_folder_id, int(new_msg.id), target_folder_id
            )
    with contextlib.suppress(Exception):
        localdb.forget_messages(source_folder_id, ids)

    return True


__all__ = [
    "cmd_get_files",
    "cmd_upload_file",
    "cmd_download_file",
    "cmd_delete_file",
    "cmd_move_files",
    "cmd_search_global",
    "cmd_cancel_transfer",
    "safe_filename",
    "unique_path",
]
