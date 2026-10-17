# Copyright (C) 2021 Tulir Asokan
# Adapted for Telegrab
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import inspect
import logging
import math
import time
import weakref
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
)

import aiofiles
from telethon import TelegramClient, helpers, utils
from telethon.crypto import AuthKey
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import (
    ExportAuthorizationRequest,
    ImportAuthorizationRequest,
)
from telethon.tl.functions.upload import (
    GetFileRequest,
    SaveBigFilePartRequest,
    SaveFilePartRequest,
)
from telethon.tl.types import (
    Document,
    InputDocumentFileLocation,
    InputFile,
    InputFileBig,
    InputFileLocation,
    InputPeerPhotoFileLocation,
    InputPhotoFileLocation,
    TypeInputFile,
)

log: logging.Logger = logging.getLogger("telegrab.telegram.fast_transfer")

TypeLocation = (
    Document
    | InputDocumentFileLocation
    | InputPeerPhotoFileLocation
    | InputFileLocation
    | InputPhotoFileLocation
)

# Telegram rejects uploads with more parts than this (4000 × 512 KB = 2 GB;
# Premium accounts get 8000 parts / 4 GB).
MAX_UPLOAD_PARTS = 8000

# Authorizations exported to foreign DCs are reusable for a while. Caching
# them avoids an ExportAuthorization round-trip (and its flood limits) for
# every single cross-DC download.
_EXPORTED_AUTH_TTL = 30 * 60
_exported_auth: weakref.WeakKeyDictionary[
    TelegramClient, dict[int, tuple[AuthKey, float]]
] = weakref.WeakKeyDictionary()
# Exporting mutates the client's shared `_init_request`, so serialise it.
_export_locks: weakref.WeakKeyDictionary[TelegramClient, asyncio.Lock] = (
    weakref.WeakKeyDictionary()
)


def _cached_auth_key(client: TelegramClient, dc_id: int) -> AuthKey | None:
    entry = _exported_auth.get(client, {}).get(dc_id)
    if entry and time.monotonic() - entry[1] < _EXPORTED_AUTH_TTL:
        return entry[0]
    return None


class DownloadSender:
    client: TelegramClient
    sender: MTProtoSender
    request: GetFileRequest
    remaining: int
    stride: int

    def __init__(
        self,
        client: TelegramClient,
        sender: MTProtoSender,
        file: TypeLocation,
        offset: int,
        limit: int,
        stride: int,
        count: int,
    ) -> None:
        self.sender = sender
        self.client = client
        self.request = GetFileRequest(file, offset=offset, limit=limit)
        self.stride = stride
        self.remaining = count

    async def next(self) -> bytes | None:
        if not self.remaining:
            return None
        result = await self.client._call(self.sender, self.request)
        self.remaining -= 1
        self.request.offset += self.stride
        return result.bytes

    def disconnect(self) -> Awaitable[None]:
        return self.sender.disconnect()


class UploadSender:
    client: TelegramClient
    sender: MTProtoSender
    request: SaveFilePartRequest | SaveBigFilePartRequest
    part_count: int
    stride: int
    previous: asyncio.Task | None
    loop: asyncio.AbstractEventLoop

    def __init__(
        self,
        client: TelegramClient,
        sender: MTProtoSender,
        file_id: int,
        part_count: int,
        big: bool,
        index: int,
        stride: int,
        loop: asyncio.AbstractEventLoop,
        on_done: Callable[[int], Any] | None = None,
    ) -> None:
        self.client = client
        self.sender = sender
        self.part_count = part_count
        if big:
            self.request = SaveBigFilePartRequest(file_id, index, part_count, b"")
        else:
            self.request = SaveFilePartRequest(file_id, index, b"")
        self.stride = stride
        self.previous = None
        self.loop = loop
        self.on_done = on_done

    async def next(self, data: bytes) -> None:
        if self.previous:
            await self.previous
        self.previous = self.loop.create_task(self._next(data))

    async def _next(self, data: bytes) -> None:
        self.request.bytes = data
        log.debug(
            "Sending file part %d/%d with %d bytes",
            self.request.file_part,
            self.part_count,
            len(data),
        )
        await self.client._call(self.sender, self.request)
        self.request.file_part += self.stride
        # Report progress only after the server has acknowledged the part,
        # so the reported speed reflects real throughput (not queued bytes).
        if self.on_done:
            r = self.on_done(len(data))
            if inspect.isawaitable(r):
                await r

    async def flush(self) -> None:
        """Wait for the in-flight part and surface its error, if any."""
        if self.previous:
            await self.previous

    async def disconnect(self) -> None:
        # Cleanup must never raise: a failed part has already been reported
        # through flush()/next(), and we still need to close the socket.
        if self.previous and not self.previous.done():
            self.previous.cancel()
        if self.previous:
            with contextlib.suppress(BaseException):
                await self.previous
        await self.sender.disconnect()


class ParallelTransferrer:
    client: TelegramClient
    loop: asyncio.AbstractEventLoop
    dc_id: int
    senders: list[DownloadSender | UploadSender] | None
    auth_key: AuthKey
    upload_ticker: int

    def __init__(self, client: TelegramClient, dc_id: int | None = None) -> None:
        self.client = client
        self.loop = asyncio.get_running_loop()
        self.dc_id = dc_id or self.client.session.dc_id
        self.is_foreign_dc = bool(dc_id) and self.client.session.dc_id != dc_id
        self.auth_key = (
            _cached_auth_key(client, self.dc_id)
            if self.is_foreign_dc
            else self.client.session.auth_key
        )
        self.senders = None
        self.upload_ticker = 0
        self.upload_progress: Callable[[int], Any] | None = None

    async def _cleanup(self) -> None:
        """Disconnect every sender. Never raises."""
        senders, self.senders = self.senders, None
        if senders:
            results = await asyncio.gather(
                *[sender.disconnect() for sender in senders], return_exceptions=True
            )
            for r in results:
                if isinstance(r, BaseException):
                    log.debug("Sender disconnect raised: %r", r)

    @staticmethod
    def _get_connection_count(file_size: int, max_count: int = 20) -> int:
        """Return an adaptive connection count based on file size.

        Telegram supports up to 20 parallel connections per DC.
        Larger files benefit from more connections due to higher
        per-connection overhead amortisation.
        """
        if file_size > 10 * 1024 * 1024:  # > 10 MB  → 20 connections (max)
            return min(20, max_count)
        if file_size > 1 * 1024 * 1024:  # > 1 MB   → 16 connections
            return min(16, max_count)
        if file_size > 256 * 1024:  # > 256 KB → 8 connections
            return min(8, max_count)
        return min(4, max_count)  # tiny files — 4 is plenty

    async def _create_senders(
        self, count: int, factory: Callable[[int], Awaitable[Any]]
    ) -> list[Any]:
        """Create `count` senders; on any failure close the ones that opened.

        The first sender is created alone because, for a foreign DC, it
        exports + imports the authorization the others then reuse.
        """
        first = await factory(0)
        results = await asyncio.gather(
            *[factory(i) for i in range(1, count)], return_exceptions=True
        )
        senders = [first] + [r for r in results if not isinstance(r, BaseException)]
        errors = [r for r in results if isinstance(r, BaseException)]
        if errors:
            self.senders = senders
            await self._cleanup()
            raise errors[0]
        return senders

    async def _init_download(
        self, connections: int, file: TypeLocation, part_count: int, part_size: int
    ) -> None:
        minimum, remainder = divmod(part_count, connections)
        counts = [minimum + (1 if i < remainder else 0) for i in range(connections)]

        async def factory(i: int) -> DownloadSender:
            return DownloadSender(
                self.client,
                await self._create_sender(),
                file,
                i * part_size,
                part_size,
                connections * part_size,
                counts[i],
            )

        self.senders = await self._create_senders(connections, factory)

    async def _init_upload(
        self, connections: int, file_id: int, part_count: int, big: bool
    ) -> None:
        async def factory(i: int) -> UploadSender:
            return UploadSender(
                self.client,
                await self._create_sender(),
                file_id,
                part_count,
                big,
                i,
                connections,
                loop=self.loop,
                on_done=self.upload_progress,
            )

        self.senders = await self._create_senders(connections, factory)

    async def _create_sender(self) -> MTProtoSender:
        dc = await self.client._get_dc(self.dc_id)
        sender = MTProtoSender(self.auth_key, loggers=self.client._log)
        try:
            await sender.connect(
                self.client._connection(
                    dc.ip_address,
                    dc.port,
                    dc.id,
                    loggers=self.client._log,
                    proxy=self.client._proxy,
                )
            )
            if not self.auth_key:
                await self._export_auth(sender)
        except BaseException:
            with contextlib.suppress(BaseException):
                await sender.disconnect()
            raise
        return sender

    async def _export_auth(self, sender: MTProtoSender) -> None:
        lock = _export_locks.get(self.client)
        if lock is None:
            lock = _export_locks[self.client] = asyncio.Lock()
        async with lock:
            log.debug("Exporting auth to DC %d", self.dc_id)
            auth = await self.client(ExportAuthorizationRequest(self.dc_id))
            self.client._init_request.query = ImportAuthorizationRequest(
                id=auth.id, bytes=auth.bytes
            )
            req = InvokeWithLayerRequest(LAYER, self.client._init_request)
            await sender.send(req)
        self.auth_key = sender.auth_key
        _exported_auth.setdefault(self.client, {})[self.dc_id] = (
            self.auth_key,
            time.monotonic(),
        )

    async def init_upload(
        self,
        file_id: int,
        file_size: int,
        part_size_kb: float | None = None,
        connection_count: int | None = None,
    ) -> tuple[int, int, bool]:
        connection_count = connection_count or self._get_connection_count(file_size)
        # Use 512 KB parts for anything over 1 MB to minimise round-trips;
        # fall back to Telethon's recommendation for tiny files.
        part_size_kb = part_size_kb or (
            512.0
            if file_size > 1 * 1024 * 1024
            else utils.get_appropriated_part_size(file_size)
        )
        part_size = int(part_size_kb * 1024)
        part_count = max(1, (file_size + part_size - 1) // part_size)
        if part_count > MAX_UPLOAD_PARTS:
            raise ValueError(
                "File is too large for Telegram (4 GB maximum with Premium, "
                "2 GB otherwise)."
            )
        # Don't spin up more connections than there are parts to send.
        connection_count = max(1, min(connection_count, part_count))
        is_large = file_size > 10 * 1024 * 1024
        await self._init_upload(connection_count, file_id, part_count, is_large)
        return part_size, part_count, is_large

    async def upload(self, part: bytes) -> None:
        await self.senders[self.upload_ticker].next(part)
        self.upload_ticker = (self.upload_ticker + 1) % len(self.senders)

    async def finish_upload(self) -> None:
        """Wait for the final in-flight parts, then close all connections."""
        try:
            await asyncio.gather(*[s.flush() for s in self.senders or []])
        finally:
            await self._cleanup()

    async def abort(self) -> None:
        """Cancel in-flight work and close all connections."""
        await self._cleanup()

    async def download(
        self,
        file: TypeLocation,
        file_size: int,
        part_size_kb: float | None = None,
        connection_count: int | None = None,
    ) -> AsyncGenerator[bytes, None]:
        connection_count = connection_count or self._get_connection_count(file_size)
        # GetFileRequest accepts up to 1 MB per request — use the full size for
        # files over 1 MB to halve the round-trips vs 512 KB parts.
        part_size_kb = part_size_kb or (
            1024.0
            if file_size > 1 * 1024 * 1024
            else utils.get_appropriated_part_size(file_size)
        )
        part_size = int(part_size_kb * 1024)
        part_count = math.ceil(file_size / part_size)
        connection_count = max(1, min(connection_count, part_count))
        log.debug(
            "Starting parallel download: %d connections, %d KB parts, %d parts, file=%s",
            connection_count,
            int(part_size_kb),
            part_count,
            str(file),
        )
        await self._init_download(connection_count, file, part_count, part_size)

        # Pipeline: keep one request in flight per sender at all times.
        # Results are consumed in sender order, and each sender is re-armed
        # for its next part immediately after its result is collected — so a
        # slow connection never stalls the others (no per-round barrier).
        senders = self.senders
        tasks = [self.loop.create_task(s.next()) for s in senders]
        try:
            part = 0
            i = 0
            while part < part_count:
                data = await tasks[i]
                if not data:
                    break
                yield data
                part += 1
                log.debug("Part %d/%d downloaded", part, part_count)
                tasks[i] = self.loop.create_task(senders[i].next())
                i = (i + 1) % len(senders)
        finally:
            # Runs on success, on error, and when the consumer stops early
            # (cancellation) — otherwise every sender's socket would leak.
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            log.debug("Parallel download finished, cleaning up connections")
            await self._cleanup()


async def _internal_transfer_to_telegram(
    client: TelegramClient,
    file_path: str,
    filename: str | None = None,
    progress_callback: callable = None,
) -> tuple[TypeInputFile, int]:
    """Upload a file to Telegram using async I/O throughout.

    Uses aiofiles for non-blocking disk reads so the event loop is never
    stalled during large file uploads.
    """
    file_id = helpers.generate_random_long()
    file_size = Path(file_path).stat().st_size

    if not filename:
        filename = Path(file_path).name or "upload"

    hash_md5 = hashlib.md5()
    uploader = ParallelTransferrer(client)

    # Report progress on server acknowledgement, not when bytes are queued —
    # otherwise the meter spikes as parts are pipelined then stalls while they
    # actually send. `acked` accumulates confirmed bytes across all senders.
    acked = 0

    async def _on_acked(n: int) -> None:
        nonlocal acked
        acked += n
        if progress_callback:
            r = progress_callback(acked, file_size)
            if inspect.isawaitable(r):
                await r

    uploader.upload_progress = _on_acked
    part_size, part_count, is_large = await uploader.init_upload(file_id, file_size)

    buffer = bytearray()
    try:
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                # Non-blocking read — does not stall the event loop
                data = await f.read(part_size)
                if not data:
                    break

                if not is_large:
                    hash_md5.update(data)

                if len(buffer) == 0 and len(data) == part_size:
                    await uploader.upload(data)
                    continue

                new_len = len(buffer) + len(data)
                if new_len >= part_size:
                    cutoff = part_size - len(buffer)
                    buffer.extend(data[:cutoff])
                    await uploader.upload(bytes(buffer))
                    buffer.clear()
                    buffer.extend(data[cutoff:])
                else:
                    buffer.extend(data)

        if len(buffer) > 0:
            await uploader.upload(bytes(buffer))
    except BaseException:
        await uploader.abort()
        raise

    await uploader.finish_upload()
    if is_large:
        return InputFileBig(file_id, part_count, filename), file_size
    return InputFile(file_id, part_count, filename, hash_md5.hexdigest()), file_size


async def download_file(
    client: TelegramClient,
    location: TypeLocation,
    out: BinaryIO | str | Path,
    progress_callback: callable = None,
) -> BinaryIO | str | Path:
    """Download a file from Telegram using async I/O throughout.

    Uses aiofiles for non-blocking disk writes so the event loop is never
    stalled while flushing chunks to disk. *out* may be a path or a file
    object; passing a path avoids opening the same file twice (which raises
    a sharing violation on Windows).
    """
    size = location.size
    dc_id, location = utils.get_input_location(location)
    downloader = ParallelTransferrer(client, dc_id)

    out_path = out if isinstance(out, str | Path) else out.name
    # aclosing() guarantees the generator's cleanup runs as soon as we stop
    # consuming it (e.g. the progress callback raised TransferCancelledError).
    async with (
        contextlib.aclosing(downloader.download(location, size)) as downloaded,
        aiofiles.open(out_path, "wb") as af,
    ):
        bytes_received = 0
        async for x in downloaded:
            await af.write(x)
            bytes_received += len(x)
            if progress_callback:
                r = progress_callback(bytes_received, size)
                if inspect.isawaitable(r):
                    await r

    return out


async def upload_file(
    client: TelegramClient,
    file: BinaryIO,
    filename: str | None = None,
    progress_callback: callable = None,
) -> TypeInputFile:
    """Upload a file object to Telegram.

    Delegates to _internal_transfer_to_telegram using the file's path so
    that aiofiles can re-open it with async I/O.
    """
    return (
        await _internal_transfer_to_telegram(
            client, file.name, filename, progress_callback
        )
    )[0]
