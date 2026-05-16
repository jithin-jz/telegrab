import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import webview

from .. import __version__

log = logging.getLogger(__name__)

REPO = "jithin-jz/telegrab"


def cmd_check_for_updates() -> dict | None:
    """Check GitHub for the latest release."""
    log.info("Checking for updates...")
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Telegrab-Updater"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())

        latest_tag = data.get("tag_name", "").lstrip("v")
        current_version = __version__.lstrip("v")

        # Simple string compare (assumes SemVer formatting)
        # For a robust approach, use packaging.version, but this is fine for now
        if latest_tag > current_version:
            log.info(f"Update found: {latest_tag}")

            # Find the appropriate asset
            download_url = None
            is_mac = sys.platform == "darwin"
            for asset in data.get("assets", []):
                name = asset["name"].lower()
                if (
                    is_mac
                    and (".dmg" in name or ".zip" in name)
                    or not is_mac
                    and ".exe" in name
                ):
                    download_url = asset["browser_download_url"]
                    break

            return {
                "available": True,
                "version": data.get("tag_name"),
                "date": data.get("published_at"),
                "body": data.get("body"),
                "download_url": download_url,
            }

        return {"available": False}
    except Exception as e:
        log.warning(f"Failed to check for updates: {e}")
        return None


def cmd_download_and_install_update(download_url: str) -> None:
    """Download the update to user's Downloads folder, run it, and close the app."""
    if not download_url:
        raise ValueError("No download URL provided")

    log.info(f"Downloading update from {download_url}...")

    # Save to Downloads folder
    downloads_dir = Path.home() / "Downloads"
    filename = download_url.split("/")[-1]

    # Prepend 'Telegrab_Update_' just to be clear
    dest_path = downloads_dir / f"Telegrab_Update_{filename}"

    # Download with progress
    try:
        req = urllib.request.Request(
            download_url, headers={"User-Agent": "Telegrab-Updater"}
        )
        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get("Content-Length", 0))

            # Fire Started event
            if webview.windows:
                js = f"window.dispatchEvent(new CustomEvent('updateProgress', {{ detail: {{ event: 'Started', total: {total_size} }} }}));"
                webview.windows[0].evaluate_js(js)

            downloaded = 0
            chunk_size = 8192

            with dest_path.open("wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if webview.windows:
                        js = f"window.dispatchEvent(new CustomEvent('updateProgress', {{ detail: {{ event: 'Progress', chunk: {len(chunk)} }} }}));"
                        webview.windows[0].evaluate_js(js)

    except Exception as e:
        log.error(f"Download failed: {e}")
        raise RuntimeError(f"Download failed: {e}") from e

    log.info(f"Update downloaded to {dest_path}. Launching...")

    # Launch the file
    try:
        if sys.platform == "win32":
            os.startfile(dest_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(dest_path)])
        else:
            subprocess.Popen(["xdg-open", str(dest_path)])

        # Exit the current app so the installer/new app can run
        if webview.windows:
            webview.windows[0].destroy()
        sys.exit(0)
    except Exception as e:
        log.error(f"Failed to launch update: {e}")
        raise RuntimeError(f"Failed to launch update: {e}") from e
