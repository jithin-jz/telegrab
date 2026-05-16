"""REST API persisted settings (data + I/O + hashing only).

The bridge commands that mutate these settings and trigger server restarts
live in `telegrab.services.api_settings`. Splitting keeps the data model
free of any reference to the supervisor/runtime.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass

from .paths import api_settings_path

DEFAULT_API_PORT = 8550


@dataclass
class ApiSettingsFile:
    enabled: bool = False
    port: int = DEFAULT_API_PORT
    key_hash: str | None = None


def load_settings() -> ApiSettingsFile:
    """Read api_settings.json, returning defaults if missing/corrupt."""
    path = api_settings_path()
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return ApiSettingsFile(
            enabled=bool(data.get("enabled", False)),
            port=int(data.get("port", DEFAULT_API_PORT)),
            key_hash=data.get("key_hash"),
        )
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ApiSettingsFile()


def save_settings(settings: ApiSettingsFile) -> None:
    path = api_settings_path()
    with path.open("w", encoding="utf-8") as fh:
        json.dump(asdict(settings), fh, indent=2)


def hash_key(plaintext: str) -> str:
    """SHA-256 hex digest. Used both when generating new keys and when
    verifying inbound `X-API-Key` headers."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def verify_key(plaintext: str, stored_hash: str) -> bool:
    """Constant-time comparison."""
    return secrets.compare_digest(hash_key(plaintext), stored_hash)
