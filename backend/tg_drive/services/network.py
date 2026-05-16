"""Network probes, log forwarding, bandwidth read-out, stream-info.

Renamed from `commands/misc.py` to `network.py` since the contents are
about runtime/network state more than miscellaneous helpers.
"""

from __future__ import annotations

import asyncio
import logging
import socket

from ..config import get_stream_config
from ..infra import get_manager

log = logging.getLogger(__name__)


async def cmd_is_network_available() -> bool:
    """Lightweight TCP probe to one of Telegram's production DCs."""

    def _probe() -> bool:
        try:
            with socket.create_connection(("149.154.167.50", 443), timeout=2.0):
                return True
        except OSError:
            return False

    return await asyncio.to_thread(_probe)


def cmd_log(message: str) -> None:
    log.info("[FRONTEND] %s", message)


def cmd_get_bandwidth() -> dict:
    return get_manager().get_stats()


def cmd_get_stream_info() -> dict:
    cfg = get_stream_config()
    return {
        "token": cfg.token,
        "base_url": f"http://localhost:{cfg.port}",
    }


__all__ = [
    "cmd_is_network_available",
    "cmd_log",
    "cmd_get_bandwidth",
    "cmd_get_stream_info",
]
