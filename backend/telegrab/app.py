"""Application entry point.

Run with `python -m telegrab` or via the `telegrab` script defined in
`pyproject.toml`. The launch sequence is:

  1. Configure logging (rotating file in the app data dir).
  2. Enforce a single running instance.
  3. Start the asyncio runtime on a background thread and schedule the
     media streaming server (pure asyncio, 127.0.0.1) on that loop.
  4. Build the Bridge object and create the pywebview window.
  5. pywebview takes over the main thread and blocks until the window closes.
  6. On exit: flush pending settings/bandwidth, disconnect Telegram, stop
     the asyncio runtime.

`--self-test` runs the import/bundle checks used by CI smoke tests and
exits without opening a window.

The frontend assets are served either from the Vite dev server (when
`TELEGRAB_DEV_URL` is set) or from a built `app/dist/` directory. In dev
the user runs `npm run dev` separately, then `python -m telegrab`.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
from pathlib import Path

# Hide any console window on Windows (frozen exe with console=False can still
# flash a conhost if a subprocess inherits the creation flags).
if sys.platform == "win32":
    import ctypes

    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

    # Prevent child processes from spawning visible console windows.
    import subprocess

    _startupinfo = subprocess.STARTUPINFO()
    _startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _startupinfo.wShowWindow = 0
    _original_popen_init = subprocess.Popen.__init__

    def _patched_popen_init(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        kwargs.setdefault("startupinfo", _startupinfo)
        _original_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _patched_popen_init

import webview

from . import telegram as tg
from .api import Bridge, serve_streaming
from .api import host as host_cmds
from .infra import bus, get_runtime

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


def _resolve_icon() -> str | None:
    """Return the path to the app icon for the window/taskbar."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        ico = Path(meipass) / "app.ico"
        if ico.exists():
            return str(ico)

    repo_root = Path(__file__).resolve().parent.parent.parent
    ico = repo_root / "assets" / "icons" / "app.ico"
    if ico.exists():
        return str(ico)
    return None


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
        return f"{dev_url}?platform=desktop"

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
        "<h2>Telegrab</h2>"
        "<p>Frontend bundle not found.</p>"
        "<p>Run <code>npm run build</code> in <code>frontend/</code> "
        "or set <code>TELEGRAB_DEV_URL=http://localhost:5173</code>.</p>"
    )


# ─────────────────────────────── lifecycle ───────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegrab (Python)")
    parser.add_argument(
        "--debug", action="store_true", help="Open the webview devtools"
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("TELEGRAB_LOG", "INFO"),
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify the build (imports, crypto, bundled frontend) and exit",
    )
    args = parser.parse_args()

    if args.self_test:
        sys.exit(_self_test())

    from .config import app_data_dir
    from .infra import setup_logging

    setup_logging(app_data_dir(), level=args.log_level)

    # Enforce single instance — exit if another is already running
    from .infra.single_instance import ensure_single_instance

    if not ensure_single_instance():
        sys.exit(0)

    runtime = get_runtime()

    # Spawn the streaming server immediately. It's lightweight and idle until
    # a request arrives.
    runtime.spawn(serve_streaming())

    bridge = Bridge()
    url = _resolve_frontend_url()
    icon = _resolve_icon()
    log.info("Loading frontend from: %s", url)

    window_kwargs: dict = {
        "title": "Telegrab",
        "url": url,
        "js_api": bridge,
        "width": 1200,
        "height": 800,
        "min_size": (900, 600),
        "frameless": False,
        "easy_drag": False,
        "background_color": "#0a0a0c",
    }

    window = webview.create_window(**window_kwargs)

    bus.attach(window)
    host_cmds.attach_window(window)

    # Start system tray
    from .services.tray import start_tray, stop_tray

    def _tray_show():
        if window:
            window.show()

    def _tray_quit():
        if window:
            window.destroy()

    def _on_loaded() -> None:
        try:
            window.evaluate_js(_BOOTSTRAP_JS)
        except Exception as exc:  # noqa: BLE001
            log.warning("Bootstrap inject failed: %s", exc)

        # Remove ciphertext left behind by an upload interrupted by a crash.
        from .services.vault import purge_temp_files

        purge_temp_files()

        # Start tray in background
        try:
            start_tray(_tray_show, _tray_quit)
        except Exception as exc:  # noqa: BLE001
            log.warning("Tray icon failed to start: %s", exc)

    window.events.loaded += _on_loaded

    def _on_maximized():
        bus.emit("window-maximized", True)

    def _on_restored():
        bus.emit("window-maximized", False)

    window.events.maximized += _on_maximized
    window.events.restored += _on_restored

    try:
        webview.start(debug=args.debug, icon=icon)
    finally:
        log.info("Shutting down...")
        with contextlib.suppress(Exception):
            stop_tray()
        # Persist anything still sitting in debounce timers.
        from .infra import get_manager, get_store

        for flush in (get_store().flush, get_manager().flush):
            try:
                flush()
            except Exception as exc:  # noqa: BLE001
                log.warning("Flush on shutdown failed: %s", exc)
        try:
            state = tg.get_state()
            if state.client is not None:
                from .telegram.client import _shutdown_client

                # Closes pooled transfer connections, then the main client.
                runtime.run_coro(_shutdown_client(state), timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            log.warning("Client shutdown error: %s", exc)
        runtime.stop()


def _self_test() -> int:
    """Smoke-test a build without opening a window. Returns an exit code."""
    problems: list[str] = []
    try:
        import cryptg  # noqa: F401
    except ImportError:
        problems.append("cryptg native crypto is missing")
    try:
        from .services import files, folders, preview, updater, vault  # noqa: F401
        from .telegram import fast_transfer  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        problems.append(f"import failed: {exc!r}")
    try:
        import io

        from .services.tray import _HAS_PYSTRAY, _load_icon_image

        if not _HAS_PYSTRAY:
            problems.append("system tray support (pystray/Pillow) is missing")
        else:
            # pystray converts the image to an .ico on Windows.
            _load_icon_image().save(io.BytesIO(), format="ICO")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"tray icon failed: {exc!r}")
    if os.environ.get(
        "TELEGRAB_DEV_URL"
    ) is None and not _resolve_frontend_url().startswith("file:"):
        problems.append("frontend bundle not found")
    for problem in problems:
        print(f"self-test: {problem}", file=sys.stderr)  # noqa: T201
    if not problems:
        print("self-test: ok")  # noqa: T201
    return 1 if problems else 0


if __name__ == "__main__":
    main()
