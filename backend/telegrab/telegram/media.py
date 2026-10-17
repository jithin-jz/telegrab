"""Helpers for converting Telethon messages/media into the metadata dicts
the React frontend expects (see `frontend/src/types/index.ts`).

Also exposes a shared download semaphore for limiting concurrent Telegram
download operations (thumbnails, previews, etc.)."""

from __future__ import annotations

import asyncio
import weakref
from pathlib import Path
from typing import Any

from telethon.tl.types import (
    Document,
    DocumentAttributeFilename,
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
)

# Limit concurrent small Telegram downloads (thumbnails/previews) to 4.
# Semaphores bind to the loop they are first used on, and the runtime may
# restart its loop after a crash — so keep one per loop.
_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def get_download_semaphore() -> asyncio.Semaphore:
    """Return the shared semaphore for limiting concurrent Telegram downloads."""
    loop = asyncio.get_running_loop()
    sem = _semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(4)
        _semaphores[loop] = sem
    return sem


def photo_size(photo: Any) -> int:
    """Byte size of the largest variant of a photo (what downloads fetch)."""
    best = 0
    for variant in getattr(photo, "sizes", None) or []:
        size = getattr(variant, "size", None)
        if isinstance(size, int):
            best = max(best, size)
        progressive = getattr(variant, "sizes", None)  # PhotoSizeProgressive
        if progressive:
            best = max(best, max(progressive))
    return best


def file_metadata_from_message(
    msg: Message, folder_id: int | None
) -> dict[str, Any] | None:
    """Return a `FileMetadata` dict for a Telethon message, or None if the
    message has no usable media."""

    media = getattr(msg, "media", None)
    if media is None:
        return None

    name, size, mime, ext = _extract_media_info(media)
    if name is None:
        return None

    return {
        "id": int(msg.id),
        "folder_id": folder_id,
        "name": name,
        "size": int(size),
        "mime_type": mime,
        "file_ext": ext,
        "created_at": msg.date.isoformat() if msg.date else "",
        "icon_type": "file",
    }


def _extract_media_info(media: Any) -> tuple[str | None, int, str | None, str | None]:
    """Returns (name, size, mime_type, ext) — all but size may be None."""

    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if not isinstance(doc, Document):
            return (None, 0, None, None)
        name = filename_from_document(doc) or "file"
        size = int(getattr(doc, "size", 0) or 0)
        mime = getattr(doc, "mime_type", None)
        ext_raw = Path(name).suffix.lstrip(".")
        ext = ext_raw or None
        return name, size, mime, ext

    if isinstance(media, MessageMediaPhoto):
        photo = getattr(media, "photo", None)
        if not isinstance(photo, Photo):
            return (None, 0, None, None)
        return (f"Photo_{photo.id}.jpg", photo_size(photo), "image/jpeg", "jpg")

    return (None, 0, None, None)


def filename_from_document(doc: Document) -> str | None:
    for attr in getattr(doc, "attributes", []) or []:
        if isinstance(attr, DocumentAttributeFilename):
            return attr.file_name
    return None


def media_total_size(msg: Message) -> int:
    """Best-effort byte size for bandwidth accounting."""
    media = getattr(msg, "media", None)
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if isinstance(doc, Document):
            return int(getattr(doc, "size", 0) or 0)
    if isinstance(media, MessageMediaPhoto):
        return photo_size(getattr(media, "photo", None))
    return 0


def mime_type_from_message(msg: Message) -> str:
    media = getattr(msg, "media", None)
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if isinstance(doc, Document):
            return getattr(doc, "mime_type", None) or "application/octet-stream"
    if isinstance(media, MessageMediaPhoto):
        return "image/jpeg"
    return "application/octet-stream"


def filename_from_message(msg: Message) -> str:
    media = getattr(msg, "media", None)
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        if isinstance(doc, Document):
            return filename_from_document(doc) or "file"
    if isinstance(media, MessageMediaPhoto):
        photo = getattr(media, "photo", None)
        return f"Photo_{photo.id}.jpg" if isinstance(photo, Photo) else "Photo.jpg"
    return "download"
