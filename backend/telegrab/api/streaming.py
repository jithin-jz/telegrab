"""Pure-asyncio media streaming server (no FastAPI / uvicorn).

Listens on 127.0.0.1:{STREAM_PORT} and handles:

  GET /stream/{folder_id}/{message_id}?token=<session_token>

Implements HTTP/1.1 byte-range requests (206 Partial Content) so
<video>/<audio> elements inside pywebview can seek without buffering
the whole file.

This server runs on the *same* asyncio event loop as the Telethon client
(via AsyncRuntime.spawn), so we can directly await `iter_download` inside
request handlers.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
import re
import time
from urllib.parse import parse_qs, urlparse

from .. import telegram as tg
from ..config import get_stream_config

log = logging.getLogger(__name__)

CHUNK_SIZE = 512 * 1024
# Socket read buffer — must be at least as large as CHUNK_SIZE to avoid
# fragmenting chunks across multiple reads (2 MB gives comfortable headroom).
_SOCKET_BUFFER_SIZE = 2 * 1024 * 1024
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")

# Maximum length of the HTTP request line (method + path + version).
# Requests exceeding this are rejected as malformed (Req 12.5).
_MAX_REQUEST_LINE_LENGTH = 8192

# Maximum concurrent streaming connections (Req 12.6).
_MAX_CONNECTIONS = 8
_active_connections = 0

_HTTP_200 = b"HTTP/1.1 200 OK\r\n"
_HTTP_206 = b"HTTP/1.1 206 Partial Content\r\n"
_HTTP_400 = b"HTTP/1.1 400 Bad Request\r\n\r\nBad Request"
_HTTP_403 = b"HTTP/1.1 403 Forbidden\r\n\r\nForbidden"
_HTTP_404 = b"HTTP/1.1 404 Not Found\r\n\r\nNot Found"
_HTTP_416 = b"HTTP/1.1 416 Range Not Satisfiable\r\n\r\nRange Not Satisfiable"
_HTTP_503 = b"HTTP/1.1 503 Service Unavailable\r\n\r\nService Unavailable"


# Message metadata cache: (folder_id, message_id) -> (timestamp, message)
_msg_cache: dict[tuple[int | None, int], tuple[float, object]] = {}
_MSG_CACHE_TTL = 30.0
_MSG_CACHE_MAX = 256


def _build_headers(headers: dict[str, str]) -> bytes:
    lines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return (lines + "\r\n").encode()


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    global _active_connections

    # Req 12.6, 12.7: Reject when at connection limit with HTTP 503.
    if _active_connections >= _MAX_CONNECTIONS:
        try:
            writer.write(_HTTP_503)
            await asyncio.wait_for(writer.drain(), timeout=1.0)
        except (TimeoutError, Exception):  # noqa: BLE001
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()
        return

    _active_connections += 1
    try:
        await _handle_request(reader, writer)
    finally:
        _active_connections -= 1


async def _handle_request(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        # Read the request line first with length validation (Req 12.5).
        request_line_raw = await reader.readline()
        if not request_line_raw:
            writer.write(_HTTP_400)
            await writer.drain()
            writer.close()
            return

        # Validate request line length (Req 12.5).
        if len(request_line_raw) > _MAX_REQUEST_LINE_LENGTH:
            log.debug(
                "Rejected request: line exceeds %d bytes", _MAX_REQUEST_LINE_LENGTH
            )
            writer.write(_HTTP_400)
            await writer.drain()
            writer.close()
            return

        request_line = request_line_raw.decode(errors="replace").rstrip("\r\n")

        # Read remaining headers (stop at blank line).
        req_headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            decoded = line.decode(errors="replace").rstrip("\r\n")
            if ": " in decoded:
                k, _, v = decoded.partition(": ")
                req_headers[k.lower()] = v

        # Validate request line has method and path (Req 12.5).
        # No sensitive data logged on malformed requests.
        parts = request_line.split(" ")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            log.debug("Rejected malformed request: missing method or path")
            writer.write(_HTTP_400)
            await writer.drain()
            writer.close()
            return

        path_qs = parts[1]
        parsed = urlparse(path_qs)
        path = parsed.path  # e.g. /stream/home/12345
        qs = parse_qs(parsed.query)

        # Req 12.2, 12.3: Validate token with constant-time comparison.
        # Return HTTP 403 without reading file data if token is invalid/missing.
        cfg = get_stream_config()
        token = qs.get("token", [""])[0]
        if not hmac.compare_digest(token, cfg.token):
            writer.write(_HTTP_403)
            await writer.drain()
            writer.close()
            return

        # Parse /stream/{folder_id}/{message_id}
        m = re.match(r"^/stream/([^/]+)/(\d+)$", path)
        if not m:
            writer.write(_HTTP_404)
            await writer.drain()
            writer.close()
            return

        folder_id_str = m.group(1)
        message_id = int(m.group(2))

        if folder_id_str.lower() in {"me", "home", "null"}:
            fid: int | None = None
        else:
            try:
                fid = int(folder_id_str)
            except ValueError:
                writer.write(_HTTP_400)
                await writer.drain()
                writer.close()
                return

        state = tg.get_state()
        client = state.client
        if client is None:
            writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\nNot connected")
            await writer.drain()
            writer.close()
            return

        peer = await tg.resolve_peer(client, fid)

        # Check message metadata cache
        cache_key = (fid, message_id)
        now = time.monotonic()
        cached = _msg_cache.get(cache_key)
        if cached and (now - cached[0]) < _MSG_CACHE_TTL:
            msg = cached[1]
        else:
            msg = await client.get_messages(peer, ids=message_id)
            if msg is not None:
                _msg_cache[cache_key] = (now, msg)
                if len(_msg_cache) > _MSG_CACHE_MAX:
                    oldest = min(_msg_cache, key=lambda k: _msg_cache[k][0])
                    del _msg_cache[oldest]

        if msg is None or msg.media is None:
            # Evict stale entry from cache if present (Req 2.4)
            _msg_cache.pop(cache_key, None)
            writer.write(_HTTP_404)
            await writer.drain()
            writer.close()
            return

        total = tg.media_total_size(msg)
        mime = tg.mime_type_from_message(msg)
        fname = tg.filename_from_message(msg)

        # Parse Range header
        range_header = req_headers.get("range", "")
        start, end = 0, max(total - 1, 0)
        is_partial = False

        if range_header and total > 0:
            rm = RANGE_RE.match(range_header.strip())
            if rm:
                a, b = rm.group(1), rm.group(2)
                if a == "" and b != "":
                    n = int(b)
                    start = max(total - n, 0)
                    end = total - 1
                else:
                    start = int(a) if a else 0
                    end = int(b) if b else total - 1
                    end = min(end, total - 1)
                if start > end or start >= total:
                    writer.write(_HTTP_416)
                    await writer.drain()
                    writer.close()
                    return
                is_partial = True

        length = end - start + 1 if total > 0 else 0

        resp_headers: dict[str, str] = {
            "Content-Type": mime,
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=120",
            "Content-Disposition": f'inline; filename="{fname}"',
        }
        if length > 0:
            resp_headers["Content-Length"] = str(length)
        if is_partial:
            resp_headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        status_line = _HTTP_206 if is_partial else _HTTP_200
        writer.write(status_line + _build_headers(resp_headers))
        await writer.drain()

        # Stream the body — drain after every chunk for smooth delivery
        # without large buffer build-up.
        sent = 0
        try:
            async for chunk in client.iter_download(
                msg, offset=start, request_size=CHUNK_SIZE
            ):
                if not chunk:
                    break
                if length > 0:
                    remaining = length - sent
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()  # drain every chunk — avoids buffer bloat
                sent += len(chunk)
                if length > 0 and sent >= length:
                    break
        except asyncio.CancelledError:
            log.debug("Stream cancelled for msg %s", message_id)
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("Stream error msg %s: %s", message_id, exc)

    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("Stream handler error: %s", exc)
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def serve_streaming() -> None:
    """Run the pure-asyncio streaming server on the current event loop.

    Binds exclusively to 127.0.0.1 (Req 12.1) — only local connections accepted.
    The socket buffer is set to 2 MB so a full 512 KB chunk never gets split
    across multiple reads.
    """
    cfg = get_stream_config()
    server = await asyncio.start_server(
        _handle,
        host="127.0.0.1",
        port=cfg.port,
        limit=_SOCKET_BUFFER_SIZE,
        reuse_address=True,
    )
    log.info("Media streaming server started on http://127.0.0.1:%s", cfg.port)
    async with server:
        await server.serve_forever()
