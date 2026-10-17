"""Network probes, proxy settings, log forwarding, bandwidth, stream-info."""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ..config import get_stream_config
from ..infra import get_manager
from ..infra.events import bus

log = logging.getLogger(__name__)

T = TypeVar("T")

# Flood waits longer than this aren't slept through: the transfer fails with
# a clear message instead of appearing frozen for up to an hour.
MAX_FLOOD_WAIT_SECONDS = 300

# One address per Telegram production DC. Any reachable one means "online".
_TELEGRAM_DC_ADDRESSES = (
    ("149.154.175.53", 443),
    ("149.154.167.51", 443),
    ("149.154.175.100", 443),
    ("149.154.167.91", 443),
    ("91.108.56.130", 443),
)
_PROBE_TIMEOUT = 3.0


class ExponentialBackoff:
    """Exponential backoff for Telegram API retries on transient errors.

    Formula: min(base_delay * 2^attempt, max_delay) for attempt in [0, max_attempts - 1].
    Defaults: base_delay=1s, max_delay=30s, max_attempts=10.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        max_attempts: int = 10,
    ) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts

    def next_delay(self, attempt: int) -> float:
        """Compute the retry delay for the given attempt number.

        Args:
            attempt: Zero-based attempt index (0 through max_attempts - 1).

        Returns:
            Delay in seconds: min(base_delay * 2^attempt, max_delay).
        """
        return min(self.base_delay * (2**attempt), self.max_delay)


async def retry_with_backoff(  # noqa: UP047
    operation: Callable[[], Awaitable[T]],
    *,
    transfer_id: str | None = None,
    backoff: ExponentialBackoff | None = None,
) -> T:
    """Retry an async operation with exponential backoff on transient errors.

    Handles FloodWaitError, TimeoutError, and ConnectionError (including
    subclasses like ConnectionResetError). Other OSErrors — disk full,
    permission denied — are not transient and are raised immediately.

    On FloodWaitError, emits a ``rate-limited`` event with the wait_seconds.
    After exhausting all retry attempts, emits a ``transfer-failed`` event
    (if transfer_id is provided) and raises the last exception.

    Args:
        operation: A zero-argument async callable to retry.
        transfer_id: Optional transfer ID for event emission.
        backoff: ExponentialBackoff instance (uses defaults if None).

    Returns:
        The result of a successful ``operation()`` call.

    Raises:
        The last caught exception if all retries are exhausted.
    """
    if backoff is None:
        backoff = ExponentialBackoff()

    from telethon.errors import FloodWaitError

    last_exc: BaseException | None = None

    for attempt in range(backoff.max_attempts):
        try:
            return await operation()
        except FloodWaitError as exc:
            last_exc = exc
            if exc.seconds > MAX_FLOOD_WAIT_SECONDS:
                bus.emit("rate-limited", {"wait_seconds": exc.seconds})
                raise
            # Respect Telegram's requested wait, but also apply our backoff
            wait_seconds = max(exc.seconds, backoff.next_delay(attempt))
            bus.emit("rate-limited", {"wait_seconds": wait_seconds})
            log.warning(
                "FloodWaitError (attempt %d/%d): waiting %.1fs (transfer=%s)",
                attempt + 1,
                backoff.max_attempts,
                wait_seconds,
                transfer_id or "N/A",
            )
            await asyncio.sleep(wait_seconds)
        except TimeoutError as exc:
            last_exc = exc
            delay = backoff.next_delay(attempt)
            log.warning(
                "TimeoutError (attempt %d/%d): retrying in %.1fs (transfer=%s)",
                attempt + 1,
                backoff.max_attempts,
                delay,
                transfer_id or "N/A",
            )
            await asyncio.sleep(delay)
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            last_exc = exc
            delay = backoff.next_delay(attempt)
            log.warning(
                "ConnectionError (attempt %d/%d): retrying in %.1fs (transfer=%s): %s",
                attempt + 1,
                backoff.max_attempts,
                delay,
                transfer_id or "N/A",
                exc,
            )
            await asyncio.sleep(delay)

    # All attempts exhausted — emit transfer-failed if we have a transfer_id
    if transfer_id:
        reason = f"Max retries ({backoff.max_attempts}) exceeded: {last_exc}"
        bus.emit(
            "transfer-failed",
            {
                "transferId": transfer_id,
                "bytesSent": 0,
                "reason": reason,
            },
        )
        log.error(
            "Transfer %s failed after %d attempts: %s",
            transfer_id,
            backoff.max_attempts,
            last_exc,
        )

    # Re-raise the last exception
    raise last_exc  # type: ignore[misc]


def _tcp_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


async def cmd_is_network_available() -> bool:
    """Lightweight TCP probe for Telegram reachability.

    With a proxy configured the proxy itself is probed (Telegram may be
    blocked on the direct route). Otherwise every DC is probed in parallel,
    so a single blocked or down DC doesn't make the app think it's offline.
    """
    from ..telegram.client import proxy_settings

    proxy = proxy_settings()
    if proxy:
        targets = [(str(proxy["host"]), int(proxy["port"]))]
    else:
        targets = list(_TELEGRAM_DC_ADDRESSES)

    probes = [asyncio.to_thread(_tcp_reachable, h, p) for h, p in targets]
    for fut in asyncio.as_completed(probes):
        if await fut:
            return True
    return False


_PROXY_TYPES = {"socks5", "socks4", "http", "mtproxy"}


def _validate_proxy(cfg: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(cfg.get("enabled"))
    kind = str(cfg.get("type") or "socks5").lower()
    host = str(cfg.get("host") or "").strip()
    try:
        port = int(cfg.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    if kind not in _PROXY_TYPES:
        raise ValueError(f"Unsupported proxy type: {kind}")
    if enabled:
        if not host:
            raise ValueError("Proxy host is required.")
        if not 0 < port < 65536:
            raise ValueError("Proxy port must be between 1 and 65535.")
        if kind == "mtproxy" and not cfg.get("secret"):
            raise ValueError("An MTProxy secret is required.")
    return {
        "enabled": enabled,
        "type": kind,
        "host": host,
        "port": port,
        "username": str(cfg.get("username") or ""),
        "password": str(cfg.get("password") or ""),
        "secret": str(cfg.get("secret") or ""),
    }


def cmd_get_proxy() -> dict[str, Any]:
    """Return the proxy settings without secrets (flags say if they're set)."""
    from ..infra import get_store

    cfg = get_store().get("proxy") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    return {
        "enabled": bool(cfg.get("enabled")),
        "type": cfg.get("type") or "socks5",
        "host": cfg.get("host") or "",
        "port": cfg.get("port") or "",
        "username": cfg.get("username") or "",
        "has_password": bool(cfg.get("password")),
        "has_secret": bool(cfg.get("secret")),
    }


async def cmd_set_proxy(cfg: dict[str, Any]) -> bool:
    """Save proxy settings and reconnect through them.

    Empty password/secret fields keep the previously saved values, so the
    UI never needs to read secrets back.
    """
    from ..infra import get_store
    from ..telegram.client import reconnect_with_current_settings

    store = get_store()
    previous = store.get("proxy") or {}
    merged = dict(cfg)
    for secret in ("password", "secret"):
        if not merged.get(secret) and isinstance(previous, dict):
            merged[secret] = previous.get(secret, "")
    store.set("proxy", _validate_proxy(merged))
    store.flush()
    await reconnect_with_current_settings()
    return True


def cmd_log(message: str) -> None:
    log.info("[FRONTEND] %s", message)


def cmd_get_bandwidth() -> dict:
    return get_manager().get_stats()


def cmd_get_stream_info() -> dict:
    cfg = get_stream_config()
    # The server binds a free port at startup; wait briefly if it isn't up yet.
    if not cfg.ready.wait(timeout=10.0):
        raise RuntimeError("Media streaming server is not running")
    return {
        "token": cfg.token,
        "base_url": f"http://127.0.0.1:{cfg.port}",
    }


__all__ = [
    "ExponentialBackoff",
    "retry_with_backoff",
    "cmd_is_network_available",
    "cmd_log",
    "cmd_get_bandwidth",
    "cmd_get_stream_info",
    "cmd_get_proxy",
    "cmd_set_proxy",
]
