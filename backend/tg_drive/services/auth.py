"""Auth use cases — orchestrate Telethon flows + state transitions.

Mirrors `src-tauri/src/commands/auth.rs`. The bridge layer in
`tg_drive.api.bridge` wraps each function so JS can invoke it.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from .. import telegram as tg

log = logging.getLogger(__name__)


# ───────────────────────── connection bookkeeping ─────────────────────────


async def cmd_connect(api_id: int, api_hash: str | None = None) -> bool:
    state = tg.get_state()
    state.api_id = int(api_id)
    if api_hash is not None:
        state.api_hash = api_hash
    if state.api_hash is None:
        # No api_hash yet — defer creation until auth flow provides one.
        return True
    await tg.ensure_client(int(api_id), state.api_hash)
    return True


async def cmd_check_connection() -> bool:
    """Return True if the client is connected and responsive."""
    state = tg.get_state()
    client = state.client

    if client is not None:
        try:
            if client.is_connected():
                await client.get_me()  # ping
                return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Connection check failed: %s", exc)

    if state.api_id is not None and state.api_hash is not None:
        state.client = None
        try:
            client = await tg.ensure_client(state.api_id, state.api_hash)
            await client.get_me()
            return True
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Auto-reconnect failed: {exc}") from exc

    return False


async def cmd_logout() -> bool:
    await tg.logout_and_reset()
    return True


# ───────────────────────────── phone-code flow ─────────────────────────────


async def cmd_auth_request_code(phone: str, api_id: int, api_hash: str) -> str:
    if not api_hash.strip():
        raise ValueError("API Hash cannot be empty.")

    client = await tg.ensure_client(int(api_id), api_hash)

    state = tg.get_state()
    state.pending_phone = phone

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            sent = await client.send_code_request(phone)
            state.pending_phone_code_hash = sent.phone_code_hash
            return "code_sent"
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            log.warning("send_code_request attempt %d failed: %s", attempt, msg)
            if "AUTH_RESTART" in msg or "500" in msg:
                last_error = exc
                continue
            raise RuntimeError(tg.map_error(exc)) from exc

    raise RuntimeError(
        f"Telegram Error after retry: {last_error}"
        if last_error
        else "Failed to send code"
    )


async def cmd_auth_sign_in(code: str) -> dict[str, Any]:
    state = tg.get_state()
    client = state.client
    if client is None:
        raise RuntimeError("Client not initialized")
    if not state.pending_phone or not state.pending_phone_code_hash:
        raise RuntimeError("No login session found (restart flow)")

    try:
        await client.sign_in(
            phone=state.pending_phone,
            code=code,
            phone_code_hash=state.pending_phone_code_hash,
        )
        return {"success": True, "next_step": "dashboard", "error": None}
    except SessionPasswordNeededError:
        return {"success": False, "next_step": "password", "error": None}
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
        raise RuntimeError(f"Sign in failed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Sign in failed: {exc}") from exc


async def cmd_auth_check_password(password: str) -> dict[str, Any]:
    state = tg.get_state()
    client = state.client
    if client is None:
        raise RuntimeError("Client not initialized")
    try:
        await client.sign_in(password=password)
        return {"success": True, "next_step": "dashboard", "error": None}
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"2FA Failed: {exc}") from exc


# ───────────────────────────── QR-login flow ─────────────────────────────


async def cmd_auth_qr_login(api_id: int, api_hash: str) -> str:
    if not api_hash.strip():
        raise ValueError("API Hash cannot be empty.")

    client = await tg.ensure_client(int(api_id), api_hash)
    state = tg.get_state()

    if state.pending_qr_task is not None:
        state.pending_qr_task.cancel()
        state.pending_qr_task = None
    state.pending_qr_login = None

    try:
        qr = await client.qr_login()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ExportLoginToken failed: {exc}") from exc

    state.pending_qr_login = qr
    return qr.url


async def cmd_auth_qr_poll() -> dict[str, Any]:
    state = tg.get_state()
    client = state.client
    qr = state.pending_qr_login
    if client is None:
        raise RuntimeError("Client not initialized")

    try:
        if await client.is_user_authorized():
            state.pending_qr_login = None
            state.pending_qr_task = None
            return {"success": True, "next_step": "dashboard", "error": None}
    except Exception as exc:  # noqa: BLE001
        log.debug("is_user_authorized check failed: %s", exc)

    if qr is None:
        return {"success": False, "next_step": "waiting", "error": None}

    try:
        await asyncio.wait_for(qr.wait(), timeout=1.0)
        state.pending_qr_login = None
        return {"success": True, "next_step": "dashboard", "error": None}
    except asyncio.TimeoutError:
        return {"success": False, "next_step": "waiting", "error": None}
    except SessionPasswordNeededError:
        return {"success": False, "next_step": "password", "error": None}
    except Exception as exc:  # noqa: BLE001
        log.warning("QR poll wait failed: %s", exc)
        return {"success": False, "next_step": "waiting", "error": None}


__all__ = [
    "cmd_connect",
    "cmd_check_connection",
    "cmd_logout",
    "cmd_auth_request_code",
    "cmd_auth_sign_in",
    "cmd_auth_check_password",
    "cmd_auth_qr_login",
    "cmd_auth_qr_poll",
]
