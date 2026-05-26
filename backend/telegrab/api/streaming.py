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
import logging
import re
import time
from urllib.parse import parse_qs, urlparse

from .. import telegram as tg
from ..config import get_stream_config

log = logging.getLogger(__name__)

CHUNK_SIZE = 512 * 1024
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")

_HTTP_200 = b"HTTP/1.1 200 OK\r\n"
_HTTP_206 = b"HTTP/1.1 206 Partial Content\r\n"
_HTTP_400 = b"HTTP/1.1 400 Bad Request\r\n\r\nBad Request"
_HTTP_403 = b"HTTP/1.1 403 Forbidden\r\n\r\nForbidden"
_HTTP_404 = b"HTTP/1.1 404 Not Found\r\n\r\nNot Found"
_HTTP_416 = b"HTTP/1.1 416 Range Not Satisfiable\r\n\r\nRange Not Satisfiable"
_HTTP_503 = b"HTTP/1.1 503 Service Unavailable\r\n\r\nNot connected"

# Message metadata cache: (folder_id, message_id) -> (timestamp, message)
_msg_cache: dict[tuple[int | None, int], tuple[float, object]] = {}
_MSG_CACHE_TTL = 30.0


def _build_headers(headers: dict[str, str]) -> bytes:
    lines = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    return (lines + "\r\n").encode()


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        # Read the request line + headers (stop at blank line).
        raw_lines: list[str] = []
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n":
                break
            raw_lines.append(line.decode(errors="replace").rstrip("\r\n"))

        if not raw_lines:
            writer.write(_HTTP_400)
            await writer.drain()
            writer.close()
            return

        request_line = raw_lines[0]
        req_headers: dict[str, str] = {}
        for h in raw_lines[1:]:
            if ": " in h:
                k, _, v = h.partition(": ")
                req_headers[k.lower()] = v

        parts = request_line.split(" ")
        if len(parts) < 2:
            writer.write(_HTTP_400)
            await writer.drain()
            writer.close()
            return

        path_qs = parts[1]
        parsed = urlparse(path_qs)
        path = parsed.path          # e.g. /stream/home/12345
        qs   = parse_qs(parsed.query)

        # Validate token
        cfg = get_stream_config()
        token = qs.get("token", [""])[0]
        if token != cfg.token:
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
            writer.write(_HTTP_503)
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

        if msg is None or msg.media is None:
            writer.write(_HTTP_404)
            await writer.drain()
            writer.close()
            return

        total = tg.media_total_size(msg)
        mime  = tg.mime_type_from_message(msg)
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
                    end   = total - 1
                else:
                    start = int(a) if a else 0
                    end   = int(b) if b else total - 1
                    end   = min(end, total - 1)
                if start > end or start >= total:
                    writer.write(_HTTP_416)
                    await writer.drain()
                    writer.close()
                    return
                is_partial = True

        length = end - start + 1 if total > 0 else 0

        resp_headers: dict[str, str] = {
            "Content-Type":        mime,
            "Accept-Ranges":       "bytes",
            "Cache-Control":       "private, max-age=120",
            "Content-Disposition": f'inline; filename="{fname}"',
        }
        if length > 0:
            resp_headers["Content-Length"] = str(length)
        if is_partial:
            resp_headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        status_line = _HTTP_206 if is_partial else _HTTP_200
        writer.write(status_line + _build_headers(resp_headers))
        await writer.drain()

        # Stream the body
        sent = 0
        chunk_count = 0
        try:
            async for chunk in client.iter_download(msg, offset=start, request_size=CHUNK_SIZE):
                if not chunk:
                    break
                if length > 0:
                    remaining = length - sent
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]
                if not chunk:
                    break
                writer.write(chunk)
                chunk_count += 1
                if chunk_count % 4 == 0:
                    await writer.drain()
                sent += len(chunk)
                if length > 0 and sent >= length:
                    break
            if chunk_count % 4 != 0:
                await writer.drain()
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
        try:
            writer.close()
        except Exception:  # noqa: BLE001
            pass


async def serve_streaming() -> None:
    """Run the pure-asyncio streaming server on the current event loop."""
    cfg = get_stream_config()
    server = await asyncio.start_server(
        _handle,
        host="127.0.0.1",
        port=cfg.port,
        limit=256 * 1024,
    )
    log.info("Media streaming server started on http://127.0.0.1:%s", cfg.port)
    async with server:
        await server.serve_forever()
