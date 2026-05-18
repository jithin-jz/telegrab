"""Build the telegrab desktop installer.

Usage (run on the platform you want to build for — PyInstaller does NOT
cross-compile):

    python installer/build.py

Steps:
  1. Ensure the backend venv exists and has PyInstaller installed.
  2. Build the React bundle (npm install + npm run build) if missing.
  3. Run PyInstaller against `installer/telegrab.spec`.
  4. Report the output path.

Output:
  * Windows: dist-installer/telegrab.exe
  * macOS:   dist-installer/telegrab.app
  * Linux:   dist-installer/telegrab/
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "installer"
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
SPEC = INSTALLER / "telegrab.spec"
VENV_DIR = BACKEND / ".venv"

DIST_OUT = ROOT / "dist-installer"
WORK_OUT = ROOT / "build-installer"

PYINSTALLER_VERSION = "6.11.1"


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _ensure_venv() -> Path:
    py = _venv_python()
    if py.exists():
        return py
    print(f"[build] Creating virtualenv at {VENV_DIR} ...")
    venv.EnvBuilder(with_pip=True, upgrade_deps=True).create(str(VENV_DIR))
    print("[build] Installing backend dependencies using uv ...")
    subprocess.check_call(
        ["uv", "sync"], cwd=str(BACKEND)
    )
    return py


def _ensure_pyinstaller(py: Path) -> None:
    """Install PyInstaller into the backend venv if it's not already there."""
    result = subprocess.run(
        [str(py), "-c", "import PyInstaller; print(PyInstaller.__version__)"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"[build] PyInstaller {result.stdout.strip()} already installed.")
        return
    print(f"[build] Installing pyinstaller=={PYINSTALLER_VERSION} ...")
    subprocess.check_call(
        [str(py), "-m", "pip", "install", f"pyinstaller=={PYINSTALLER_VERSION}"]
    )


def _ensure_frontend_build(force: bool) -> None:
    dist_index = FRONTEND / "dist" / "index.html"
    if dist_index.exists() and not force:
        print(f"[build] Frontend bundle already present at {FRONTEND / 'dist'}")
        return
    print("[build] Building React frontend ...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    if shutil.which(npm) is None:
        sys.exit("node/npm not found on PATH — install Node.js 18+ first.")
    if not (FRONTEND / "node_modules").exists():
        subprocess.check_call([npm, "install"], cwd=str(FRONTEND))
    subprocess.check_call([npm, "run", "build"], cwd=str(FRONTEND))


def _run_pyinstaller(py: Path, clean: bool) -> None:
    if clean:
        for d in (DIST_OUT, WORK_OUT):
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

    cmd = [
        str(py),
        "-m",
        "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--distpath",
        str(DIST_OUT),
        "--workpath",
        str(WORK_OUT),
    ]
    print(f"[build] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))


def _run_inno_setup() -> None:
    """Run Inno Setup to produce a proper Windows installer."""
    if sys.platform != "win32":
        print("[build] Skipping Inno Setup (Windows only).")
        return

    iss = INSTALLER / "telegrab_setup.iss"
    if not iss.exists():
        sys.exit(f"[build] Inno Setup script not found: {iss}")

    # Find ISCC.exe
    iscc_paths = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    iscc = next((p for p in iscc_paths if p.exists()), shutil.which("iscc"))
    if not iscc:
        sys.exit(
            "[build] Inno Setup not found. Install it:\n"
            "  winget install JRSoftware.InnoSetup"
        )

    print(f"[build] Running Inno Setup: {iscc}")
    subprocess.check_call([str(iscc), str(iss)])
    setup_exe = DIST_OUT / "Telegrab-1.4.0-Setup.exe"
    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"[build] Installer created: {setup_exe} ({size_mb:.1f} MB)")


def _report() -> None:
    print()
    print("=" * 60)
    print("Build complete.")
    print()
    if sys.platform == "win32":
        artifact = DIST_OUT / "telegrab.exe"
    elif sys.platform == "darwin":
        artifact = DIST_OUT / "telegrab.app"
    else:
        artifact = DIST_OUT / "telegrab"
    if artifact.exists():
        size_mb = (
            sum(p.stat().st_size for p in artifact.rglob("*") if p.is_file())
            if artifact.is_dir()
            else artifact.stat().st_size
        ) / (1024 * 1024)
        print(f"Output:   {artifact}")
        print(f"Size:     {size_mb:.1f} MB")
        print(f"Platform: {platform.system()} {platform.release()} {platform.machine()}")
    else:
        print(f"Expected artifact not found at {artifact}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe dist-installer/ and build-installer/ before building",
    )
    parser.add_argument(
        "--rebuild-frontend",
        action="store_true",
        help="Force a fresh `npm run build` even if dist/ exists",
    )
    parser.add_argument(
        "--installer",
        action="store_true",
        help="Run Inno Setup after PyInstaller to produce a Setup.exe (Windows only)",
    )
    args = parser.parse_args()

    print(f"[build] Building telegrab installer for {sys.platform} ({platform.machine()})")
    py = _ensure_venv()
    _ensure_pyinstaller(py)
    _ensure_frontend_build(force=args.rebuild_frontend)
    _run_pyinstaller(py, clean=args.clean)
    if args.installer:
        _run_inno_setup()
    _report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
