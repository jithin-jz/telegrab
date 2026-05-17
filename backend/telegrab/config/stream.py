"""Streaming server configuration (port + per-session token)."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

# Single source of truth for the streaming port — referenced by the
# FastAPI streaming server, the bridge command that exposes it to JS,
# and the REST API command that refuses the same port.
STREAM_PORT = 14201


# CORS allow-list for both the streaming server and the REST API.
#
#  * `null`                       — pywebview loads the production bundle
#                                   from a `file://` URL, so the browser
#                                   sends `Origin: null`.
#  * `http://localhost:5173`      — Vite dev server.
#  * `http://127.0.0.1:5173`      — Vite dev server (loopback variant).
#
# A user can extend this via the TELEGRAB_EXTRA_ORIGINS environment
# variable (comma-separated) for power-user setups (e.g. a custom UI
# on top of the REST API).
_DEFAULT_LOCAL_ORIGINS: tuple[str, ...] = (
    "null",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def allowed_origins() -> list[str]:
    extra = os.environ.get("TELEGRAB_EXTRA_ORIGINS", "").strip()
    extras = [o.strip() for o in extra.split(",") if o.strip()] if extra else []
    return [*_DEFAULT_LOCAL_ORIGINS, *extras]


@dataclass
class StreamConfig:
    token: str
    port: int
    allowed_origins: list[str] = field(default_factory=allowed_origins)


_cfg: StreamConfig | None = None


def get_stream_config() -> StreamConfig:
    """Lazy singleton — token is generated once per process."""
    global _cfg
    if _cfg is None:
        _cfg = StreamConfig(token=secrets.token_hex(16), port=STREAM_PORT)
    return _cfg
