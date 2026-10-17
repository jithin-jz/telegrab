"""GitHub-based auto-updater.

Compares the running app version against the latest GitHub release using
a strict SemVer parse. Any non-SemVer tag (e.g. ``vbuild-30``) is treated
as "no update" so we never show a misleading prompt.

Trust model
-----------
* The release to install is resolved here, in Python, by
  :func:`cmd_check_for_updates` and remembered; the frontend can only say
  "install it" — it can't supply a URL or checksum.
* Asset URLs must point at this repository's release downloads on
  github.com (redirects may only go to GitHub's asset CDN).
* The expected SHA-256 comes from the release's ``SHA256SUMS`` asset, the
  asset ``digest`` GitHub computes, or the checksum list in the release
  notes — in that order. That protects against corruption and CDN
  tampering.
* If :data:`UPDATE_PUBLIC_KEY` is set, ``SHA256SUMS`` must also carry a
  valid Ed25519 signature (``SHA256SUMS.sig``) made with the matching
  private key in CI. That additionally protects against a compromised
  GitHub account publishing a malicious release.

Automatic install is Windows-only (Inno Setup installer). On macOS and
Linux the release page is opened so the user can download the new build.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import webview

from .. import __version__
from ..config import app_cache_dir

log = logging.getLogger(__name__)

REPO = "jithin-jz/telegrab"
_RELEASE_PATH_PREFIX = f"/{REPO}/releases/download/"

# Base64 Ed25519 public key used to verify SHA256SUMS.sig. Empty disables
# signature checks (checksums are still enforced). Generate a key pair with
# `python scripts/update_signing.py keygen`, put the private key in the
# UPDATE_SIGNING_KEY repository secret and the public key here.
UPDATE_PUBLIC_KEY = ""

_CHECKSUMS_ASSET = "SHA256SUMS"
_SIGNATURE_ASSET = "SHA256SUMS.sig"

# The release resolved by the last successful update check.
_pending_update: dict[str, Any] | None = None

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
    return bool(
        hostname == "githubusercontent.com"
        or hostname.endswith(".githubusercontent.com")
    )


def _is_release_asset_url(url: str) -> bool:
    """True only for HTTPS downloads of *this* repository's release assets."""
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == "github.com"
        and parsed.path.startswith(_RELEASE_PATH_PREFIX)
    )


def _is_allowed_redirect(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and _validate_url_domain(url)


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
        if not _is_allowed_redirect(newurl):
            raise urllib.error.URLError(
                f"Redirect to non-GitHub domain rejected: {urlparse(newurl).hostname}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: float):
    req = urllib.request.Request(url, headers={"User-Agent": "Telegrab-Updater"})
    opener = urllib.request.build_opener(_GitHubOnlyRedirectHandler)
    return opener.open(req, timeout=timeout)


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


# ───────────────────────────── checksums ─────────────────────────────

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def parse_checksum_list(text: str) -> dict[str, str]:
    """Parse ``sha256sum``-style lines into ``{basename: hex}``."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and _HEX64.match(parts[0]):
            name = parts[-1].lstrip("*").replace("\\", "/").rsplit("/", 1)[-1]
            out[name] = parts[0].lower()
    return out


def checksum_from_release(release: dict, asset: dict) -> str:
    """Best available SHA-256 for `asset` from the release metadata alone."""
    digest = str(asset.get("digest") or "")
    if digest.lower().startswith("sha256:") and _HEX64.match(digest[7:]):
        return digest[7:].lower()
    listed = parse_checksum_list(release.get("body") or "").get(asset.get("name", ""))
    if listed:
        return listed
    # Legacy convention: a single "SHA256: <hex>" line.
    m = re.search(r"sha-?256[:\s]+([0-9a-fA-F]{64})", release.get("body") or "", re.I)
    return m.group(1).lower() if m else ""


def _verify_signature(message: bytes, signature_b64: str) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(UPDATE_PUBLIC_KEY))
    try:
        key.verify(base64.b64decode(signature_b64.strip()), message)
    except (InvalidSignature, ValueError) as exc:
        raise RuntimeError("Update signature is invalid; refusing to install.") from exc


def _fetch_small_asset(asset: dict) -> bytes:
    url = asset.get("browser_download_url") or ""
    if not _is_release_asset_url(url):
        raise RuntimeError(f"Unexpected asset URL: {url}")
    with _open(url, timeout=15) as response:
        return response.read(1024 * 1024)


def _resolve_checksum(release: dict, asset: dict) -> str:
    """Expected SHA-256 for `asset`, verifying the signed checksum list if required."""
    assets = {a.get("name"): a for a in release.get("assets") or []}
    sums_asset = assets.get(_CHECKSUMS_ASSET)

    if UPDATE_PUBLIC_KEY:
        sig_asset = assets.get(_SIGNATURE_ASSET)
        if not sums_asset or not sig_asset:
            raise RuntimeError("Release is not signed; refusing to install.")
        sums = _fetch_small_asset(sums_asset)
        _verify_signature(sums, _fetch_small_asset(sig_asset).decode("ascii"))
        expected = parse_checksum_list(sums.decode("utf-8", "replace")).get(
            asset["name"]
        )
        if not expected:
            raise RuntimeError("Signed checksum list does not cover this installer.")
        return expected

    if sums_asset:
        with contextlib.suppress(Exception):
            sums = _fetch_small_asset(sums_asset).decode("utf-8", "replace")
            expected = parse_checksum_list(sums).get(asset["name"])
            if expected:
                return expected
    return checksum_from_release(release, asset)


# ───────────────────────────── public API ─────────────────────────────


def _pick_asset(assets: list[dict]) -> dict | None:
    """Installer for this OS (Windows only; others update manually)."""
    if sys.platform != "win32":
        return None
    fallback = None
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".exe") and "setup" in name:
            return asset
        if name.endswith(".exe") and fallback is None:
            fallback = asset
    return fallback


def cmd_check_for_updates() -> dict | None:
    """Check GitHub for the latest release.

    Always returns a dict shaped ``{"available": bool, ...}``. Returns
    ``None`` only on transport errors so the UI can distinguish a network
    failure from "you're up to date". ``manual`` is True when the update must
    be downloaded from the release page (macOS / Linux).
    """
    global _pending_update
    log.info("Checking for updates...")
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Telegrab-Updater",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
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
    asset = _pick_asset(data.get("assets") or [])
    release_page = data.get("html_url") or f"https://github.com/{REPO}/releases/latest"
    if not str(release_page).startswith(f"https://github.com/{REPO}/"):
        release_page = f"https://github.com/{REPO}/releases/latest"

    _pending_update = {
        "release": data,
        "asset": asset,
        "release_page": release_page,
    }
    return {
        "available": True,
        "version": data.get("tag_name"),
        "date": data.get("published_at"),
        "body": data.get("body") or "",
        "manual": asset is None,
    }


def _emit_progress(js: str) -> None:
    if webview.windows:
        with contextlib.suppress(Exception):
            webview.windows[0].evaluate_js(js)


def cmd_download_and_install_update() -> None:
    """Install the update found by the last :func:`cmd_check_for_updates`."""
    pending = _pending_update
    if pending is None:
        raise RuntimeError("No update available. Check for updates first.")

    asset = pending["asset"]
    if asset is None:
        # No automatic installer for this platform — send the user to the page.
        webbrowser.open(pending["release_page"], new=2)
        return

    expected = _resolve_checksum(pending["release"], asset)
    download_and_install(asset.get("browser_download_url") or "", expected)


def _updates_dir() -> Path:
    path = app_cache_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_and_install(download_url: str, expected_sha256: str = "") -> None:
    """Download the installer, verify its checksum, run it, and close the app."""
    if not download_url:
        raise ValueError("No download URL provided")

    # Requirement 11.2: Abort if no SHA-256 checksum provided
    if not expected_sha256:
        raise RuntimeError(
            "Update aborted: no SHA-256 checksum found for the installer. "
            "The update could not be verified for integrity."
        )

    if not _is_release_asset_url(download_url):
        raise ValueError(
            "Download URL rejected: not a release asset of the Telegrab repository"
        )

    log.info("Downloading update from %s ...", download_url)
    updates_dir = _updates_dir()

    # Check available disk space before downloading
    disk_usage = shutil.disk_usage(str(updates_dir))
    # Require at least 200MB free (typical installer is ~30MB, but leave headroom)
    min_free_bytes = 200 * 1024 * 1024
    if disk_usage.free < min_free_bytes:
        raise RuntimeError(
            f"Insufficient disk space. Need at least 200 MB free, "
            f"but only {disk_usage.free // (1024 * 1024)} MB available."
        )

    # Requirement 11.6: Sanitize filename
    filename = Path(download_url.split("?")[0].split("#")[0]).name
    filename = _sanitize_filename(filename)
    dest_path = updates_dir / f"Telegrab_Update_{filename}"

    sha256_hash = hashlib.sha256()
    downloaded_bytes = 0
    total_size = 0

    try:
        # Requirement 11.8: 300-second download timeout
        with _open(download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            # Validate the final URL after redirects
            final_url = response.geturl()
            if not _is_allowed_redirect(final_url):
                raise ValueError(
                    f"Download redirected to non-GitHub domain: "
                    f"{urlparse(final_url).hostname}"
                )

            total_size = int(response.headers.get("Content-Length", 0))
            _emit_progress(
                "window.dispatchEvent(new CustomEvent('updateProgress', "
                f"{{ detail: {{ event: 'Started', total: {total_size} }} }}));"
            )

            chunk_size = 64 * 1024
            unreported = 0
            last_report = time.monotonic()
            with dest_path.open("wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    downloaded_bytes += len(chunk)
                    unreported += len(chunk)
                    # evaluate_js is synchronous; throttle to ~5 updates/sec.
                    now = time.monotonic()
                    if now - last_report >= 0.2:
                        _emit_progress(
                            "window.dispatchEvent(new CustomEvent('updateProgress', "
                            f"{{ detail: {{ event: 'Progress', chunk: {unreported} }} }}));"
                        )
                        unreported = 0
                        last_report = now
            if unreported:
                _emit_progress(
                    "window.dispatchEvent(new CustomEvent('updateProgress', "
                    f"{{ detail: {{ event: 'Progress', chunk: {unreported} }} }}));"
                )

    except TimeoutError as exc:
        # Requirement 11.8: Delete partial file on timeout
        log.error(
            "Download timed out after %d seconds: %s", DOWNLOAD_TIMEOUT_SECONDS, exc
        )
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
    _launch_installer(dest_path)


def _launch_installer(installer: Path) -> None:
    try:
        pid = os.getpid()
        bat_path = installer.with_name("telegrab_updater.bat")
        # Wait for the current process to exit, run the installer silently
        # (it relaunches the app), then delete itself.
        bat_content = (
            "@echo off\n"
            ":loop\n"
            f'tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL\n'
            "if %ERRORLEVEL%==0 (\n"
            "    ping 127.0.0.1 -n 2 > nul\n"
            "    goto loop\n"
            ")\n"
            f'"{installer}" /SILENT /SUPPRESSMSGBOXES /NORESTART\n'
            'del "%~f0"\n'
        )
        try:
            bat_path.write_text(bat_content, encoding="utf-8")
            cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/c", str(bat_path)]
            subprocess.Popen(cmd, creationflags=0x00000008)  # DETACHED_PROCESS
        except Exception as exc:  # noqa: BLE001
            log.error(
                "Failed to write or run batch file: %s. Falling back to direct launch.",
                exc,
            )
            subprocess.Popen([str(installer), "/SILENT", "/SUPPRESSMSGBOXES"])

        # Closing the window ends webview.start(); app.main() then shuts down.
        if webview.windows:
            webview.windows[0].destroy()
    except Exception as exc:  # noqa: BLE001
        log.error("Failed to launch update: %s", exc)
        raise RuntimeError(f"Failed to launch update: {exc}") from exc


__all__ = [
    "cmd_check_for_updates",
    "cmd_download_and_install_update",
    "download_and_install",
    "checksum_from_release",
    "parse_checksum_list",
    "_sanitize_filename",
]
