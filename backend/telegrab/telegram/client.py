"""Telethon client lifecycle & shared state.

Holds the singleton `TelegramState` plus the `ensure_client` /
`logout_and_reset` lifecycle helpers. All state is touched only from inside
the asyncio loop owned by `infra.AsyncRuntime`, so explicit locks aren't
needed.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.tl.custom import QRLogin

from ..config import session_path

log = logging.getLogger(__name__)

_PEER_CACHE_MAX = 500


class _BoundedOrderedDict(OrderedDict):
    """OrderedDict that evicts the oldest entry when exceeding max size."""

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        if len(self) > _PEER_CACHE_MAX:
            self.popitem(last=False)


# ──────────────────────────── shared state ────────────────────────────


@dataclass
class TelegramState:
    """Mutable state for the Telegram session.

    Touched only on the asyncio runtime loop, so no locks.
    """

    client: TelegramClient | None = None
    api_id: int | None = None
    api_hash: str | None = None

    # Auth flow state
    pending_phone: str | None = None
    pending_phone_code_hash: str | None = None
    pending_qr_login: QRLogin | None = None
    pending_qr_task: asyncio.Task | None = None

    # peer_cache: folder_id (int) → Telethon entity (User/Channel/Chat)
    peer_cache: _BoundedOrderedDict = field(default_factory=_BoundedOrderedDict)

    # Transfer IDs that have been requested to cancel.
    cancelled_transfers: set[str] = field(default_factory=set)


_state = TelegramState()
_connect_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _connect_lock
    if _connect_lock is None:
        _connect_lock = asyncio.Lock()
    return _connect_lock


def get_state() -> TelegramState:
    return _state


# ─────────────────────────── client lifecycle ───────────────────────────


async def ensure_client(api_id: int, api_hash: str | None = None) -> TelegramClient:
    """Create or return the shared TelegramClient.

    A new client is created the first time, or whenever the api_id changes.
    Uses an asyncio lock to prevent concurrent session access (which causes
    SQLite "database is locked" errors from Telethon).
    """
    async with _get_lock():
        return await _ensure_client_inner(api_id, api_hash)


async def _ensure_client_inner(api_id: int, api_hash: str | None = None) -> TelegramClient:
    state = _state

    if state.client is not None and state.api_id == api_id:
        if not state.client.is_connected():
            try:
                await state.client.connect()
            except Exception as exc:  # noqa: BLE001
                log.warning("Reconnect failed, recreating client: %s", exc)
                await _shutdown_client(state)

        if state.client is not None:
            return state.client

    # Recreate from scratch.
    await _shutdown_client(state)

    if api_hash is None:
        api_hash = state.api_hash
    if not api_hash:
        raise ValueError("api_hash is required to (re)create the client")

    session_str = str(session_path())
    log.info("Creating Telethon client (api_id=%s, session=%s)", api_id, session_str)

    try:
        client = _build_client(session_str, api_id, api_hash)
        await client.connect()
    except Exception as exc:
        log.warning("Session open failed (%s); recreating session file", exc)
        for ext in ("", "-journal", "-wal", "-shm"):
            with contextlib.suppress(FileNotFoundError, OSError):
                Path(session_str + ext).unlink()
        client = _build_client(session_str, api_id, api_hash)
        await client.connect()

    state.client = client
    state.api_id = api_id
    state.api_hash = api_hash
    return client


def _check_cryptg() -> None:
    """Verify that the cryptg C-extension is active.

    cryptg provides native AES-IGE encryption, which is 5-10x faster than
    Telethon's pure-Python fallback. If it is missing at runtime (e.g. due
    to a missing Visual C++ Redistributable on Windows), all MTProto crypto
    will be slow — this warning makes the problem immediately visible in logs.
    """
    try:
        import cryptg  # noqa: F401
        log.info("cryptg native crypto acceleration is active")
    except ImportError:
        log.warning(
            "cryptg is not available — falling back to slow pure-Python AES. "
            "Install the Visual C++ Redistributable (Windows) or rebuild cryptg "
            "to restore full transfer speed."
        )


def _build_client(session_str: str, api_id: int, api_hash: str) -> TelegramClient:
    from .. import __version__
    _check_cryptg()
    return TelegramClient(
        session_str,
        api_id,
        api_hash,
        device_model="Desktop",
        system_version="Telegrab",
        app_version=__version__,
        lang_code="en",
        system_lang_code="en",
        # ── Performance tuning ─────────────────────────────────────────
        # Retry transient connection failures up to 5 times before giving up.
        connection_retries=5,
        # Wait 1 second between connection retries (avoids thundering-herd).
        retry_delay=1,
        # Auto-sleep on FloodWaitError up to 60 s; longer waits raise instead.
        flood_sleep_threshold=60,
        # Retry individual RPC requests up to 5 times on network errors.
        request_retries=5,
    )


async def _shutdown_client(state: TelegramState) -> None:
    """Disconnect the client and reset transient state."""
    if state.pending_qr_task is not None:
        state.pending_qr_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await state.pending_qr_task
        state.pending_qr_task = None
    state.pending_qr_login = None

    if state.client is not None:
        try:
            await state.client.disconnect()  # type: ignore[func-returns-value]
        except Exception as exc:  # noqa: BLE001
            log.warning("Client disconnect raised: %s", exc)
    state.client = None


async def logout_and_reset() -> None:
    """Sign out from Telegram and wipe local session state."""
    state = _state
    if state.client is not None:
        try:
            await state.client.log_out()
        except Exception as exc:  # noqa: BLE001
            log.warning("log_out failed (non-fatal): %s", exc)

    await _shutdown_client(state)

    state.api_id = None
    state.api_hash = None
    state.pending_phone = None
    state.pending_phone_code_hash = None
    state.peer_cache.clear()
    state.cancelled_transfers.clear()

    session_str = str(session_path())
    for ext in ("", "-journal", "-wal", "-shm"):
        with contextlib.suppress(FileNotFoundError, OSError):
            Path(session_str + ext).unlink()
