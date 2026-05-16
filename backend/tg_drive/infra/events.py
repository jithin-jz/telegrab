"""Tauri-style event bus, bridged to JS through `window.evaluate_js`.

The Rust backend used `app.emit("upload-progress", payload)` and the React
frontend listened with `listen('upload-progress', cb)` from
`@tauri-apps/api/event`. pywebview has no equivalent event channel, so we
build a tiny one on top of `evaluate_js`:

    Python                                 JS
    ──────────                             ────────────────────────────────
    EventBus.emit("upload-progress", x) ─► window.__tgDriveBus.dispatch(
                                                "upload-progress", x)

The companion JS shim (`@tauri-apps/api/event` → `src/lib/platform/event.ts`)
subscribes to `window.__tgDriveBus` and delivers payloads to listeners with
the exact same signature the original Tauri code expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import webview

log = logging.getLogger(__name__)


class EventBus:
    """Pushes events into the JS runtime."""

    def __init__(self) -> None:
        self._window: webview.Window | None = None

    def attach(self, window: "webview.Window") -> None:
        self._window = window

    def emit(self, event: str, payload: Any) -> None:
        """Deliver `payload` to any JS listener registered for `event`.

        Safe to call from any thread; pywebview serialises `evaluate_js`
        calls onto the GUI thread internally.
        """
        if self._window is None:
            return
        try:
            payload_json = json.dumps(payload, default=_default_encoder)
            event_json = json.dumps(event)
            script = (
                f"window.__tgDriveBus && "
                f"window.__tgDriveBus.dispatch({event_json}, {payload_json});"
            )
            self._window.evaluate_js(script)
        except Exception as exc:  # noqa: BLE001
            log.warning("EventBus.emit(%s) failed: %s", event, exc)


def _default_encoder(obj: Any) -> Any:
    """JSON encoder fallback for objects Telethon hands back (datetimes, etc)."""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Cannot JSON-serialise {type(obj).__name__}")


# Singleton — `attach()` is called in app.main().
bus = EventBus()
