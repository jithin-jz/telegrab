# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Telegram Drive.
#
# Run via `python installer/build.py` (preferred) or directly:
#   pyinstaller installer/telegrab.spec --noconfirm
#
# Output:
#   * Windows:  dist-installer/Telegrab.exe          (single-file)
#   * macOS:    dist-installer/Telegrab.app          (Cocoa app bundle)
#   * Linux:    dist-installer/Telegrab/             (onedir)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# SPECPATH is provided by PyInstaller — points to the directory containing
# this .spec file.
SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
ENTRY = BACKEND / "telegrab" / "__main__.py"

if not FRONTEND_DIST.exists():
    raise SystemExit(
        "frontend/dist/ not found. Build the React bundle first:\n"
        "  cd frontend && npm install && npm run build"
    )

# ─────────────────────── icon resolution (optional) ───────────────────────
def _icon():
    if sys.platform == "win32":
        candidates = [
            SPEC_DIR / "app.ico",
        ]
    elif sys.platform == "darwin":
        candidates = [
            SPEC_DIR / "app.icns",
        ]
    else:
        return None
    for p in candidates:
        if p.exists():
            return str(p)
    return None

ICON = _icon()

# ───────────────── Hidden imports & runtime data files ─────────────────
# Telethon dynamically constructs TL types — make sure all submodules ship.
hidden_telethon = collect_submodules("telethon")
# Uvicorn picks loop / http implementations at runtime.
hidden_uvicorn = collect_submodules("uvicorn")
# pywebview's per-platform backend module is imported via importlib.
if sys.platform == "win32":
    hidden_pywebview = [
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.cef",
    ]
elif sys.platform == "darwin":
    hidden_pywebview = ["webview.platforms.cocoa"]
else:
    hidden_pywebview = ["webview.platforms.gtk", "webview.platforms.qt"]

hidden_imports = (
    hidden_telethon
    + hidden_uvicorn
    + hidden_pywebview
    + [
        "telegrab",
        "telegrab.app",
        "telegrab.api",
        "telegrab.api.bridge",
        "telegrab.api.host",
        "telegrab.api.streaming",
        "telegrab.api.rest",
        "telegrab.config",
        "telegrab.infra",
        "telegrab.services",
        "telegrab.services.auth",
        "telegrab.services.files",
        "telegrab.services.folders",
        "telegrab.services.preview",
        "telegrab.services.network",
        "telegrab.services.api_settings",
        "telegrab.telegram",
    ]
)

# Bundle the React frontend as data, plus any data files Telethon ships.
datas = [(str(FRONTEND_DIST), "frontend/dist")] + collect_data_files("telethon")

# ────────────────────────────── Analysis ──────────────────────────────
a = Analysis(
    [str(ENTRY)],
    pathex=[str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Trim test runners and editor helpers we never use.
        "tkinter",
        "unittest",
        "pydoc_data",
        "test",
        "_pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ────────────────────────── Per-platform output ──────────────────────────
APP_NAME = "telegrab"

if sys.platform == "win32":
    # Single-file Windows binary. Slight cold-start cost but trivially
    # distributable.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,           # GUI app — no console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )

elif sys.platform == "darwin":
    # macOS: COLLECT into a folder, then BUNDLE that folder as a .app.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,     # Forward dropped files / URL events
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier="com.telegrab.app",
        info_plist={
            "CFBundleDisplayName": "telegrab",
            "CFBundleShortVersionString": "1.4.0",
            "CFBundleVersion": "1.4.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
            "NSAppleEventsUsageDescription": "telegrab opens external links.",
        },
    )

else:
    # Linux: onedir output. AppImage / tarball packaging is left to CI.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
