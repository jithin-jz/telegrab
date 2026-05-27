"""Streaming server configuration (port + per-session token)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

# Single source of truth for the streaming port — referenced by the
# streaming server and the bridge command that exposes it to JS.
STREAM_PORT = 14201


@dataclass
class StreamConfig:
    token: str
    port: int


_cfg: StreamConfig | None = None


def get_stream_config() -> StreamConfig:
    """Lazy singleton — token is generated once per process.

    The token uses 32 bytes of cryptographic randomness (Req 12.4),
    held only in process memory and never written to disk or logs.
    """
    global _cfg
    if _cfg is None:
        _cfg = StreamConfig(token=secrets.token_hex(32), port=STREAM_PORT)
    return _cfg
