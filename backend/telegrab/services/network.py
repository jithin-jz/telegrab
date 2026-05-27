"""Network probes, log forwarding, bandwidth read-out, stream-info.

Renamed from `commands/misc.py` to `network.py` since the contents are
about runtime/network state more than miscellaneous helpers.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ..config import get_stream_config
from ..infra import get_manager
from ..infra.events import bus

log = logging.getLogger(__name__)

T = TypeVar("T")


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
    OSError subclasses like ConnectionResetError).

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
        except (ConnectionError, OSError) as exc:
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
    "ExponentialBackoff",
    "retry_with_backoff",
    "cmd_is_network_available",
    "cmd_log",
    "cmd_get_bandwidth",
    "cmd_get_stream_info",
]
