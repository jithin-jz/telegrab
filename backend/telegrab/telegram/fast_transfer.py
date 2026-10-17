# Parallel transfer approach originally adapted from FastTelethon
# (Copyright (C) 2021 Tulir Asokan); rewritten for Telegrab.
"""Pooled, pipelined file transfers over MTProto.

Design
------
* **One connection pool per data centre** (:class:`DcPool`), shared by every
  transfer and by media streaming. Connections are opened on demand, reused
  across files, and closed after :data:`IDLE_TIMEOUT` seconds unused. Small
  files no longer pay for opening a dozen fresh connections each.
* **Pipelining**: each connection carries up to
  :data:`REQUESTS_PER_CONNECTION` requests at once, so a high-latency link
  never sits idle waiting for the previous part's reply.
* **One global budget**: concurrent transfers draw request slots from the same
  pool (at most :data:`MAX_CONNECTIONS_PER_DC` sockets per DC), handed out in
  FIFO order so parallel transfers share bandwidth fairly instead of opening
  20 connections each and tripping Telegram's flood limits.
* **Work queue, not lock-step**: parts are fetched/sent by a group of workers
  and written at their offset, so one slow request never stalls the rest.
* **Per-part retries** with backoff, reconnecting broken connections,
  refreshing expired file references, and sleeping through moderate flood
  waits — a short network blip doesn't restart a multi-GB transfer.

The module only depends on Telethon; callers supply progress/flood callbacks.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import functools
import hashlib
import inspect
import logging
import math
import threading
import time
import weakref
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from telethon import TelegramClient, helpers, utils
from telethon.errors import (
    AuthBytesInvalidError,
    AuthKeyUnregisteredError,
    FileReferenceExpiredError,
    FloodWaitError,
)
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

# ─────────────────────────────── tuning ───────────────────────────────

# Sockets per data centre, shared by all transfers (FastTelethon's proven cap).
MAX_CONNECTIONS_PER_DC = 20
# Requests in flight on one connection. 2 keeps the pipe busy across a
# round-trip without letting one socket hog the bandwidth.
REQUESTS_PER_CONNECTION = 2
# Close pooled connections unused for this long.
IDLE_TIMEOUT = 30.0
_REAPER_INTERVAL = 5.0

# upload.getFile allows up to 1 MB; saveFilePart up to 512 KB.
DOWNLOAD_PART_SIZE = 1024 * 1024
UPLOAD_PART_SIZE = 512 * 1024
# Files above this size must use saveBigFilePart (Telegram rule).
BIG_FILE_THRESHOLD = 10 * 1024 * 1024
# Telegram rejects uploads with more parts than this (4000 × 512 KB = 2 GB;
# Premium accounts get 8000 parts / 4 GB).
MAX_UPLOAD_PARTS = 8000

# Attempts per part before the transfer fails, with exponential backoff.
PART_RETRIES = 8
_BACKOFF_START = 0.5
_BACKOFF_MAX = 15.0
# A single part request may take this long before its connection is
# considered dead (generous: many parts share a slow link).
REQUEST_TIMEOUT = 180.0
# Longer flood waits fail fast with a clear error instead of looking frozen.
MAX_FLOOD_WAIT_SECONDS = 300

# Small files are split into about this many parts (see _part_size_for).
TARGET_PARTS = 16
MIN_PART_SIZE = 64 * 1024

# Media streaming keeps this many 1 MB parts in flight ahead of the player
# (enough for high-bitrate 4K over a high-latency link).
STREAM_READAHEAD = 8

_TRANSIENT_ERRORS = (
    ConnectionError,
    OSError,
    asyncio.IncompleteReadError,
    TimeoutError,
)

FloodCallback = Callable[[float], Any]


class PoolClosedError(RuntimeError):
    """The pool was shut down (logout / exit); never retried."""


ProgressCallback = Callable[[int, int], Any]


async def _maybe_await(value: Any) -> None:
    if inspect.isawaitable(value):
        await value


# ─────────────────────────────── pool ───────────────────────────────


class _Connection:
    __slots__ = ("sender", "in_flight", "last_used", "broken")

    def __init__(self, sender: Any) -> None:
        self.sender = sender
        self.in_flight = 0
        self.last_used = time.monotonic()
        self.broken = False


SenderFactory = Callable[[], Awaitable[Any]]
CallFn = Callable[[Any, Any], Awaitable[Any]]


class DcPool:
    """Authorized MTProto connections to one data centre, shared by transfers.

    ``sender_factory`` and ``call`` are injectable so tests and benchmarks can
    simulate a network without Telegram.
    """

    def __init__(
        self,
        client: TelegramClient | None,
        dc_id: int,
        *,
        max_connections: int = MAX_CONNECTIONS_PER_DC,
        requests_per_connection: int = REQUESTS_PER_CONNECTION,
        sender_factory: SenderFactory | None = None,
        call: CallFn | None = None,
        idle_timeout: float = IDLE_TIMEOUT,
    ) -> None:
        self.client = client
        self.dc_id = dc_id
        self.max_connections = max(1, max_connections)
        self.requests_per_connection = max(1, requests_per_connection)
        self.idle_timeout = idle_timeout
        self._sender_factory = sender_factory or self._open_sender
        self._call = call or (client._call if client is not None else None)
        self._conns: list[_Connection] = []
        self._connecting = 0
        self._cond = asyncio.Condition()
        self._closed = False
        self._reaper: asyncio.Task | None = None
        # Our own DC reuses the session's key; other DCs need an exported one.
        self._is_home = client is None or client.session.dc_id == dc_id
        self._auth_key = client.session.auth_key if (client and self._is_home) else None
        self._auth_lock = asyncio.Lock()

    @property
    def capacity(self) -> int:
        """Maximum number of requests this pool runs at once."""
        return self.max_connections * self.requests_per_connection

    @property
    def connection_count(self) -> int:
        return len(self._conns)

    # ── connection lifecycle ──

    async def _open_sender(self) -> MTProtoSender:
        assert self.client is not None
        if self._auth_key is None:
            # The first connection to a foreign DC exports our authorization;
            # the rest wait for it and then reuse its key.
            async with self._auth_lock:
                if self._auth_key is None:
                    return await self._connect(authorize=True)
        return await self._connect(authorize=False)

    async def _connect(self, *, authorize: bool) -> MTProtoSender:
        client = self.client
        assert client is not None
        dc = await client._get_dc(self.dc_id)
        sender = MTProtoSender(
            None if authorize else self._auth_key, loggers=client._log
        )
        try:
            kwargs: dict[str, Any] = {"loggers": client._log, "proxy": client._proxy}
            if hasattr(client, "_local_addr"):
                kwargs["local_addr"] = client._local_addr
            await sender.connect(
                client._connection(dc.ip_address, dc.port, dc.id, **kwargs)
            )
            if authorize:
                log.debug("Exporting authorization to DC %d", self.dc_id)
                auth = await client(ExportAuthorizationRequest(self.dc_id))
                # Copy the init request: mutating the client's shared one would
                # race with other pools exporting at the same time.
                init = copy.copy(client._init_request)
                init.query = ImportAuthorizationRequest(id=auth.id, bytes=auth.bytes)
                await sender.send(InvokeWithLayerRequest(LAYER, init))
                self._auth_key = sender.auth_key
        except BaseException:
            with contextlib.suppress(BaseException):
                await sender.disconnect()
            raise
        return sender

    @staticmethod
    async def _disconnect(conn: _Connection) -> None:
        with contextlib.suppress(BaseException):
            await _maybe_await(conn.sender.disconnect())

    def _forget_locked(self, conn: _Connection) -> None:
        if conn in self._conns:
            self._conns.remove(conn)
            asyncio.ensure_future(self._disconnect(conn))

    def _ensure_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.ensure_future(self._reap_idle())

    async def _reap_idle(self) -> None:
        while not self._closed:
            await asyncio.sleep(_REAPER_INTERVAL)
            async with self._cond:
                now = time.monotonic()
                for conn in list(self._conns):
                    if conn.in_flight == 0 and now - conn.last_used > self.idle_timeout:
                        self._forget_locked(conn)
                if not self._conns:
                    self._reaper = None
                    return

    async def close(self) -> None:
        async with self._cond:
            self._closed = True
            conns, self._conns = self._conns, []
            self._cond.notify_all()
        if self._reaper is not None:
            self._reaper.cancel()
        await asyncio.gather(*(self._disconnect(c) for c in conns))

    # ── slots ──

    async def _acquire(self) -> _Connection:
        async with self._cond:
            while True:
                if self._closed:
                    raise PoolClosedError("Connection pool closed")
                usable = [c for c in self._conns if not c.broken]
                free = [c for c in usable if c.in_flight < self.requests_per_connection]
                can_open = len(usable) + self._connecting < self.max_connections
                best = min(free, key=lambda c: c.in_flight) if free else None
                # Spread load over sockets first; pipeline once at the cap.
                if best is not None and (best.in_flight == 0 or not can_open):
                    best.in_flight += 1
                    return best
                if can_open:
                    self._connecting += 1
                    break
                await self._cond.wait()

        try:
            sender = await self._sender_factory()
        except BaseException:
            async with self._cond:
                self._connecting -= 1
                self._cond.notify()
            raise
        conn = _Connection(sender)
        conn.in_flight = 1
        async with self._cond:
            self._connecting -= 1
            if self._closed:
                asyncio.ensure_future(self._disconnect(conn))
                raise PoolClosedError("Connection pool closed")
            self._conns.append(conn)
            self._ensure_reaper()
            self._cond.notify_all()  # the new socket has spare slots
        return conn

    async def _release(self, conn: _Connection) -> None:
        async with self._cond:
            conn.in_flight -= 1
            conn.last_used = time.monotonic()
            if conn.broken:
                self._forget_locked(conn)
            self._cond.notify()

    @contextlib.asynccontextmanager
    async def slot(self) -> AsyncIterator[_Connection]:
        """Borrow one request slot on a pooled connection."""
        conn = await self._acquire()
        try:
            yield conn
        finally:
            await self._release(conn)

    async def _reset_authorization(self) -> None:
        if self._is_home:
            return
        async with self._cond:
            self._auth_key = None
            for conn in list(self._conns):
                conn.broken = True
                if conn.in_flight == 0:
                    self._forget_locked(conn)

    # ── requests ──

    async def request(
        self,
        make_request: Callable[[], Any],
        *,
        refresh: Callable[[], Awaitable[None]] | None = None,
        on_flood_wait: FloodCallback | None = None,
    ) -> Any:
        """Run one request with retries, reconnects and flood-wait handling."""
        delay = _BACKOFF_START
        last_exc: BaseException | None = None
        for attempt in range(PART_RETRIES):
            wait = 0.0
            try:
                async with self.slot() as conn:
                    try:
                        return await asyncio.wait_for(
                            self._call(conn.sender, make_request()), REQUEST_TIMEOUT
                        )
                    except _TRANSIENT_ERRORS:
                        conn.broken = True
                        raise
            except FloodWaitError as exc:
                if exc.seconds > MAX_FLOOD_WAIT_SECONDS:
                    raise
                last_exc, wait = exc, float(exc.seconds)
                log.warning("Flood wait %ss on DC %s", exc.seconds, self.dc_id)
                if on_flood_wait:
                    with contextlib.suppress(Exception):
                        on_flood_wait(wait)
            except FileReferenceExpiredError as exc:
                if refresh is None or attempt == PART_RETRIES - 1:
                    raise
                last_exc = exc
                await refresh()
                continue
            except (AuthKeyUnregisteredError, AuthBytesInvalidError) as exc:
                if self._is_home:
                    raise
                last_exc, wait = exc, delay
                await self._reset_authorization()
            except _TRANSIENT_ERRORS as exc:
                last_exc, wait = exc, delay
                log.debug(
                    "Transient error on DC %s (attempt %d/%d): %r",
                    self.dc_id,
                    attempt + 1,
                    PART_RETRIES,
                    exc,
                )
            delay = min(delay * 2, _BACKOFF_MAX)
            if attempt < PART_RETRIES - 1:
                await asyncio.sleep(wait)
        assert last_exc is not None
        raise last_exc


# ─────────────────────────────── registry ───────────────────────────────

_pools: weakref.WeakKeyDictionary[TelegramClient, dict[int, DcPool]] = (
    weakref.WeakKeyDictionary()
)


def get_pool(client: TelegramClient, dc_id: int | None = None) -> DcPool:
    """The shared pool for `dc_id` (default: the account's home DC)."""
    dc = dc_id or client.session.dc_id
    pools = _pools.setdefault(client, {})
    pool = pools.get(dc)
    if pool is None or pool._closed:
        pool = pools[dc] = DcPool(client, dc)
    return pool


async def close_pools(client: TelegramClient) -> None:
    """Close every pooled connection of `client` (on logout / shutdown)."""
    pools = _pools.pop(client, {})
    await asyncio.gather(*(p.close() for p in pools.values()), return_exceptions=True)


# ─────────────────────────────── part sources ───────────────────────────────


class PartSource(Protocol):
    """Random-access bytes to upload. Methods are blocking (run in a thread)."""

    size: int

    def read(self, offset: int, length: int) -> bytes: ...

    def md5(self) -> str: ...

    def close(self) -> None: ...


class FilePartSource:
    """Plain file on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.size = self.path.stat().st_size
        self._f: BinaryIO | None = None
        self._lock = threading.Lock()

    def read(self, offset: int, length: int) -> bytes:
        with self._lock:
            if self._f is None:
                self._f = self.path.open("rb")
            self._f.seek(offset)
            return self._f.read(length)

    def md5(self) -> str:
        h = hashlib.md5()
        with self.path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def close(self) -> None:
        with self._lock:
            if self._f is not None:
                self._f.close()
                self._f = None


class _SequentialWriter:
    """Appends data to a file from a worker thread.

    Writes are strictly sequential: on NTFS, out-of-order writes into a
    growing file can be 10-20x slower than appending.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._f: BinaryIO | None = None

    async def open(self) -> None:
        self._f = await asyncio.to_thread(self.path.open, "wb")

    def _write_all(self, chunks: list[bytes]) -> None:
        assert self._f is not None
        for chunk in chunks:
            self._f.write(chunk)

    async def write(self, chunks: list[bytes]) -> None:
        await asyncio.to_thread(self._write_all, chunks)

    async def close(self) -> None:
        if self._f is not None:
            f, self._f = self._f, None
            await asyncio.to_thread(f.close)


# ─────────────────────────────── orchestration ───────────────────────────────


def _part_size_for(size: int, max_part: int) -> int:
    """Part size giving each file about TARGET_PARTS parts (power of two).

    Small files split into smaller parts so they still spread over many
    connections; large files use the biggest part Telegram allows. Powers of
    two between MIN_PART_SIZE and the maximum satisfy Telegram's rules for
    both upload.saveFilePart (divides 512 KB) and upload.getFile (divides
    1 MB, multiple of 4 KB).
    """
    wanted = max(MIN_PART_SIZE, -(-size // TARGET_PARTS))
    part = MIN_PART_SIZE
    while part < wanted and part < max_part:
        part *= 2
    return min(part, max_part)


async def _run_workers(count: int, worker: Callable[[], Awaitable[None]]) -> None:
    """Run `count` workers; the first failure cancels the rest and is raised."""
    if count <= 0:
        return
    tasks = [asyncio.ensure_future(worker()) for _ in range(count)]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            if not task.cancelled() and task.exception() is not None:
                raise task.exception()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run_pipeline(
    count: int,
    worker: Callable[[], Awaitable[None]],
    consumer: Callable[[], Awaitable[None]],
    finish: Callable[[], None],
) -> None:
    """Run producers and one consumer; any failure cancels everything.

    ``finish`` is called once all producers succeeded, to let the consumer
    drain and exit.
    """
    workers = [asyncio.ensure_future(worker()) for _ in range(count)]
    consumer_task = asyncio.ensure_future(consumer())
    producers = asyncio.gather(*workers)
    try:
        if not workers:
            finish()
            await consumer_task
            return
        # FIRST_COMPLETED, not FIRST_EXCEPTION: the consumer only exits after
        # finish(), so waiting for "all done" would deadlock.
        done, _ = await asyncio.wait(
            {producers, consumer_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if consumer_task in done:
            consumer_task.result()  # raises the consumer's error
            raise RuntimeError("Download writer stopped unexpectedly")
        producers.result()  # raises the first worker error, if any
        finish()
        await consumer_task
    finally:
        for task in (*workers, consumer_task):
            task.cancel()
        await asyncio.gather(*workers, consumer_task, return_exceptions=True)
        if not producers.done():
            producers.cancel()
        with contextlib.suppress(BaseException):
            await producers


async def download_file(
    client: TelegramClient,
    location: TypeLocation,
    out: BinaryIO | str | Path,
    progress_callback: ProgressCallback | None = None,
    *,
    refresh_location: Callable[[], Awaitable[TypeLocation]] | None = None,
    on_flood_wait: FloodCallback | None = None,
    pool: DcPool | None = None,
) -> BinaryIO | str | Path:
    """Download `location` to `out` (a path, or a file object's name).

    ``refresh_location`` re-fetches the location when Telegram reports an
    expired file reference (long downloads outlive them).
    """
    size = int(getattr(location, "size", 0) or 0)
    dc_id, input_location = utils.get_input_location(location)
    pool = pool or get_pool(client, dc_id)
    part_size = _part_size_for(size, DOWNLOAD_PART_SIZE)
    part_count = math.ceil(size / part_size) if size else 0

    current = {"location": input_location}
    refresh_lock = asyncio.Lock()

    async def refresh() -> None:
        assert refresh_location is not None
        async with refresh_lock:
            _, current["location"] = utils.get_input_location(await refresh_location())

    writer = _SequentialWriter(out if isinstance(out, str | Path) else out.name)
    await writer.open()
    workers = min(part_count, pool.capacity)
    # Parts complete out of order but are written in order. Fetching may run
    # at most `max_ahead` parts ahead of the disk, which bounds memory to
    # roughly max_ahead x part_size.
    max_ahead = max(4, 2 * workers)
    state = {"next_part": 0, "next_flush": 0, "written_parts": 0, "done_bytes": 0}
    completed: dict[int, bytes] = {}
    window = asyncio.Condition()
    queue: asyncio.Queue[list[bytes] | None] = asyncio.Queue()

    async def fetch(index: int) -> bytes:
        offset = index * part_size
        expected = min(part_size, size - offset)
        for _attempt in range(3):
            result = await pool.request(
                lambda: GetFileRequest(
                    current["location"], offset=offset, limit=part_size
                ),
                refresh=refresh if refresh_location else None,
                on_flood_wait=on_flood_wait,
            )
            if len(result.bytes) == expected:
                return result.bytes
            log.warning(
                "Short part at %d (%d of %d bytes), retrying",
                offset,
                len(result.bytes),
                expected,
            )
        raise ConnectionError(
            f"Telegram kept returning a short part at offset {offset}"
        )

    async def worker() -> None:
        while True:
            async with window:
                await window.wait_for(
                    lambda: state["next_part"] >= part_count
                    or state["next_part"] < state["written_parts"] + max_ahead
                )
                if state["next_part"] >= part_count:
                    return
                index = state["next_part"]
                state["next_part"] += 1
            data = await fetch(index)
            async with window:
                completed[index] = data
                batch = []
                while state["next_flush"] in completed:
                    batch.append(completed.pop(state["next_flush"]))
                    state["next_flush"] += 1
                if batch:
                    queue.put_nowait(batch)  # queue order == file order

    async def write_loop() -> None:
        while (batch := await queue.get()) is not None:
            await writer.write(batch)
            async with window:
                state["written_parts"] += len(batch)
                window.notify_all()
            state["done_bytes"] += sum(len(c) for c in batch)
            if progress_callback:
                await _maybe_await(progress_callback(state["done_bytes"], size))

    try:
        await _run_pipeline(workers, worker, write_loop, lambda: queue.put_nowait(None))
    finally:
        await writer.close()
    return out


async def upload_source(
    client: TelegramClient,
    source: PartSource,
    filename: str,
    progress_callback: ProgressCallback | None = None,
    *,
    on_flood_wait: FloodCallback | None = None,
    pool: DcPool | None = None,
) -> TypeInputFile:
    """Upload `source` and return the InputFile to attach to a message."""
    size = source.size
    part_size = _part_size_for(size, UPLOAD_PART_SIZE)
    part_count = max(1, math.ceil(size / part_size))
    if part_count > MAX_UPLOAD_PARTS:
        raise ValueError(
            "File is too large for Telegram (4 GB maximum with Premium, 2 GB otherwise)."
        )
    is_big = size > BIG_FILE_THRESHOLD
    file_id = helpers.generate_random_long()
    pool = pool or get_pool(client)
    md5 = "" if is_big else await asyncio.to_thread(source.md5)

    next_part = 0
    done_bytes = 0

    async def worker() -> None:
        nonlocal next_part, done_bytes
        while next_part < part_count:
            index = next_part
            next_part += 1
            data = await asyncio.to_thread(source.read, index * part_size, part_size)
            make = (
                functools.partial(
                    SaveBigFilePartRequest, file_id, index, part_count, data
                )
                if is_big
                else functools.partial(SaveFilePartRequest, file_id, index, data)
            )
            if not await pool.request(make, on_flood_wait=on_flood_wait):
                raise ConnectionError(f"Telegram did not accept file part {index}")
            done_bytes += len(data)
            if progress_callback:
                await _maybe_await(progress_callback(done_bytes, size))

    await _run_workers(min(part_count, pool.capacity), worker)
    if is_big:
        return InputFileBig(file_id, part_count, filename)
    return InputFile(file_id, part_count, filename, md5)


async def upload_file(
    client: TelegramClient,
    file: BinaryIO | str | Path,
    filename: str | None = None,
    progress_callback: ProgressCallback | None = None,
    *,
    on_flood_wait: FloodCallback | None = None,
) -> TypeInputFile:
    """Upload a file (path or open file object) from disk."""
    path = Path(file if isinstance(file, str | Path) else file.name)
    source = FilePartSource(path)
    try:
        return await upload_source(
            client,
            source,
            filename or path.name or "upload",
            progress_callback,
            on_flood_wait=on_flood_wait,
        )
    finally:
        source.close()


async def iter_range(
    client: TelegramClient,
    location: TypeLocation,
    start: int,
    end: int,
    *,
    readahead: int = STREAM_READAHEAD,
    pool: DcPool | None = None,
) -> AsyncIterator[bytes]:
    """Yield bytes ``start..end`` (inclusive) of a file, in order.

    Fetches 1 MB-aligned parts (Telegram requires aligned requests) with
    `readahead` parts in flight, so playback and seeking stay smooth.
    """
    size = int(getattr(location, "size", 0) or 0)
    end = min(end, size - 1)
    if size <= 0 or start > end:
        return
    dc_id, input_location = utils.get_input_location(location)
    pool = pool or get_pool(client, dc_id)
    part = DOWNLOAD_PART_SIZE
    first, last = start // part, end // part

    def fetch(index: int) -> asyncio.Future:
        return asyncio.ensure_future(
            pool.request(
                lambda: GetFileRequest(input_location, offset=index * part, limit=part)
            )
        )

    pending: deque[tuple[int, asyncio.Future]] = deque()
    next_index = first
    try:
        while next_index <= last and len(pending) < max(1, readahead):
            pending.append((next_index, fetch(next_index)))
            next_index += 1
        while pending:
            index, fut = pending.popleft()
            data = (await fut).bytes
            if next_index <= last:
                pending.append((next_index, fetch(next_index)))
                next_index += 1
            lo = start - index * part if index == first else 0
            hi = end - index * part + 1 if index == last else len(data)
            chunk = data[lo:hi]
            if chunk:
                yield chunk
    finally:
        for _, fut in pending:
            fut.cancel()
        await asyncio.gather(*(f for _, f in pending), return_exceptions=True)


__all__ = [
    "DcPool",
    "FilePartSource",
    "PoolClosedError",
    "PartSource",
    "close_pools",
    "download_file",
    "get_pool",
    "iter_range",
    "upload_file",
    "upload_source",
    "MAX_UPLOAD_PARTS",
]
