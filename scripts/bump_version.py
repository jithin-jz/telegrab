"""Sync version across all project files.

Usage:
    python scripts/bump_version.py 1.6.0

Updates:
    - backend/pyproject.toml  (version = "X.Y.Z")
    - backend/telegrab/__init__.py  (__version__ = "X.Y.Z")
    - frontend/package.json and package-lock.json  ("version": "X.Y.Z")
    - installer/telegrab_setup.iss and installer/telegrab.spec
    - backend/uv.lock (via `uv lock`, when uv is installed)

Commit the result, then push a matching `vX.Y.Z` tag to trigger the release.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "pyproject": ROOT / "backend" / "pyproject.toml",
    "init": ROOT / "backend" / "telegrab" / "__init__.py",
    "frontend_pkg": ROOT / "frontend" / "package.json",
    "frontend_lock": ROOT / "frontend" / "package-lock.json",
    "setup_iss": ROOT / "installer" / "telegrab_setup.iss",
    "spec": ROOT / "installer" / "telegrab.spec",
}


def update_pyproject(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{version}"', text, count=1, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")


def update_init(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', text, count=1)
    path.write_text(text, encoding="utf-8")


def update_package_json(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_package_lock(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    data.get("packages", {}).get("", {})["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_setup_iss(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^#define\s+MyAppVersion\s+"[^"]+"', f'#define MyAppVersion "{version}"', text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")


def update_spec(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"CFBundleShortVersionString":\s*"[^"]+"', f'"CFBundleShortVersionString": "{version}"', text)
    text = re.sub(r'"CFBundleVersion":\s*"[^"]+"', f'"CFBundleVersion": "{version}"', text)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        # Read current version from pyproject.toml
        text = FILES["pyproject"].read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        current = m.group(1) if m else "unknown"
        print(f"Current version: {current}")
        print(f"Usage: python {sys.argv[0]} <new_version>")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")
    if not re.match(r"^\d+\.\d+\.\d+", version):
        print(f"Error: '{version}' is not a valid semver version")
        sys.exit(1)

    update_pyproject(FILES["pyproject"], version)
    update_init(FILES["init"], version)
    update_package_json(FILES["frontend_pkg"], version)
    update_package_lock(FILES["frontend_lock"], version)
    update_setup_iss(FILES["setup_iss"], version)
    update_spec(FILES["spec"], version)

    print(f"OK Version synced to {version} across:")
    for name, path in FILES.items():
        print(f"  - {path.relative_to(ROOT)}")

    uv = shutil.which("uv")
    if uv:
        subprocess.run([uv, "lock"], cwd=str(ROOT / "backend"), check=True)
        print("  - backend/uv.lock")
    else:
        print("uv not found: run `uv lock` in backend/ before committing.")


if __name__ == "__main__":
    main()
