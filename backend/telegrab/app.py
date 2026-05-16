"""Application entry point.

Run with `python -m telegrab` or via the `telegram-drive` script defined in
`pyproject.toml`. The launch sequence is:

  1. Start the asyncio runtime on a background thread.
  2. Schedule the streaming server (FastAPI on port 14201) on that loop.
  3. Wire up the REST API supervisor and have api_settings commands trigger
     start / restart / stop on it.
  4. Build the Bridge object and create the pywebview window.
  5. pywebview takes over the main thread and blocks until the window closes.
  6. On exit: stop the streaming server, REST API, asyncio runtime.

The frontend assets are served either from the Vite dev server (when
`TELEGRAB_DEV_URL` is set) or from a built `app/dist/` directory. In dev
the user runs `npm run dev` separately, then `python -m telegrab`.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import webview

from . import telegram as tg
from .api import Bridge, RestApiSupervisor, host as host_cmds, serve_streaming
from .infra import bus, get_runtime
from .services import api_settings as api_cmd_module

log = logging.getLogger(__name__)


# ────────────────────────────── HTML bootstrap ──────────────────────────────

# Tiny script injected into the page so the React side has an event bus the
# Python EventBus can dispatch into. The frontend's platform shim's
# `listen()` registers subscribers on this bus; `dispatch()` invokes every
# callback. The shim itself also creates the bus eagerly on first import,
# but we re-inject here as a safety net for early page loads.
_BOOTSTRAP_JS = r"""
(function () {
  if (window.__telegrabBus) { return; }
  const listeners = new Map();
  window.__telegrabBus = {
    subscribe(event, cb) {
      let s = listeners.get(event);
      if (!s) { s = new Set(); listeners.set(event, s); }
      s.add(cb);
      return () => s.delete(cb);
    },
    dispatch(event, payload) {
      const s = listeners.get(event);
      if (!s) { return; }
      for (const cb of s) {
        try { cb({ event, payload }); }
        catch (e) { console.error('event callback failed', e); }
      }
    }
  };
})();
"""


def _resolve_frontend_url() -> str:
    """Return the URL pywebview should load.

    Priority:
      1. TELEGRAB_DEV_URL environment variable (e.g. "http://localhost:5173")
      2. PyInstaller-bundled frontend under sys._MEIPASS (production .exe / .app)
      3. ../../frontend/dist/index.html relative to this file (dev / source run)
      4. Fall back to a tiny error page.
    """
    dev_url = os.environ.get("TELEGRAB_DEV_URL")
    if dev_url:
        return dev_url

    # Production: when PyInstaller bundles the app, frontend/dist is unpacked
    # into sys._MEIPASS at runtime (see installer/telegrab.spec).
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled_index = Path(meipass) / "frontend" / "dist" / "index.html"
        if bundled_index.exists():
            return bundled_index.as_uri()

    # Dev: backend/telegrab/app.py → repo root → frontend/dist/index.html
    repo_root = Path(__file__).resolve().parent.parent.parent
    dist_index = repo_root / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return dist_index.as_uri()

    return "data:text/html," + (
        "<h2>Telegram Drive</h2>"
        "<p>Frontend bundle not found.</p>"
        "<p>Run <code>npm run build</code> in <code>frontend/</code> "
        "or set <code>TELEGRAB_DEV_URL=http://localhost:5173</code>.</p>"
    )


# ─────────────────────────────── lifecycle ───────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram Drive (Python)")
    parser.add_argument(
        "--debug", action="store_true", help="Open the webview devtools"
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("TELEGRAB_LOG", "INFO"),
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )

    runtime = get_runtime()

    # Spawn the streaming server immediately. It's lightweight and idle until
    # a request arrives.
    runtime.spawn(serve_streaming())

    # Wire the REST API supervisor into the api_settings command module so
    # cmd_update_api_settings / cmd_regenerate_api_key can ask it to restart.
    rest_supervisor = RestApiSupervisor(runtime)
    api_cmd_module.set_restart_hook(rest_supervisor.start)
    api_cmd_module.set_running_probe(rest_supervisor.is_running)

    # Start the REST API now if it was enabled in a previous run.
    rest_supervisor.start()

    bridge = Bridge()
    url = _resolve_frontend_url()
    log.info("Loading frontend from: %s", url)

    window = webview.create_window(
        title="Telegrab",
        url=url,
        js_api=bridge,
        width=1200,
        height=800,
        min_size=(900, 600),
        frameless=True,
        easy_drag=False,
        background_color="#0a0a0c",
    )

    bus.attach(window)
    host_cmds.attach_window(window)

    def _on_loaded() -> None:
        try:
            window.evaluate_js(_BOOTSTRAP_JS)
        except Exception as exc:  # noqa: BLE001
            log.warning("Bootstrap inject failed: %s", exc)

    window.events.loaded += _on_loaded

    try:
        webview.start(debug=args.debug)
    finally:
        log.info("Shutting down...")
        try:
            rest_supervisor.stop()
        except Exception:
            pass
        try:
            state = tg.get_state()
            if state.client is not None:
                runtime.run_coro(state.client.disconnect(), timeout=5.0)  # type: ignore[func-returns-value]
        except Exception as exc:  # noqa: BLE001
            log.warning("Client shutdown error: %s", exc)
        runtime.stop()


if __name__ == "__main__":
    main()
