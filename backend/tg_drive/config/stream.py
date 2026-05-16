"""Streaming server configuration (port + per-session token)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

# Single source of truth for the streaming port — referenced by the
# FastAPI streaming server, the bridge command that exposes it to JS,
# and the REST API command that refuses the same port.
STREAM_PORT = 14201


@dataclass
class StreamConfig:
    token: str
    port: int


_cfg: StreamConfig | None = None


def get_stream_config() -> StreamConfig:
    """Lazy singleton — token is generated once per process."""
    global _cfg
    if _cfg is None:
        _cfg = StreamConfig(token=secrets.token_hex(16), port=STREAM_PORT)
    return _cfg
