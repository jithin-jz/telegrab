"""Telethon → frontend error string mapping.

Mirrors the Rust `map_error` helper so the React UI receives the same
sentinel strings (`FLOOD_WAIT_<seconds>`, `PASSWORD_REQUIRED`, …) regardless
of which backend it talks to.
"""

from __future__ import annotations

from telethon.errors import FloodWaitError, RPCError, SessionPasswordNeededError


def map_error(exc: BaseException) -> str:
    if isinstance(exc, FloodWaitError):
        return f"FLOOD_WAIT_{exc.seconds}"
    if isinstance(exc, SessionPasswordNeededError):
        return "PASSWORD_REQUIRED"
    if isinstance(exc, RPCError):
        return f"{exc.__class__.__name__}: {exc}"
    return str(exc)
