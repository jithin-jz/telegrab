"""Preview / thumbnail / cache-clean use cases."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import re
import shutil
import time
from pathlib import Path

from telethon.tl.types import Document, MessageMediaDocument, MessageMediaPhoto

from .. import telegram as tg
from ..config import preview_cache_dir, thumbnail_cache_dir
from ..infra import get_manager, get_store
from ..telegram.media import filename_from_document, get_download_semaphore
from . import require_client

log = logging.getLogger(__name__)

# Preview cache: bounded by file count and by the user's "cache size limit"
# setting (MB, 0 = unlimited). Thumbnails are tiny and have their own caps.
PREVIEW_CACHE_MAX_FILES = 200
DEFAULT_CACHE_LIMIT_MB = 500
THUMB_CACHE_MAX_FILES = 5000
THUMB_CACHE_MAX_TOTAL_BYTES = 200 * 1024 * 1024
_PRUNE_INTERVAL_SECS = 60.0

# Images larger than this are returned as a file path instead of a data: URI
# so we never push tens of MB of base64 through the JS bridge.
_MAX_BASE64_SIZE = 2 * 1024 * 1024  # 2MB

# Inflight dedup: (folder_id, message_id) -> shared download task
_inflight: dict[tuple[int | None, int], asyncio.Task[str]] = {}
_last_prune: dict[Path, float] = {}

_THUMB_NAME_RE = re.compile(r"^(home|\d+)_\d+\.")

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


def _folder_part(folder_id: int | None) -> str:
    return str(folder_id) if folder_id is not None else "home"


def preview_cache_limit_bytes() -> int:
    """The user's cache size limit setting in bytes (0 = unlimited)."""
    settings = get_store().get("settings") or {}
    try:
        mb = int(settings.get("cacheSizeLimitMB", DEFAULT_CACHE_LIMIT_MB))
    except (TypeError, ValueError, AttributeError):
        mb = DEFAULT_CACHE_LIMIT_MB
    return max(mb, 0) * 1024 * 1024


def _prune_cache(
    cache_dir: Path, max_files: int, max_bytes: int, *, force: bool = False
) -> None:
    """Evict oldest files until under `max_files` and `max_bytes` (0 = no cap)."""
    now = time.monotonic()
    if not force and now - _last_prune.get(cache_dir, 0.0) < _PRUNE_INTERVAL_SECS:
        return
    _last_prune[cache_dir] = now
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
            len(files) > max_files or (max_bytes > 0 and total > max_bytes)
        ):
            path, _, size = files.pop(0)
            try:
                path.unlink()
                total -= size
            except OSError:
                pass
    except FileNotFoundError:
        pass


def _prune_preview_cache(cache_dir: Path, *, force: bool = False) -> None:
    _prune_cache(
        cache_dir, PREVIEW_CACHE_MAX_FILES, preview_cache_limit_bytes(), force=force
    )


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


def _data_uri(path: Path, ext: str) -> str:
    mime = _EXT_TO_MIME.get(ext, "image/jpeg")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def cmd_get_preview(message_id: int, folder_id: int | None) -> str:
    """Return a preview for a file (data: URI for small images, else a path).

    Concurrent requests for the same file share one download. The download
    is shielded so a caller timing out doesn't cancel it for the others.
    """
    key = (folder_id, message_id)
    task = _inflight.get(key)
    if task is None:
        task = asyncio.ensure_future(_do_get_preview(message_id, folder_id))
        _inflight[key] = task
        task.add_done_callback(lambda _t, k=key: _inflight.pop(k, None))
    return await asyncio.shield(task)


async def _do_get_preview(message_id: int, folder_id: int | None) -> str:
    cache_dir = preview_cache_dir()
    log.debug("Preview request: msg_id=%s", message_id)

    from . import vault as vault_mod

    if await vault_mod.ensure_vault_known(folder_id):
        # Vault files are ciphertext on Telegram — previews would be garbage.
        raise RuntimeError(
            "Previews aren't available for vault files. Download it instead."
        )

    client = require_client()
    peer = await tg.resolve_peer(client, folder_id)
    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        raise RuntimeError("File not found or failed to download")

    ext = _ext_from_media(msg.media).lower()
    save_path = cache_dir / f"{_folder_part(folder_id)}_{message_id}.{ext}"

    if save_path.exists():
        log.debug("Preview cache hit for %s", message_id)
        save_path.touch()  # keep recently used previews out of LRU eviction
    else:
        size = tg.media_total_size(msg)
        ok, err = get_manager().can_transfer(size or 0)
        if not ok:
            log.warning("Bandwidth limit hit for preview: %s", err)
            raise RuntimeError("Bandwidth limit reached")
        partial = save_path.with_name(save_path.name + ".part")
        partial.unlink(missing_ok=True)
        try:
            async with get_download_semaphore():
                result = await client.download_media(msg, file=str(partial))
            if result is None:
                raise RuntimeError("Download returned None")
            # Telethon may pick a different name if the target already exists.
            partial = Path(result)
            if not partial.exists() or partial.stat().st_size == 0:
                raise RuntimeError("Download produced empty file")
            partial.replace(save_path)
        except BaseException as exc:
            partial.unlink(missing_ok=True)
            if isinstance(exc, Exception):
                log.error("Preview download error: %s", exc)
                raise RuntimeError(f"Download failed: {exc}") from exc
            raise
        get_manager().add_down(size or 0)
        _prune_preview_cache(cache_dir, force=True)

    if ext in _IMAGE_EXTENSIONS:
        try:
            if save_path.stat().st_size <= _MAX_BASE64_SIZE:
                return await asyncio.to_thread(_data_uri, save_path, ext)
        except OSError as exc:
            log.error("Failed to read preview: %s", exc)
            raise RuntimeError("File not found or failed to download") from exc

    return str(save_path)


def clear_cache_dirs() -> None:
    """Wipe the preview and thumbnail caches."""
    for cache_dir in (preview_cache_dir(), thumbnail_cache_dir()):
        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
        finally:
            cache_dir.mkdir(parents=True, exist_ok=True)


async def cmd_clean_cache() -> None:
    await asyncio.to_thread(clear_cache_dirs)


def cache_size_bytes() -> int:
    total = 0
    for d in (preview_cache_dir(), thumbnail_cache_dir()):
        with contextlib.suppress(OSError):
            for f in d.iterdir():
                if f.is_file():
                    with contextlib.suppress(OSError):
                        total += f.stat().st_size
    return total


def _prune_thumbnails(cache_dir: Path) -> None:
    # Thumbnails used to be keyed by message id alone, which collides across
    # folders (message ids restart in every channel) — drop that old format.
    with contextlib.suppress(OSError):
        for entry in cache_dir.iterdir():
            if entry.is_file() and not _THUMB_NAME_RE.match(entry.name):
                entry.unlink(missing_ok=True)
    _prune_cache(cache_dir, THUMB_CACHE_MAX_FILES, THUMB_CACHE_MAX_TOTAL_BYTES)


async def cmd_get_thumbnail(message_id: int, folder_id: int | None) -> str:
    cache_dir = thumbnail_cache_dir()
    save_path = cache_dir / f"{_folder_part(folder_id)}_{message_id}.jpg"

    if save_path.exists():
        with contextlib.suppress(OSError):
            return await asyncio.to_thread(_data_uri, save_path, "jpg")

    state = tg.get_state()
    client = state.client
    if client is None:
        return ""

    peer = await tg.resolve_peer(client, folder_id)
    msg = await client.get_messages(peer, ids=int(message_id))
    if msg is None or msg.media is None:
        return ""

    media = msg.media
    if isinstance(media, MessageMediaDocument):
        doc = getattr(media, "document", None)
        # Only documents that carry thumbnails (photos, videos, etc.)
        if not isinstance(doc, Document) or not getattr(doc, "thumbs", None):
            return ""
    elif not isinstance(media, MessageMediaPhoto):
        return ""

    try:
        async with get_download_semaphore():
            data = await client.download_media(msg, file=bytes, thumb=-1)
    except Exception as exc:  # noqa: BLE001
        log.warning("Thumbnail download failed: %s", exc)
        return ""
    if not data:
        return ""

    with contextlib.suppress(OSError):
        save_path.write_bytes(data)
    _prune_thumbnails(cache_dir)
    return f"data:image/jpeg;base64,{base64.b64encode(data).decode('ascii')}"


__all__ = [
    "cmd_get_preview",
    "cmd_clean_cache",
    "cmd_get_thumbnail",
    "cache_size_bytes",
    "clear_cache_dirs",
]
