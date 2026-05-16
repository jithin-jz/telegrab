"""Optional REST API server.

Endpoints:

  GET /api/v1/health
  GET /api/v1/files?folder_id=&page=&limit=&search=
  GET /api/v1/files/{message_id}?folder_id=
  GET /api/v1/files/{message_id}/download?folder_id=

All non-health endpoints require an `X-API-Key` header that hashes to the
`key_hash` saved in `api_settings.json` (see `tg_drive.config.api_settings`).
The server is started/stopped/restarted by `RestApiSupervisor` (below),
which is wired into `services.api_settings.set_restart_hook` from app.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .. import __version__, telegram as tg
from ..config import load_settings, verify_key

log = logging.getLogger(__name__)


def _create_app(initial_key_hash: Optional[str]) -> FastAPI:
    """Build the API server. The captured key hash is the one the server
    was configured with at start-time; restarts re-create the app so
    changes pick up cleanly.
    """

    app = FastAPI(
        title="Telegram Drive API",
        version=__version__,
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_key(x_api_key: Optional[str] = Header(default=None)) -> None:
        # Always look up the latest hash on disk so a regenerated key takes
        # effect for the next request without a server restart.
        settings = load_settings()
        stored = settings.key_hash or initial_key_hash
        if not stored:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "code": "NO_KEY_CONFIGURED",
                        "message": "No API key has been configured. Generate one in Settings.",
                    }
                },
            )
        if not x_api_key:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Missing X-API-Key header",
                    }
                },
            )
        if not verify_key(x_api_key, stored):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {"code": "UNAUTHORIZED", "message": "Invalid API key"}
                },
            )

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/files", dependencies=[Depends(require_key)])
    async def list_files(
        folder_id: Optional[int] = Query(default=None),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=200),
        search: Optional[str] = Query(default=None),
    ) -> dict:
        client = tg.get_state().client
        if client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": {
                        "code": "NOT_CONNECTED",
                        "message": "Telegram client is not connected",
                    }
                },
            )

        try:
            peer = await tg.resolve_peer(client, folder_id)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {"code": "PEER_ERROR", "message": str(exc)}
                },
            ) from exc

        files = []
        async for msg in client.iter_messages(peer):
            meta = tg.file_metadata_from_message(msg, folder_id)
            if meta is None:
                continue
            if search and search.lower() not in meta["name"].lower():
                continue
            files.append(meta)

        total = len(files)
        start = (page - 1) * limit
        page_items = files[start : start + limit]

        return {
            "files": page_items,
            "page": page,
            "limit": limit,
            "total": total,
        }

    @app.get("/api/v1/files/{message_id}", dependencies=[Depends(require_key)])
    async def get_file(
        message_id: int = Path(...),
        folder_id: Optional[int] = Query(default=None),
    ) -> dict:
        client = tg.get_state().client
        if client is None:
            raise HTTPException(status_code=503, detail="Telegram client not connected")

        peer = await tg.resolve_peer(client, folder_id)
        msg = await client.get_messages(peer, ids=int(message_id))
        if msg is None or msg.media is None:
            raise HTTPException(status_code=404, detail="File not found")
        meta = tg.file_metadata_from_message(msg, folder_id)
        if meta is None:
            raise HTTPException(status_code=404, detail="File not found")
        return meta

    @app.get(
        "/api/v1/files/{message_id}/download", dependencies=[Depends(require_key)]
    )
    async def download_file(
        message_id: int = Path(...),
        folder_id: Optional[int] = Query(default=None),
    ):
        client = tg.get_state().client
        if client is None:
            raise HTTPException(status_code=503, detail="Telegram client not connected")

        peer = await tg.resolve_peer(client, folder_id)
        msg = await client.get_messages(peer, ids=int(message_id))
        if msg is None or msg.media is None:
            raise HTTPException(status_code=404, detail="File not found")

        size = tg.media_total_size(msg)
        mime = tg.mime_type_from_message(msg)
        filename = tg.filename_from_message(msg)

        async def streamer() -> AsyncIterator[bytes]:
            try:
                async for chunk in client.iter_download(msg):
                    if chunk:
                        yield chunk
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.error("API download stream error: %s", exc)

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        if size:
            headers["Content-Length"] = str(size)

        return StreamingResponse(streamer(), media_type=mime, headers=headers)

    return app


# ────────────────────────────── supervisor ──────────────────────────────


class RestApiSupervisor:
    """Owns the optional REST API server's start/stop/restart lifecycle.

    Lives on the runtime asyncio loop. Public methods are safe to call from
    any thread because they all dispatch onto that loop via
    `runtime.AsyncRuntime.spawn`.
    """

    def __init__(self, runtime) -> None:
        self._runtime = runtime
        self._task: asyncio.Task | None = None
        self._server: uvicorn.Server | None = None
        self._running: bool = False

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Spawn (or respawn) the server based on the current settings."""
        self._runtime.spawn(self._restart())

    def stop(self) -> None:
        self._runtime.spawn(self._stop_only())

    async def _stop_only(self) -> None:
        await self._stop_current_locked()

    async def _stop_current_locked(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
        self._task = None
        self._server = None
        self._running = False

    async def _restart(self) -> None:
        await self._stop_current_locked()

        settings = load_settings()
        if not settings.enabled:
            log.info("REST API disabled — server will not start")
            return

        app = _create_app(settings.key_hash)
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=settings.port,
            log_level="warning",
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(config)

        async def _runner() -> None:
            try:
                self._running = True
                log.info("REST API server starting on http://127.0.0.1:%s", settings.port)
                await self._server.serve()  # type: ignore[union-attr]
            except Exception as exc:  # noqa: BLE001
                log.error("REST API server crashed: %s", exc)
            finally:
                self._running = False

        self._task = asyncio.create_task(_runner())
