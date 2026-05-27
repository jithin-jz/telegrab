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
from urllib.parse import urlparse

import webview

from .. import __version__

log = logging.getLogger(__name__)

REPO = "jithin-jz/telegrab"

# ───────────────────────────── URL domain validation ─────────────────────────


def _validate_url_domain(url: str) -> bool:
    """Validate that a URL's hostname is github.com or a subdomain of github.com.

    Returns True if the hostname is exactly ``github.com`` or ends with
    ``.github.com``. Also accepts ``githubusercontent.com`` and its subdomains,
    as GitHub uses this CDN domain for release asset downloads.
    Returns False for all other domains, missing hostnames, or unparseable URLs.
    """
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False

    # Accept github.com and *.github.com
    if hostname == "github.com" or hostname.endswith(".github.com"):
        return True

    # Accept githubusercontent.com and *.githubusercontent.com (GitHub CDN)
    if hostname == "githubusercontent.com" or hostname.endswith(".githubusercontent.com"):
        return True

    return False


class _GitHubOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom redirect handler that rejects redirects to non-GitHub domains."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp,  # noqa: ANN001
        code: int,
        msg: str,
        headers,  # noqa: ANN001
        newurl: str,
    ) -> urllib.request.Request | None:
        if not _validate_url_domain(newurl):
            raise urllib.error.URLError(
                f"Redirect to non-GitHub domain rejected: {urlparse(newurl).hostname}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ───────────────────────────── filename sanitization ─────────────────────────

DOWNLOAD_TIMEOUT_SECONDS = 300


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing path traversal and separator characters.

    Removes all occurrences of ``..``, ``/``, and ``\\`` from the filename.
    If the result is empty after sanitization, returns ``"telegrab_update"``.
    """
    sanitized = filename.replace("..", "").replace("/", "").replace("\\", "")
    if not sanitized:
        return "telegrab_update"
    return sanitized


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
    import shutil

    if not download_url:
        raise ValueError("No download URL provided")

    # Requirement 11.2: Abort if no SHA-256 checksum provided
    if not expected_sha256:
        raise RuntimeError(
            "Update aborted: no SHA-256 checksum found in release body. "
            "The update could not be verified for integrity."
        )

    # Validate URL domain before downloading
    if not _validate_url_domain(download_url):
        raise ValueError(
            "Download URL rejected: hostname is not github.com or *.github.com"
        )

    log.info("Downloading update from %s ...", download_url)

    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    # Check available disk space before downloading
    disk_usage = shutil.disk_usage(str(downloads_dir))
    # Require at least 200MB free (typical installer is ~30MB, but leave headroom)
    min_free_bytes = 200 * 1024 * 1024
    if disk_usage.free < min_free_bytes:
        raise RuntimeError(
            f"Insufficient disk space. Need at least 200 MB free, "
            f"but only {disk_usage.free // (1024 * 1024)} MB available in Downloads."
        )

    # Requirement 11.6: Sanitize filename
    filename = Path(download_url.split("?")[0].split("#")[0]).name
    filename = _sanitize_filename(filename)
    dest_path = downloads_dir / f"Telegrab_Update_{filename}"

    sha256_hash = hashlib.sha256()
    downloaded_bytes = 0

    try:
        req = urllib.request.Request(
            download_url, headers={"User-Agent": "Telegrab-Updater"}
        )
        # Use custom opener that rejects redirects to non-GitHub domains
        opener = urllib.request.build_opener(_GitHubOnlyRedirectHandler)
        # Requirement 11.8: 300-second download timeout
        with opener.open(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            # Validate the final URL after redirects
            final_url = response.geturl()
            if not _validate_url_domain(final_url):
                raise ValueError(
                    f"Download redirected to non-GitHub domain: "
                    f"{urlparse(final_url).hostname}"
                )

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
                    downloaded_bytes += len(chunk)
                    if webview.windows:
                        js = (
                            "window.dispatchEvent(new CustomEvent('updateProgress', "
                            f"{{ detail: {{ event: 'Progress', chunk: {len(chunk)} }} }}));"
                        )
                        webview.windows[0].evaluate_js(js)

    except TimeoutError as exc:
        # Requirement 11.8: Delete partial file on timeout
        log.error("Download timed out after %d seconds: %s", DOWNLOAD_TIMEOUT_SECONDS, exc)
        with contextlib.suppress(OSError):
            dest_path.unlink()
        raise RuntimeError(
            f"Update download timed out after {DOWNLOAD_TIMEOUT_SECONDS} seconds. "
            "Please check your network connection and try again."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        log.error("Download failed: %s", exc)
        # Delete partial file on any download failure
        with contextlib.suppress(OSError):
            dest_path.unlink()
        raise RuntimeError(f"Download failed: {exc}") from exc

    # Requirement 11.5: Verify file size matches Content-Length
    if total_size > 0 and downloaded_bytes != total_size:
        log.error(
            "File size mismatch! Expected %d bytes (Content-Length), got %d bytes",
            total_size,
            downloaded_bytes,
        )
        with contextlib.suppress(OSError):
            dest_path.unlink()
        raise RuntimeError(
            f"Update verification failed: file size mismatch. "
            f"Expected {total_size} bytes, downloaded {downloaded_bytes} bytes."
        )

    # Requirement 11.1, 11.3: Verify SHA-256 checksum (mandatory)
    actual_sha256 = sha256_hash.hexdigest()
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
            pid = os.getpid()
            bat_path = downloads_dir / "telegrab_updater.bat"
            # Wait for current process to exit, run installer silently,
            # then relaunch the app from its install location.
            bat_content = (
                f'@echo off\n'
                f':loop\n'
                f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL\n'
                f'if %ERRORLEVEL%==0 (\n'
                f'    ping 127.0.0.1 -n 2 > nul\n'
                f'    goto loop\n'
                f')\n'
                f'"{dest_path}" /SILENT /SUPPRESSMSGBOXES\n'
                f'del "%~f0"\n'
            )
            try:
                bat_path.write_text(bat_content, encoding="utf-8")
                cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", str(bat_path)]
                subprocess.Popen(cmd, creationflags=0x00000008)
            except Exception as exc:
                log.error("Failed to write or run batch file: %s. Falling back to direct launch.", exc)
                subprocess.Popen([str(dest_path), "/SILENT", "/SUPPRESSMSGBOXES"])
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


__all__ = ["cmd_check_for_updates", "cmd_download_and_install_update", "_sanitize_filename"]
