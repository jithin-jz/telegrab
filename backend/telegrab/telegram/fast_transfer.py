# Copyright (C) 2021 Tulir Asokan
# Adapted for Telegrab
from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import math
from collections.abc import AsyncGenerator, Awaitable
from pathlib import Path
from typing import (
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

    async def disconnect(self) -> None:
        if self.previous:
            await self.previous
        return await self.sender.disconnect()


class ParallelTransferrer:
    client: TelegramClient
    loop: asyncio.AbstractEventLoop
    dc_id: int
    senders: list[DownloadSender | UploadSender] | None
    auth_key: AuthKey
    upload_ticker: int

    def __init__(self, client: TelegramClient, dc_id: int | None = None) -> None:
        self.client = client
        self.loop = self.client.loop
        self.dc_id = dc_id or self.client.session.dc_id
        self.auth_key = (
            None
            if dc_id and self.client.session.dc_id != dc_id
            else self.client.session.auth_key
        )
        self.senders = None
        self.upload_ticker = 0

    async def _cleanup(self) -> None:
        if self.senders:
            await asyncio.gather(*[sender.disconnect() for sender in self.senders])
        self.senders = None

    @staticmethod
    def _get_connection_count(file_size: int, max_count: int = 20) -> int:
        """Return an adaptive connection count based on file size.

        Telegram supports up to 20 parallel connections per DC.
        Larger files benefit from more connections due to higher
        per-connection overhead amortisation.
        """
        if file_size > 100 * 1024 * 1024:  # > 100 MB → 20 connections
            return 20
        if file_size > 10 * 1024 * 1024:  # > 10 MB  → 16 connections
            return 16
        if file_size > 1 * 1024 * 1024:  # > 1 MB   → 8 connections
            return 8
        return 4  # small files — 4 is sufficient

    async def _init_download(
        self, connections: int, file: TypeLocation, part_count: int, part_size: int
    ) -> None:
        minimum, remainder = divmod(part_count, connections)

        def get_part_count() -> int:
            nonlocal remainder
            if remainder > 0:
                remainder -= 1
                return minimum + 1
            return minimum

        # The first cross-DC sender will export+import the authorization, so we always create it
        # before creating any other senders.
        self.senders = [
            await self._create_download_sender(
                file, 0, part_size, connections * part_size, get_part_count()
            ),
            *await asyncio.gather(
                *[
                    self._create_download_sender(
                        file, i, part_size, connections * part_size, get_part_count()
                    )
                    for i in range(1, connections)
                ]
            ),
        ]

    async def _create_download_sender(
        self,
        file: TypeLocation,
        index: int,
        part_size: int,
        stride: int,
        part_count: int,
    ) -> DownloadSender:
        return DownloadSender(
            self.client,
            await self._create_sender(),
            file,
            index * part_size,
            part_size,
            stride,
            part_count,
        )

    async def _init_upload(
        self, connections: int, file_id: int, part_count: int, big: bool
    ) -> None:
        self.senders = [
            await self._create_upload_sender(file_id, part_count, big, 0, connections),
            *await asyncio.gather(
                *[
                    self._create_upload_sender(file_id, part_count, big, i, connections)
                    for i in range(1, connections)
                ]
            ),
        ]

    async def _create_upload_sender(
        self, file_id: int, part_count: int, big: bool, index: int, stride: int
    ) -> UploadSender:
        return UploadSender(
            self.client,
            await self._create_sender(),
            file_id,
            part_count,
            big,
            index,
            stride,
            loop=self.loop,
        )

    async def _create_sender(self) -> MTProtoSender:
        dc = await self.client._get_dc(self.dc_id)
        sender = MTProtoSender(self.auth_key, loggers=self.client._log)
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
            log.debug("Exporting auth to DC %d", self.dc_id)
            auth = await self.client(ExportAuthorizationRequest(self.dc_id))
            self.client._init_request.query = ImportAuthorizationRequest(
                id=auth.id, bytes=auth.bytes
            )
            req = InvokeWithLayerRequest(LAYER, self.client._init_request)
            await sender.send(req)
            self.auth_key = sender.auth_key
        return sender

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
        part_count = (file_size + part_size - 1) // part_size
        is_large = file_size > 10 * 1024 * 1024
        await self._init_upload(connection_count, file_id, part_count, is_large)
        return part_size, part_count, is_large

    async def upload(self, part: bytes) -> None:
        await self.senders[self.upload_ticker].next(part)
        self.upload_ticker = (self.upload_ticker + 1) % len(self.senders)

    async def finish_upload(self) -> None:
        await self._cleanup()

    async def download(
        self,
        file: TypeLocation,
        file_size: int,
        part_size_kb: float | None = None,
        connection_count: int | None = None,
    ) -> AsyncGenerator[bytes, None]:
        connection_count = connection_count or self._get_connection_count(file_size)
        # Use 512 KB parts for anything over 1 MB to minimise round-trips.
        part_size_kb = part_size_kb or (
            512.0
            if file_size > 1 * 1024 * 1024
            else utils.get_appropriated_part_size(file_size)
        )
        part_size = int(part_size_kb * 1024)
        part_count = math.ceil(file_size / part_size)
        log.debug(
            "Starting parallel download: %d connections, %d KB parts, %d parts, file=%s",
            connection_count,
            int(part_size_kb),
            part_count,
            str(file),
        )
        await self._init_download(connection_count, file, part_count, part_size)

        part = 0
        while part < part_count:
            # Launch all sender tasks concurrently, then collect with gather
            # so we never block on one while others are already done.
            tasks = [self.loop.create_task(sender.next()) for sender in self.senders]
            results = await asyncio.gather(*tasks)
            for data in results:
                if not data:
                    log.debug("Parallel download finished, cleaning up connections")
                    await self._cleanup()
                    return
                yield data
                part += 1
                log.debug("Part %d/%d downloaded", part, part_count)
                if part >= part_count:
                    break

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
        try:
            filename = Path(file_path).name
        except Exception:
            filename = "upload"

    hash_md5 = hashlib.md5()
    uploader = ParallelTransferrer(client)
    part_size, part_count, is_large = await uploader.init_upload(file_id, file_size)

    buffer = bytearray()
    bytes_uploaded = 0

    async with aiofiles.open(file_path, "rb") as f:
        while True:
            # Non-blocking read — does not stall the event loop
            data = await f.read(part_size)
            if not data:
                break

            if progress_callback:
                r = progress_callback(bytes_uploaded, file_size)
                if inspect.isawaitable(r):
                    await r

            if not is_large:
                hash_md5.update(data)

            if len(buffer) == 0 and len(data) == part_size:
                await uploader.upload(data)
                bytes_uploaded += len(data)
                continue

            new_len = len(buffer) + len(data)
            if new_len >= part_size:
                cutoff = part_size - len(buffer)
                buffer.extend(data[:cutoff])
                await uploader.upload(bytes(buffer))
                bytes_uploaded += part_size
                buffer.clear()
                buffer.extend(data[cutoff:])
            else:
                buffer.extend(data)

    if len(buffer) > 0:
        await uploader.upload(bytes(buffer))
        bytes_uploaded += len(buffer)

    await uploader.finish_upload()
    if is_large:
        return InputFileBig(file_id, part_count, filename), file_size
    return InputFile(file_id, part_count, filename, hash_md5.hexdigest()), file_size


async def download_file(
    client: TelegramClient,
    location: TypeLocation,
    out: BinaryIO,
    progress_callback: callable = None,
) -> BinaryIO:
    """Download a file from Telegram using async I/O throughout.

    Uses aiofiles for non-blocking disk writes so the event loop is never
    stalled while flushing chunks to disk.
    """
    size = location.size
    dc_id, location = utils.get_input_location(location)
    downloader = ParallelTransferrer(client, dc_id)
    downloaded = downloader.download(location, size)

    async with aiofiles.open(out.name, "wb") as af:
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
