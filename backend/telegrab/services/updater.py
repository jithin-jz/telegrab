"""GitHub-based auto-updater.

Compares the running app version against the latest GitHub release using
a strict SemVer parse. Any non-SemVer tag (e.g. ``vbuild-30``) is treated
as "no update" so we never show a misleading prompt.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import webview

from .. import __version__

log = logging.getLogger(__name__)

REPO = "jithin-jz/telegrab"

# ───────────────────────────── version parsing ─────────────────────────────

_SEMVER_RE = re.compile(
    r"""
    ^\s*v?                     # optional leading 'v'
    (?P<major>0|[1-9]\d*)
    \.(?P<minor>0|[1-9]\d*)
    (?:\.(?P<patch>0|[1-9]\d*))?
    (?:-(?P<pre>[0-9A-Za-z.-]+))?      # pre-release identifiers
    (?:\+(?P<build>[0-9A-Za-z.-]+))?   # build metadata (ignored for compare)
    \s*$
    """,
    re.VERBOSE,
)


def _parse(tag: str | None) -> tuple | None:
    """Return a comparable tuple for a SemVer-ish tag, or ``None``.

    Comparable shape: ``(major, minor, patch, is_release, pre_parts)``
      * ``is_release`` is 1 for normal releases, 0 for pre-releases. This
        ensures ``1.0.0-alpha < 1.0.0`` per SemVer.
      * ``pre_parts`` is a tuple of (int, str) pairs so dotted pre-release
        identifiers compare numerically when numeric, lexicographically
        otherwise (also per SemVer).
    """
    if not tag:
        return None
    m = _SEMVER_RE.match(tag)
    if not m:
        return None

    major = int(m.group("major"))
    minor = int(m.group("minor"))
    patch = int(m.group("patch") or 0)
    pre = m.group("pre")

    if pre is None:
        return (major, minor, patch, 1, ())

    parts: list[tuple[int, object]] = []
    for ident in pre.split("."):
        if ident.isdigit():
            # numeric identifier — group 0 sorts before group 1 (strings)
            parts.append((0, int(ident)))
        else:
            parts.append((1, ident))
    return (major, minor, patch, 0, tuple(parts))


# ───────────────────────────── public API ─────────────────────────────


def cmd_check_for_updates() -> dict | None:
    """Check GitHub for the latest release.

    Always returns a dict shaped ``{"available": bool, ...}``. Returns
    ``None`` only on transport errors so the UI can distinguish a network
    failure from "you're up to date".
    """
    log.info("Checking for updates...")
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Telegrab-Updater"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        # 404 = no releases yet → no update, but not a hard error
        if exc.code == 404:
            log.info("No releases published yet.")
            return {"available": False}
        log.warning("Update check HTTP error: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Update check failed: %s", exc)
        return None

    # Defensive: skip drafts/prereleases even though releases/latest already
    # excludes them.
    if data.get("draft") or data.get("prerelease"):
        return {"available": False}

    latest_raw = (data.get("tag_name") or "").strip()
    latest = _parse(latest_raw)
    current = _parse(__version__)

    if latest is None:
        log.info(
            "Latest release tag %r is not SemVer; treating as no update available.",
            latest_raw,
        )
        return {"available": False}
    if current is None:
        log.warning(
            "Current app version %r is not SemVer; cannot compare.", __version__
        )
        return {"available": False}

    if latest <= current:
        log.info("Up to date (current=%s, latest=%s).", __version__, latest_raw)
        return {"available": False}

    log.info("Update found: %s -> %s", __version__, latest_raw)

    # Pick the asset for this OS (prefer installer over portable).
    download_url: str | None = None
    is_mac = sys.platform == "darwin"
    is_win = sys.platform == "win32"
    for asset in data.get("assets") or []:
        name = (asset.get("name") or "").lower()
        if is_mac and (name.endswith(".dmg") or name.endswith(".zip")):
            download_url = asset.get("browser_download_url")
            break
        if is_win and "setup" in name and name.endswith(".exe"):
            download_url = asset.get("browser_download_url")
            break
        if is_win and name.endswith(".exe") and not download_url:
            download_url = asset.get("browser_download_url")
        if not is_mac and not is_win and (
            name.endswith(".appimage") or name.endswith(".deb") or name.endswith(".rpm")
        ):
            download_url = asset.get("browser_download_url")
            break

    if not download_url:
        log.info("No matching asset for this platform; not offering update.")
        return {"available": False}

    # Try to extract SHA-256 from release body (convention: "SHA256: <hex>" or "sha256: <hex>")
    body = data.get("body") or ""
    sha256_match = re.search(
        r"(?:sha256|SHA256)[:\s]+([0-9a-fA-F]{64})", body
    )
    expected_sha256 = sha256_match.group(1) if sha256_match else ""

    return {
        "available": True,
        "version": data.get("tag_name"),
        "date": data.get("published_at"),
        "body": body,
        "download_url": download_url,
        "sha256": expected_sha256,
    }


def cmd_download_and_install_update(download_url: str, expected_sha256: str = "") -> None:
    """Download the update to user's Downloads folder, verify checksum, run it, and close the app."""
    import hashlib

    if not download_url:
        raise ValueError("No download URL provided")

    log.info("Downloading update from %s ...", download_url)

    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(download_url.split("?")[0].split("#")[0]).name
    # Sanitize filename to prevent path traversal
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    if not filename:
        filename = "telegrab_update"
    dest_path = downloads_dir / f"Telegrab_Update_{filename}"

    sha256_hash = hashlib.sha256()

    try:
        req = urllib.request.Request(
            download_url, headers={"User-Agent": "Telegrab-Updater"}
        )
        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get("Content-Length", 0))

            if webview.windows:
                js = (
                    "window.dispatchEvent(new CustomEvent('updateProgress', "
                    f"{{ detail: {{ event: 'Started', total: {total_size} }} }}));"
                )
                webview.windows[0].evaluate_js(js)

            chunk_size = 8192
            with dest_path.open("wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    if webview.windows:
                        js = (
                            "window.dispatchEvent(new CustomEvent('updateProgress', "
                            f"{{ detail: {{ event: 'Progress', chunk: {len(chunk)} }} }}));"
                        )
                        webview.windows[0].evaluate_js(js)

    except Exception as exc:  # noqa: BLE001
        log.error("Download failed: %s", exc)
        raise RuntimeError(f"Download failed: {exc}") from exc

    # Verify SHA-256 checksum if provided
    actual_sha256 = sha256_hash.hexdigest()
    if expected_sha256:
        if actual_sha256.lower() != expected_sha256.lower():
            log.error(
                "Checksum mismatch! Expected %s, got %s", expected_sha256, actual_sha256
            )
            with contextlib.suppress(OSError):
                dest_path.unlink()
            raise RuntimeError(
                "Update verification failed: SHA-256 checksum mismatch. "
                "The download may be corrupted or tampered with."
            )
        log.info("SHA-256 checksum verified: %s", actual_sha256)

    log.info("Update downloaded to %s. Launching...", dest_path)

    try:
        if sys.platform == "win32":
            os.startfile(dest_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(dest_path)])
        else:
            subprocess.Popen(["xdg-open", str(dest_path)])

        if webview.windows:
            webview.windows[0].destroy()
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to launch update: %s", exc)
        raise RuntimeError(f"Failed to launch update: {exc}") from exc


__all__ = ["cmd_check_for_updates", "cmd_download_and_install_update"]
