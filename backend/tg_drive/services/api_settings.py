"""REST API server settings — bridge commands + supervisor wiring.

The persisted data model and hashing helpers live in
`tg_drive.config.api_settings`. This module owns the *commands* the
frontend calls plus the indirection that lets the bridge ask the running
supervisor to start/stop/restart the server.
"""

from __future__ import annotations

import logging
import secrets
from typing import Callable, Optional

from ..config import (
    STREAM_PORT,
    ApiSettingsFile,
    hash_key,
    load_settings,
    save_settings,
)

log = logging.getLogger(__name__)


# Restart hook is wired in app.py — bridge methods call it after mutating
# settings. Indirection avoids a circular import on the supervisor.
_restart_hook: Optional[Callable[[], None]] = None
_running_probe: Optional[Callable[[], bool]] = None


def set_restart_hook(fn: Callable[[], None]) -> None:
    global _restart_hook
    _restart_hook = fn


def set_running_probe(fn: Callable[[], bool]) -> None:
    global _running_probe
    _running_probe = fn


def _is_running() -> bool:
    if _running_probe is None:
        return False
    try:
        return bool(_running_probe())
    except Exception:  # noqa: BLE001
        return False


def _trigger_restart() -> None:
    if _restart_hook is None:
        log.warning("API restart hook not set")
        return
    try:
        _restart_hook()
    except Exception as exc:  # noqa: BLE001
        log.error("API server restart failed: %s", exc)


def _public_view(settings: ApiSettingsFile) -> dict:
    return {
        "enabled": settings.enabled,
        "port": settings.port,
        "key_set": settings.key_hash is not None,
        "running": _is_running(),
    }


# ──────────────────────────────── commands ────────────────────────────────


async def cmd_get_api_settings() -> dict:
    return _public_view(load_settings())


async def cmd_update_api_settings(enabled: bool, port: int) -> dict:
    if port < 1024:
        raise ValueError("Port must be 1024 or higher")
    if port == STREAM_PORT:
        raise ValueError(
            f"Port {port} is used by the media streaming server"
        )

    settings = load_settings()
    changed = settings.port != int(port) or settings.enabled != bool(enabled)
    settings.enabled = bool(enabled)
    settings.port = int(port)
    save_settings(settings)
    if changed:
        _trigger_restart()
    return _public_view(settings)


async def cmd_regenerate_api_key() -> str:
    settings = load_settings()
    plaintext = secrets.token_hex(32)
    settings.key_hash = hash_key(plaintext)
    save_settings(settings)
    _trigger_restart()
    return plaintext


__all__ = [
    "set_restart_hook",
    "set_running_probe",
    "cmd_get_api_settings",
    "cmd_update_api_settings",
    "cmd_regenerate_api_key",
]
