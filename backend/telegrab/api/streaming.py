"""Local media-streaming HTTP server.

  GET /stream/{folder_id}/{message_id}?token=<session_token>

Implements byte-range requests (HTTP 206), so video / audio seek works in
`<video>` / `<audio>` elements without buffering the entire stream.

Started on the same asyncio loop the Telethon client lives on (see
`telegrab.infra.runtime.AsyncRuntime`), so we can directly await
`iter_download(...)` inside request handlers.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .. import telegram as tg
from ..config import allowed_origins, get_stream_config

log = logging.getLogger(__name__)

CHUNK_SIZE = 512 * 1024  # Telethon's iter_download default chunk
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _create_app() -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["Range", "Content-Type", "Accept"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
        max_age=3600,
    )

    cfg = get_stream_config()

    def _check_token(token: str | None) -> None:
        if not token or token != cfg.token:
            log.error("Stream request: invalid token")
            raise HTTPException(
                status_code=403, detail="Invalid or missing stream token"
            )

    def _parse_folder_id(folder_id_str: str) -> int | None:
        if folder_id_str.lower() in {"me", "home", "null"}:
            return None
        try:
            return int(folder_id_str)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid folder ID") from exc

    @app.get("/stream/{folder_id}/{message_id}")
    async def stream_media(
        folder_id: str = Path(...),
        message_id: int = Path(..., gt=0),
        token: str | None = Query(default=None),
        range_header: str | None = Header(default=None, alias="range"),
    ):
        _check_token(token)
        fid = _parse_folder_id(folder_id)

        state = tg.get_state()
        client = state.client
        if client is None:
            log.error("Stream request: client not connected")
            raise HTTPException(status_code=503, detail="Telegram client not connected")

        peer = await tg.resolve_peer(client, fid)
        msg = await client.get_messages(peer, ids=int(message_id))
        if msg is None or msg.media is None:
            raise HTTPException(status_code=404, detail="Message or media not found")

        total = tg.media_total_size(msg)
        mime = tg.mime_type_from_message(msg)
        filename = tg.filename_from_message(msg)

        # Default range: whole file.
        start, end = 0, max(total - 1, 0)
        is_partial = False

        if range_header and total > 0:
            match = RANGE_RE.match(range_header.strip())
            if match:
                a, b = match.group(1), match.group(2)
                if a == "" and b != "":
                    n = int(b)
                    start = max(total - n, 0)
                    end = total - 1
                else:
                    start = int(a) if a else 0
                    end = int(b) if b else total - 1
                    end = min(end, total - 1)
                if start > end or start >= total:
                    raise HTTPException(
                        status_code=416,
                        detail="Requested range not satisfiable",
                        headers={"Content-Range": f"bytes */{total}"},
                    )
                is_partial = True

        length = end - start + 1 if total > 0 else 0

        async def streamer() -> AsyncIterator[bytes]:
            sent = 0
            try:
                async for chunk in client.iter_download(
                    msg, offset=start, request_size=CHUNK_SIZE
                ):
                    if not chunk:
                        break
                    remaining = length - sent if length > 0 else None
                    if remaining is not None and len(chunk) > remaining:
                        chunk = chunk[:remaining]
                    if not chunk:
                        break
                    yield chunk
                    sent += len(chunk)
                    if length > 0 and sent >= length:
                        break
            except asyncio.CancelledError:
                log.debug("Stream cancelled for msg %s", message_id)
                raise
            except Exception as exc:  # noqa: BLE001
                log.error("Stream error msg %s: %s", message_id, exc)

        headers: dict[str, str] = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=120",
            "Content-Disposition": f'inline; filename="{filename}"',
        }
        if length > 0:
            headers["Content-Length"] = str(length)
        if is_partial:
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"

        status = 206 if is_partial else 200
        return StreamingResponse(
            streamer(),
            status_code=status,
            media_type=mime,
            headers=headers,
        )

    return app


# ───────────────────────────── server lifecycle ─────────────────────────────


async def serve_streaming() -> None:
    """Run the streaming server forever on the current event loop."""
    cfg = get_stream_config()
    app = _create_app()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=cfg.port,
        log_level="warning",
        access_log=False,
        lifespan="off",
    )
    server = uvicorn.Server(config)
    log.info("Starting media streaming server on http://127.0.0.1:%s", cfg.port)
    await server.serve()
