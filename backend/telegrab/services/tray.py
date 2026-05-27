"""System tray icon using pystray (optional dependency)."""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

_icon = None

try:
    import pystray
    from PIL import Image, ImageDraw

    _HAS_PYSTRAY = True
except ImportError:
    _HAS_PYSTRAY = False


def _load_icon_image():
    """Load the app icon from disk, fall back to a generated purple square."""
    # Try to load the real app.ico
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(Path(meipass) / "app.ico")
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates.append(repo_root / "assets" / "icons" / "app.ico")

    for path in candidates:
        if path.exists():
            try:
                img = Image.open(str(path))
                return img.resize((64, 64), Image.LANCZOS)
            except Exception:
                pass

    # Fallback: purple rounded square with T
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 63, 63], radius=12, fill=(99, 102, 241, 255))
    # T shape
    draw.line([(20, 24), (44, 24)], fill=(255, 255, 255, 255), width=6)
    draw.line([(32, 24), (32, 46)], fill=(255, 255, 255, 255), width=6)
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
    _icon = pystray.Icon("Telegrab", _load_icon_image(), "Telegrab", menu)
    t = threading.Thread(target=_icon.run, daemon=True)
    t.start()


def stop_tray() -> None:
    global _icon
    if _icon:
        _icon.stop()
        _icon = None
