"""Telegram Drive — top-level launcher.

Usage (from the repo root):

    # Production: build the React frontend, then open the desktop window.
    python run.py

    # Dev: spawn `vite` (port 5173) and the Python window. The window
    # loads from the Vite dev server so HMR works.
    python run.py --dev

    # Skip the Vite spawn (e.g. you already have it running):
    python run.py --dev --no-vite

The launcher uses `uv` to manage the virtualenv at `backend/.venv/` and
installs dependencies from `pyproject.toml`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_DIR = REPO_ROOT / "backend"
VENV_DIR = BACKEND_DIR / ".venv"
DIST_INDEX = FRONTEND_DIR / "dist" / "index.html"

VITE_DEV_URL = "http://localhost:5173"
VITE_READY_TIMEOUT_S = 30


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _ensure_venv() -> Path:
    py = _venv_python()
    if py.exists():
        return py
    print(f"[run.py] Creating virtualenv at {VENV_DIR} ...")
    uv = shutil.which("uv")
    if uv:
        subprocess.check_call([uv, "sync"], cwd=str(BACKEND_DIR))
    else:
        import venv
        venv.EnvBuilder(with_pip=True, upgrade_deps=True).create(str(VENV_DIR))
        subprocess.check_call(
            [str(py), "-m", "pip", "install", "-e", "."], cwd=str(BACKEND_DIR)
        )
    return py


def _ensure_frontend_build() -> None:
    if DIST_INDEX.exists():
        return
    print("[run.py] React bundle not found — running `npm run build` in frontend/ ...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm) is None:
        sys.exit(
            "node/npm not found on PATH. Install Node.js 18+ then re-run.\n"
            "Or build the frontend manually: cd frontend && npm run build"
        )
    if not (FRONTEND_DIR / "node_modules").exists():
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND_DIR))
    subprocess.check_call([npm, "run", "build"], cwd=str(FRONTEND_DIR))


def _spawn_vite() -> subprocess.Popen:
    print("[run.py] Starting Vite dev server ...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm) is None:
        sys.exit("node/npm not found on PATH; cannot start Vite.")
    return subprocess.Popen(
        [npm, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        env=os.environ.copy(),
    )


def _wait_for_vite() -> None:
    """Poll until the Vite dev server responds, or timeout."""
    import urllib.error
    import urllib.request

    print(f"[run.py] Waiting for Vite at {VITE_DEV_URL} ...", end="", flush=True)
    start = time.time()
    while time.time() - start < VITE_READY_TIMEOUT_S:
        try:
            with urllib.request.urlopen(VITE_DEV_URL, timeout=1):
                print(" ready.")
                return
        except urllib.error.URLError:
            print(".", end="", flush=True)
            time.sleep(0.5)
    print(" timed out (continuing anyway).")


def _run_python_app(py: Path, dev: bool, debug: bool) -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    if dev:
        env["TELEGRAB_DEV_URL"] = VITE_DEV_URL
    cmd = [str(py), "-m", "telegrab"]
    if debug:
        cmd.append("--debug")
    print(f"[run.py] Launching: {' '.join(cmd)}")
    return subprocess.call(cmd, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run with Vite dev server + HMR (otherwise loads built bundle)",
    )
    parser.add_argument(
        "--no-vite",
        action="store_true",
        help="With --dev, skip spawning Vite (assume it's already running)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Open the webview devtools"
    )
    args = parser.parse_args()

    py = _ensure_venv()

    vite_proc: subprocess.Popen | None = None
    try:
        if args.dev:
            if not args.no_vite:
                vite_proc = _spawn_vite()
            _wait_for_vite()
        else:
            _ensure_frontend_build()

        return _run_python_app(py, dev=args.dev, debug=args.debug)
    finally:
        if vite_proc is not None and vite_proc.poll() is None:
            print("[run.py] Stopping Vite ...")
            vite_proc.terminate()
            try:
                vite_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite_proc.kill()


if __name__ == "__main__":
    sys.exit(main())
