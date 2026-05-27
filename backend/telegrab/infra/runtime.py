"""Background asyncio runtime.

pywebview owns the main thread on Windows and macOS, so we run a dedicated
event loop on a worker thread. Every JS-API method on the bridge is
synchronous from pywebview's point of view but schedules its real work on
this loop via `run_coro`.

`run_coro` enforces a timeout by default so a hung Telegram RPC can't
freeze the JS bridge call indefinitely. Long-running operations (uploads,
downloads, streaming) explicitly opt out by passing `timeout=None`.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from collections.abc import Awaitable
from concurrent.futures import Future
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


# Default timeout (seconds) for routine bridge calls. Network round-trips
# to Telegram + a bit of slack. Long-running ops pass `timeout=None`.
DEFAULT_BRIDGE_TIMEOUT = 60.0

# Crash recovery constants
_MAX_RESTARTS = 3
_RESTART_WINDOW = 5.0  # seconds


class AsyncRuntime:
    """A long-lived asyncio loop running on a background thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stopping = False  # True when stop() is called (clean shutdown)
        self._restart_count: int = 0
        self._restart_window_start: float = 0.0

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stopping = False
        self._thread = threading.Thread(
            target=self._run, name="tg-drive-asyncio", daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if not self._ready.is_set():
            raise RuntimeError("AsyncRuntime failed to start")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        except Exception as exc:  # noqa: BLE001
            log.error("AsyncRuntime loop crashed: %s", exc, exc_info=True)
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            except Exception:  # noqa: BLE001
                pass
            finally:
                loop.close()
                self._loop = None

            # Trigger crash recovery if this was not a clean shutdown
            if not self._stopping:
                self._attempt_recovery()

    def _attempt_recovery(self) -> None:
        """Attempt to restart the runtime after an unexpected crash.

        Allows up to _MAX_RESTARTS restarts within a _RESTART_WINDOW second
        window. On successful restart, re-establishes the Telegram connection
        and emits a recovery toast. On failure (all attempts exhausted), emits
        a fatal toast indicating manual restart is required.
        """
        from ..infra.events import bus

        now = time.monotonic()

        # Reset the restart counter if we're outside the window
        if now - self._restart_window_start > _RESTART_WINDOW:
            self._restart_count = 0
            self._restart_window_start = now

        self._restart_count += 1

        if self._restart_count > _MAX_RESTARTS:
            log.critical(
                "AsyncRuntime: all %d restart attempts exhausted within %.1fs. "
                "Manual restart required.",
                _MAX_RESTARTS,
                _RESTART_WINDOW,
            )
            bus.emit(
                "toast",
                {
                    "type": "fatal",
                    "title": "Connection Lost",
                    "message": (
                        "The background runtime could not be restored after "
                        f"{_MAX_RESTARTS} attempts. Please restart the application."
                    ),
                },
            )
            return

        log.warning(
            "AsyncRuntime: attempting restart %d/%d",
            self._restart_count,
            _MAX_RESTARTS,
        )

        try:
            # Reset state for a fresh start
            self._thread = None
            self._ready.clear()

            # Start a new loop + thread
            self._thread = threading.Thread(
                target=self._run, name="tg-drive-asyncio", daemon=True
            )
            self._thread.start()
            self._ready.wait(timeout=5.0)

            if not self._ready.is_set():
                raise RuntimeError("New loop failed to become ready")

            # Re-establish Telegram connection
            self._reconnect_telegram()

            log.info(
                "AsyncRuntime: successfully recovered (attempt %d)", self._restart_count
            )
            bus.emit(
                "toast",
                {
                    "type": "recovery",
                    "title": "Connection Restored",
                    "message": (
                        "Temporary disconnection detected. "
                        "The connection has been restored."
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.error(
                "AsyncRuntime: restart attempt %d failed: %s",
                self._restart_count,
                exc,
            )
            # Recurse to try again (will be bounded by _MAX_RESTARTS)
            self._attempt_recovery()

    def _reconnect_telegram(self) -> None:
        """Re-establish the Telegram client connection after recovery.

        Runs on the recovery thread (not the event loop thread).
        Uses the existing api_id/api_hash from TelegramState to reconnect.
        """
        from ..telegram.client import ensure_client, get_state

        state = get_state()
        if state.api_id is None or state.api_hash is None:
            log.info("AsyncRuntime: no Telegram credentials stored; skipping reconnect")
            return

        # Disconnect old client if it still holds a reference
        if state.client is not None:
            state.client = None

        # Use run_coro to reconnect on the new loop
        try:
            self.run_coro(
                ensure_client(state.api_id, state.api_hash),
                timeout=10.0,
            )
            log.info("AsyncRuntime: Telegram client reconnected")
        except Exception as exc:  # noqa: BLE001
            log.warning("AsyncRuntime: Telegram reconnect failed: %s", exc)
            # Non-fatal — the runtime is running, user can retry manually

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        return self._loop

    def run_coro(
        self,
        coro: Awaitable[T],
        timeout: float | None = DEFAULT_BRIDGE_TIMEOUT,
    ) -> T:
        """Run a coroutine on the runtime loop and block until it finishes.

        On timeout the underlying task is cancelled and a
        :class:`TimeoutError` is raised so the caller can map it to a
        user-friendly bridge error.
        """
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        fut: Future[T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            fut.cancel()
            log.warning("run_coro timed out after %.1fs", timeout or 0)
            raise TimeoutError(
                f"Operation timed out after {timeout:.1f}s"
                if timeout
                else "Operation timed out"
            ) from exc

    def spawn(self, coro: Awaitable[T]) -> Future[T]:
        """Schedule a coroutine on the loop without blocking."""
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        self._stopping = True
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._loop = None
        self._thread = None
        self._ready.clear()


# Module-level singleton — created in app.main() and shared everywhere.
_runtime: AsyncRuntime | None = None


def get_runtime() -> AsyncRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AsyncRuntime()
        _runtime.start()
    return _runtime
