"""Streaming server configuration (port + per-session token)."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field

# Preferred port for the streaming server. If it is taken (another app, or a
# second user session on the same machine) the server falls back to any free
# port; the frontend always asks the bridge for the actual one.
STREAM_PORT = 14201


@dataclass
class StreamConfig:
    token: str
    port: int
    # Set once the server is listening and `port` holds the bound port.
    ready: threading.Event = field(default_factory=threading.Event)


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
