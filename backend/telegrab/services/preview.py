"""Preview / thumbnail / cache-clean use cases.

Mirrors `src-tauri/src/commands/preview.rs`.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import shutil
from pathlib import Path

from telethon.tl.types import Document, MessageMediaDocument, MessageMediaPhoto

from .. import telegram as tg
from ..config import preview_cache_dir, thumbnail_cache_dir
from ..infra import get_manager
from ..telegram.media import filename_from_document

log = logging.getLogger(__name__)

PREVIEW_CACHE_MAX_FILES = 30
PREVIEW_CACHE_MAX_TOTAL_BYTES = 80 * 1024 * 1024
_MAX_BASE64_SIZE = 2 * 1024 * 1024  # 2MB

# Inflight dedup: (folder_id, message_id) -> Future
_inflight: dict[tuple[int | None, int], asyncio.Future[str]] = {}

# Limit concurrent Telegram download operations for thumbnails/previews
_thumbnail_semaphore = asyncio.Semaphore(4)

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg"}
_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/svg+xml": "svg",
    "video/mp4": "mp4",
}
_EXT_TO_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
}


def _prune_preview_cache(cache_dir: Path) -> None:
    try:
        files: list[tuple[Path, float, int]] = []
        for entry in cache_dir.iterdir():
            if not entry.is_file():
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            files.append((entry, stat.st_mtime, stat.st_size))
        files.sort(key=lambda t: t[1])  # oldest first

        total = sum(size for _, _, size in files)
        while files and (
            len(files) > PREVIEW_CACHE_MAX_FILES
            or total > PREVIEW_CACHE_MAX_TOTAL_BYTES
        ):
            path, _, size = files.pop(0)
            try:
                path.unlink()
                total -= size
            except OSError:
                pass
    except FileNotFoundError:
        pass


def _ext_from_media(media) -> str:
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if isinstance(doc, Document):
            name = filename_from_document(doc) or ""
            ext = Path(name).suffix.lstrip(".").lower()
            if ext:
                return ext
            mime = getattr(doc, "mime_type", None)
            if mime in _MIME_TO_EXT:
                return _MIME_TO_EXT[mime]
        return "bin"
    if isinstance(media, MessageMediaPhoto):
        return "jpg"
    return "bin"


async def cmd_get_preview(message_id: int, folder_id: int | None) -> str:
    key = (folder_id, message_id)

    # Inflight dedup: await existing fetch if in progress
    if key in _inflight:
        try:
            return await _inflight[key]
        except Exception:
            # Previous attempt failed — remove and retry below
            _inflight.pop(key, None)

    loop = asyncio.get_event_loop()
    fut: asyncio.Future[str] = loop.create_future()
    _inflight[key] = fut
    try:
        result = await _do_get_preview(message_id, folder_id)
        fut.set_result(result)
        return result
    except Exception as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise
    finally:
        _inflight.pop(key, None)


async def _do_get_preview(message_id: int, folder_id: int | None) -> str:
    cache_dir = preview_cache_dir()
    _prune_preview_cache(cache_dir)
    log.info("Preview request: msg_id=%s", message_id)

    state = tg.get_state()
    client = state.client
    if client is None:
        return ""

    peer = await tg.resolve_peer(client, folder_id)
    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        raise RuntimeError("File not found or failed to download")

    ext = _ext_from_media(msg.media).lower()
    folder_key = str(folder_id) if folder_id is not None else "home"
    save_path = cache_dir / f"{folder_key}_{message_id}.{ext}"

    if save_path.exists():
        log.info("Preview cache hit for %s", message_id)
    else:
        size = tg.media_total_size(msg)
        log.info("Downloading preview... size=%s", size)
        ok, err = get_manager().can_transfer(size or 0)
        if not ok:
            log.warning("Bandwidth limit hit for preview: %s", err)
            raise RuntimeError("Bandwidth limit reached")
        try:
            async with _thumbnail_semaphore:
                result = await client.download_media(msg, file=str(save_path))
            if result is None:
                raise RuntimeError("Download returned None")
        except Exception as exc:  # noqa: BLE001
            # Clean up partial file
            if save_path.exists():
                save_path.unlink(missing_ok=True)
            log.error("Preview download error: %s", exc)
            raise RuntimeError(f"Download failed: {exc}") from exc
        if not save_path.exists() or save_path.stat().st_size == 0:
            save_path.unlink(missing_ok=True)
            raise RuntimeError("Download produced empty file")
        get_manager().add_down(size or 0)
        _prune_preview_cache(cache_dir)

    if ext in _IMAGE_EXTENSIONS:
        try:
            data = save_path.read_bytes()
        except OSError as exc:
            log.error("Failed to read preview: %s", exc)
            raise RuntimeError("File not found or failed to download") from exc
        mime = _EXT_TO_MIME.get(ext, "image/jpeg")
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"

    return str(save_path)


async def cmd_clean_cache() -> None:
    """Wipe the preview cache directory."""
    cache_dir = preview_cache_dir()
    try:
        shutil.rmtree(cache_dir, ignore_errors=True)
    finally:
        cache_dir.mkdir(parents=True, exist_ok=True)


async def cmd_get_thumbnail(message_id: int, folder_id: int | None) -> str:
    cache_dir = thumbnail_cache_dir()
    _prune_preview_cache(cache_dir)

    try:
        for entry in cache_dir.iterdir():
            if entry.is_file() and entry.name.startswith(f"{message_id}."):
                ext = entry.suffix.lstrip(".").lower() or "jpg"
                mime = _EXT_TO_MIME.get(ext, "image/jpeg")
                try:
                    data = entry.read_bytes()
                except OSError:
                    continue
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
    except FileNotFoundError:
        pass

    state = tg.get_state()
    client = state.client
    if client is None:
        return ""

    peer = await tg.resolve_peer(client, folder_id)
    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        return ""

    media = msg.media
    if isinstance(media, MessageMediaPhoto):
        ext = "jpg"
    elif isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if not isinstance(doc, Document):
            return ""
        # Check if the document has any thumbnails (photos, videos, etc.)
        thumbs = getattr(doc, "thumbs", None)
        if not thumbs:
            return ""
        ext = "jpg"
    else:
        return ""

    save_path = cache_dir / f"{message_id}.{ext}"
    try:
        async with _thumbnail_semaphore:
            await client.download_media(msg, file=str(save_path), thumb=-1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Thumbnail download failed: %s", exc)
        return ""

    try:
        data = save_path.read_bytes()
    except OSError:
        return ""
    mime = _EXT_TO_MIME.get(ext, "image/jpeg")
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


__all__ = ["cmd_get_preview", "cmd_clean_cache", "cmd_get_thumbnail"]
