"""Background asyncio runtime.

pywebview owns the main thread on Windows and macOS, so we run a dedicated
event loop on a worker thread. Every JS-API method on the bridge is
synchronous from pywebview's point of view but schedules its real work on
this loop via `run_coro`.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable
from concurrent.futures import Future
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncRuntime:
    """A long-lived asyncio loop running on a background thread."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
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
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            finally:
                loop.close()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        return self._loop

    def run_coro(self, coro: Awaitable[T], timeout: float | None = None) -> T:
        """Run a coroutine on the runtime loop and block until it finishes."""
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        fut: Future[T] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def spawn(self, coro: Awaitable[T]) -> Future[T]:
        """Schedule a coroutine on the loop without blocking."""
        if self._loop is None:
            raise RuntimeError("AsyncRuntime not started")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
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
