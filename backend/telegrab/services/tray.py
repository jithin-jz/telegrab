"""System tray icon using pystray (optional dependency)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

log = logging.getLogger(__name__)

_icon = None

try:
    import pystray
    from PIL import Image, ImageDraw
    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False


def _create_icon_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(34, 197, 94, 255))
    return img


def start_tray(on_show: Callable, on_quit: Callable) -> None:
    global _icon
    if not _HAS_PYSTRAY:
        log.info("pystray not installed — skipping system tray")
        return
    menu = pystray.Menu(
        pystray.MenuItem("Show Telegrab", lambda: on_show()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda: on_quit()),
    )
    _icon = pystray.Icon("Telegrab", _create_icon_image(), "Telegrab", menu)
    t = threading.Thread(target=_icon.run, daemon=True)
    t.start()


def stop_tray() -> None:
    global _icon
    if _icon:
        _icon.stop()
        _icon = None
