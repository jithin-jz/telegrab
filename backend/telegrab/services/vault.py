"""Encrypted Vaults — AES-256-GCM client-side encryption.

Files are encrypted before upload and decrypted after download. The vault
password derives a key via PBKDF2-SHA256; Telegram never sees plaintext.

Vault metadata (salt + an encrypted password check) is stored in two places:

* the vault folder's channel description on Telegram, as a
  ``[telegrab-vault:1:<salt>:<check>]`` tag — so a vault survives reinstalls
  and works on every device signed in to the account; and
* a local SQLite cache (``vaults.db``) so lookups don't need the network.

File format (current, ``TGVLTCH2``)::

    magic(8) | base_nonce(12) | chunk_size(4, BE) | num_chunks(8, BE)
    then per chunk: ct_len(4, BE) | AES-GCM(chunk) incl. 16-byte tag

Each chunk uses nonce ``base_nonce XOR index`` and authenticates the header
plus ``(index, is_last)`` as associated data, so chunks can't be reordered,
dropped or truncated without detection. The older ``TGVAULT1`` (single-shot)
and ``TGVLTCHK`` (chunked, unauthenticated header) formats remain readable.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import contextlib
import ctypes
import hashlib
import logging
import os
import re
import secrets
import sqlite3
import struct
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from ..api.errors import BridgeError, ErrorCode
from ..config import app_cache_dir, app_data_dir

log = logging.getLogger(__name__)

_VAULT_DB: sqlite3.Connection | None = None
_PBKDF2_ITERATIONS = 600_000
_HEADER_MAGIC = b"TGVAULT1"  # legacy single-shot format
_CHUNKED_MAGIC = b"TGVLTCHK"  # legacy chunked format (header not authenticated)
_CHUNKED_V2_MAGIC = b"TGVLTCH2"  # current format
_CHUNK_SIZE = 16 * 1024 * 1024  # legacy chunk size (kept for reference)
_V2_CHUNK_SIZE = 8 * 1024 * 1024
_KEY_CHECK_PLAINTEXT = b"TELEGRAB_VAULT_OK"

# Telegram channel descriptions are limited to 255 characters.
_ABOUT_MAX = 255
_VAULT_TAG_RE = re.compile(r"\s*\[telegrab-vault:1:([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)\]")

# Flag indicating vault DB integrity status. Set to False if integrity check fails.
_vault_db_healthy: bool = True

_vault_db_lock = threading.Lock()

# Folders whose Telegram description was already checked this session.
_remote_checked: set[int] = set()


def _check_db_integrity() -> bool:
    """Run PRAGMA integrity_check on the vault database.

    Returns True if the database passes integrity check, False otherwise.
    Sets the global _vault_db_healthy flag accordingly.
    """
    global _vault_db_healthy
    try:
        if _VAULT_DB is None:
            _vault_db_healthy = False
            return False
        result = _VAULT_DB.execute("PRAGMA integrity_check").fetchone()
        if result and result[0] == "ok":
            _vault_db_healthy = True
            log.debug("Vault database integrity check passed")
            return True
        _vault_db_healthy = False
        detail = str(result[0]) if result else "unknown error"
        log.error("Vault database integrity check failed: %s", detail)
        return False
    except Exception as exc:
        _vault_db_healthy = False
        log.error("Vault database integrity check error: %s", exc)
        return False


def _require_healthy_db() -> None:
    """Raise an error if the vault database failed integrity check."""
    if not _vault_db_healthy:
        raise BridgeError(
            code=ErrorCode.VAULT_DB_CORRUPT,
            message="Vault database is corrupted. Please re-initialize the vault.",
            detail="SQLite integrity_check failed on startup. Vault operations are disabled until re-initialization.",
        )


def _get_vault_db() -> sqlite3.Connection:
    global _VAULT_DB, _vault_db_healthy
    with _vault_db_lock:
        if _VAULT_DB is None:
            path = app_data_dir() / "vaults.db"
            try:
                _VAULT_DB = sqlite3.connect(str(path), check_same_thread=False)
            except Exception as exc:
                _vault_db_healthy = False
                log.error("Failed to open vault database: %s", exc)
                raise BridgeError(
                    code=ErrorCode.VAULT_DB_CORRUPT,
                    message="Vault database cannot be opened. Please re-initialize the vault.",
                    detail=f"Failed to open vault database at {path}: {exc}",
                ) from exc
            _VAULT_DB.row_factory = sqlite3.Row
            try:
                _VAULT_DB.executescript("""
                    CREATE TABLE IF NOT EXISTS vaults (
                        folder_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        salt BLOB NOT NULL,
                        key_check BLOB NOT NULL,
                        created_at REAL NOT NULL
                    );
                """)
                _VAULT_DB.commit()
            except Exception as exc:
                _vault_db_healthy = False
                _VAULT_DB = None
                log.error("Vault database schema creation failed: %s", exc)
                raise BridgeError(
                    code=ErrorCode.VAULT_DB_CORRUPT,
                    message="Vault database is corrupted. Please re-initialize the vault.",
                    detail=f"Failed to initialize vault database schema at {path}: {exc}",
                ) from exc
            # Run integrity check on first initialization
            _check_db_integrity()
    return _VAULT_DB


def _derive_key(password: str, salt: bytes) -> bytearray:
    """Derive a 256-bit key from password + salt using PBKDF2-SHA256.

    Returns a mutable bytearray so the key can be zeroized in place — an
    immutable bytes copy would linger in memory un-wiped.
    """
    return bytearray(
        hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
        )
    )


def _encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Encrypt data with AES-256-GCM. Returns: magic + nonce(12) + tag(16) + ciphertext."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    aesgcm = AESGCM(bytes(key))
    ct = aesgcm.encrypt(nonce, data, None)
    # ct includes the 16-byte tag appended by cryptography lib
    return _HEADER_MAGIC + nonce + ct


def _decrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Decrypt data encrypted by _encrypt_bytes."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not data.startswith(_HEADER_MAGIC):
        raise ValueError("Not a vault-encrypted file")
    payload = data[len(_HEADER_MAGIC) :]
    nonce = payload[:12]
    ct = payload[12:]
    aesgcm = AESGCM(bytes(key))
    return aesgcm.decrypt(nonce, ct, None)


# ─────────────────────── Telegram-side metadata ───────────────────────


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def format_vault_tag(salt: bytes, key_check: bytes) -> str:
    return f"[telegrab-vault:1:{_b64(salt)}:{_b64(key_check)}]"


def parse_vault_tag(about: str | None) -> tuple[bytes, bytes] | None:
    """Return (salt, key_check) from a channel description, if present."""
    m = _VAULT_TAG_RE.search(about or "")
    if not m:
        return None
    try:
        return _unb64(m.group(1)), _unb64(m.group(2))
    except (ValueError, TypeError):
        return None


def strip_vault_tag(about: str | None) -> str:
    return _VAULT_TAG_RE.sub("", about or "").strip()


async def _get_channel(client: Any, folder_id: int) -> Any:
    from telethon.tl import types

    from .. import telegram as tg

    entity = await tg.resolve_peer(client, folder_id)
    if not isinstance(entity, types.Channel):
        raise RuntimeError("Only folders can be turned into vaults.")
    return entity


async def _read_about(client: Any, folder_id: int) -> tuple[str, Any]:
    from telethon.tl import functions

    channel = await _get_channel(client, folder_id)
    full = await client(functions.channels.GetFullChannelRequest(channel=channel))
    about = getattr(getattr(full, "full_chat", None), "about", "") or ""
    return about, channel


async def _write_about(client: Any, channel: Any, about: str) -> None:
    from telethon.tl import functions

    await client(functions.messages.EditChatAboutRequest(peer=channel, about=about))


def _insert_vault_row(folder_id: int, name: str, salt: bytes, key_check: bytes) -> None:
    db = _get_vault_db()
    with _vault_db_lock:
        db.execute(
            "INSERT OR REPLACE INTO vaults (folder_id, name, salt, key_check, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (folder_id, name, salt, key_check, time.time()),
        )
        db.commit()


def _channel_display_name(channel: Any) -> str:
    title = getattr(channel, "title", "") or "Vault"
    return title.replace("[TD]", "").strip() or title


async def ensure_vault_known(folder_id: int | None) -> bool:
    """Return True if `folder_id` is a vault.

    Checks the local cache first, then (once per session) the folder's
    Telegram description, importing the vault metadata if found. This is
    what makes vaults work after a reinstall or on a second device.
    """
    if folder_id is None:
        return False
    _require_healthy_db()
    if is_vault(folder_id):
        return True
    if folder_id in _remote_checked:
        return False

    from .. import telegram as tg

    client = tg.get_state().client
    if client is None:
        return False
    try:
        about, channel = await _read_about(client, folder_id)
    except Exception as exc:  # noqa: BLE001
        # Not a channel, or offline — don't cache the miss so we retry later.
        log.debug("Vault metadata lookup failed for %s: %s", folder_id, exc)
        return False

    _remote_checked.add(folder_id)
    parsed = parse_vault_tag(about)
    if parsed is None:
        return False
    salt, key_check = parsed
    _insert_vault_row(folder_id, _channel_display_name(channel), salt, key_check)
    log.info("Imported vault metadata from Telegram (folder_id=%s)", folder_id)
    return True


# ─────────────────────── Session key store ───────────────────────
# Unlocked vault keys are held in memory only for the session.
_session_keys: dict[int, bytearray] = {}

# ─────────────────────── Key zeroization ───────────────────────


def _zeroize_key(key: bytearray | bytes) -> None:
    """Overwrite key bytes with zeros in memory using ctypes.memset."""
    if not key:
        return
    if isinstance(key, bytearray):
        buf = (ctypes.c_char * len(key)).from_buffer(key)
        ctypes.memset(buf, 0, len(key))


def _zeroize_all_keys() -> None:
    """Zeroize all held vault session keys. Called on shutdown and logout."""
    for folder_id in list(_session_keys.keys()):
        key = _session_keys.pop(folder_id, None)
        if key is not None:
            _zeroize_key(key)
    with _timer_lock:
        for timer in _inactivity_timers.values():
            timer.cancel()
        _inactivity_timers.clear()
    log.debug("All vault session keys zeroized")


# Register the atexit handler to zeroize keys on application exit
atexit.register(_zeroize_all_keys)

# ─────────────────────── Inactivity auto-lock ───────────────────────

_AUTO_LOCK_MINUTES: int = 30  # Default: 30 minutes
_AUTO_LOCK_MIN: int = 1
_AUTO_LOCK_MAX: int = 1440
_inactivity_timers: dict[int, threading.Timer] = {}
_timer_lock = threading.Lock()


def set_auto_lock_timeout(minutes: int) -> None:
    """Configure the vault auto-lock timeout in minutes (1-1440)."""
    global _AUTO_LOCK_MINUTES
    if minutes < _AUTO_LOCK_MIN or minutes > _AUTO_LOCK_MAX:
        raise ValueError(
            f"Auto-lock timeout must be between {_AUTO_LOCK_MIN} and {_AUTO_LOCK_MAX} minutes"
        )
    _AUTO_LOCK_MINUTES = minutes
    log.info("Vault auto-lock timeout set to %d minutes", minutes)


def get_auto_lock_timeout() -> int:
    """Return the current auto-lock timeout in minutes."""
    return _AUTO_LOCK_MINUTES


def _on_inactivity_timeout(folder_id: int) -> None:
    """Called when the inactivity timer expires. Zeroizes key and reports vault as locked."""
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)
        log.info("Vault auto-locked due to inactivity (folder_id=%s)", folder_id)
        from ..infra.events import bus

        bus.emit("vault-locked", {"folderId": folder_id})

    with _timer_lock:
        _inactivity_timers.pop(folder_id, None)


def _reset_inactivity_timer(folder_id: int) -> None:
    """Reset (or start) the inactivity auto-lock timer for a vault."""
    with _timer_lock:
        # Cancel existing timer if any
        existing = _inactivity_timers.pop(folder_id, None)
        if existing is not None:
            existing.cancel()

        # Start a new timer
        timeout_seconds = _AUTO_LOCK_MINUTES * 60
        timer = threading.Timer(
            timeout_seconds, _on_inactivity_timeout, args=(folder_id,)
        )
        timer.daemon = True
        timer.start()
        _inactivity_timers[folder_id] = timer


def _cancel_inactivity_timer(folder_id: int) -> None:
    """Cancel the inactivity timer for a vault (e.g., on explicit lock)."""
    with _timer_lock:
        timer = _inactivity_timers.pop(folder_id, None)
        if timer is not None:
            timer.cancel()


# ─────────────────────── Public API ───────────────────────


async def cmd_create_vault(name: str, password: str, folder_id: int) -> dict[str, Any]:
    """Create a new encrypted vault linked to a Telegram folder."""
    from . import require_client

    _require_healthy_db()
    if len(password or "") < 8:
        raise RuntimeError("Vault password must be at least 8 characters.")
    client = require_client()
    if await ensure_vault_known(folder_id):
        raise RuntimeError("This folder is already a vault")

    about, channel = await _read_about(client, folder_id)

    salt = secrets.token_bytes(32)
    # PBKDF2 with 600k iterations takes ~0.5 s — keep it off the event loop.
    key = await asyncio.to_thread(_derive_key, password, salt)
    # Store a known plaintext encrypted as key_check for password verification
    key_check = _encrypt_bytes(_KEY_CHECK_PLAINTEXT, key)

    tag = format_vault_tag(salt, key_check)
    base = strip_vault_tag(about)
    new_about = f"{base}\n{tag}" if base else tag
    if len(new_about) > _ABOUT_MAX:
        raise RuntimeError(
            "This folder's description is too long to store vault settings. "
            "Shorten it in Telegram and try again."
        )
    # Persist on Telegram first: without it the vault would be lost on reinstall.
    await _write_about(client, channel, new_about)
    _insert_vault_row(folder_id, name, salt, key_check)
    _remote_checked.add(folder_id)

    # Auto-unlock for this session
    _session_keys[folder_id] = key
    _reset_inactivity_timer(folder_id)
    log.info("Vault created: %s (folder_id=%s)", name, folder_id)
    return {"folder_id": folder_id, "name": name, "locked": False}


async def cmd_unlock_vault(folder_id: int, password: str) -> bool:
    """Unlock a vault for this session by verifying the password."""
    _require_healthy_db()
    if not await ensure_vault_known(folder_id):
        raise RuntimeError("Not a vault")
    db = _get_vault_db()
    with _vault_db_lock:
        row = db.execute(
            "SELECT salt, key_check FROM vaults WHERE folder_id = ?", (folder_id,)
        ).fetchone()
    if not row:
        raise RuntimeError("Not a vault")

    key = await asyncio.to_thread(_derive_key, password, bytes(row["salt"]))
    try:
        _decrypt_bytes(bytes(row["key_check"]), key)
    except Exception:
        _zeroize_key(key)
        raise BridgeError(
            code=ErrorCode.VAULT_WRONG_PASSWORD,
            message="Incorrect password",
            detail=f"Vault key check failed for folder {folder_id}",
        ) from None

    _session_keys[folder_id] = key
    _reset_inactivity_timer(folder_id)
    await _backfill_remote_tag(folder_id, bytes(row["salt"]), bytes(row["key_check"]))
    return True


async def _backfill_remote_tag(folder_id: int, salt: bytes, key_check: bytes) -> None:
    """Copy vault metadata to Telegram for vaults created before it was stored there.

    Best-effort: without it the vault only works on this machine, but a
    failure here must not block unlocking.
    """
    from .. import telegram as tg

    client = tg.get_state().client
    if client is None:
        return
    try:
        about, channel = await _read_about(client, folder_id)
        if parse_vault_tag(about) is not None:
            return
        base = strip_vault_tag(about)
        tag = format_vault_tag(salt, key_check)
        new_about = f"{base}\n{tag}" if base else tag
        if len(new_about) > _ABOUT_MAX:
            log.warning(
                "Folder %s description too long to back up vault metadata", folder_id
            )
            return
        await _write_about(client, channel, new_about)
        log.info("Backed up vault metadata to Telegram (folder_id=%s)", folder_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not back up vault metadata for %s: %s", folder_id, exc)


async def cmd_lock_vault(folder_id: int) -> bool:
    """Lock a vault (zeroize and clear session key)."""
    _cancel_inactivity_timer(folder_id)
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)
    return True


async def cmd_list_vaults() -> list[dict[str, Any]]:
    """List all vaults with their lock status."""
    _require_healthy_db()
    db = _get_vault_db()
    with _vault_db_lock:
        rows = db.execute("SELECT folder_id, name, created_at FROM vaults").fetchall()
    return [
        {
            "folder_id": r["folder_id"],
            "name": r["name"],
            "created_at": r["created_at"],
            "locked": r["folder_id"] not in _session_keys,
        }
        for r in rows
    ]


async def cmd_get_vault_status(folder_id: int | None) -> dict[str, bool]:
    """Return whether a folder is a vault and whether it is currently locked."""
    vault = await ensure_vault_known(folder_id)
    return {"is_vault": vault, "locked": vault and not is_unlocked(folder_id)}


async def cmd_delete_vault(folder_id: int) -> bool:
    """Stop treating a folder as a vault.

    Files already uploaded stay encrypted on Telegram and can never be
    decrypted again afterwards, so the vault must be unlocked (proving the
    caller knows the password) and the UI must warn before calling this.
    """
    from . import require_client

    _require_healthy_db()
    if not is_unlocked(folder_id):
        raise RuntimeError("Unlock the vault before removing it.")
    client = require_client()
    about, channel = await _read_about(client, folder_id)
    if parse_vault_tag(about) is not None:
        await _write_about(client, channel, strip_vault_tag(about))
    forget_vault(folder_id)
    return True


def forget_vault(folder_id: int) -> None:
    """Drop local vault state for a folder (metadata row, key, timer)."""
    db = _get_vault_db()
    with _vault_db_lock:
        db.execute("DELETE FROM vaults WHERE folder_id = ?", (folder_id,))
        db.commit()
    _remote_checked.discard(folder_id)
    _cancel_inactivity_timer(folder_id)
    key = _session_keys.pop(folder_id, None)
    if key is not None:
        _zeroize_key(key)


def reset_local_state() -> None:
    """Forget all vaults and keys (called on logout).

    Safe because vault metadata lives on Telegram and is re-imported on demand.
    """
    _zeroize_all_keys()
    _remote_checked.clear()
    db = _get_vault_db()
    with _vault_db_lock:
        db.execute("DELETE FROM vaults")
        db.commit()


def is_vault(folder_id: int | None) -> bool:
    """Check the local cache for whether a folder is a vault."""
    if folder_id is None:
        return False
    db = _get_vault_db()
    with _vault_db_lock:
        return (
            db.execute(
                "SELECT 1 FROM vaults WHERE folder_id = ?", (folder_id,)
            ).fetchone()
            is not None
        )


def is_unlocked(folder_id: int | None) -> bool:
    """Check if a vault is unlocked for this session."""
    if folder_id is None:
        return False
    return folder_id in _session_keys


# ─────────────────────── File encryption ───────────────────────


def vault_temp_dir() -> Path:
    """Private scratch directory for ciphertext staged for upload."""
    p = app_cache_dir() / "vault-tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def purge_temp_files() -> None:
    """Delete leftover staged files (e.g. after a crash mid-upload)."""
    with contextlib.suppress(OSError):
        for entry in vault_temp_dir().iterdir():
            with contextlib.suppress(OSError):
                entry.unlink()


def _session_key_copy(folder_id: int) -> bytes:
    key = _session_keys.get(folder_id)
    if not key:
        raise RuntimeError("Vault is locked")
    # Immutable copy — the auto-lock timer may zeroize the original mid-use.
    return bytes(key)


def _chunk_nonce(base_nonce: bytes, index: int) -> bytes:
    return (int.from_bytes(base_nonce, "big") ^ index).to_bytes(12, "big")


def encrypt_file(path: str, folder_id: int, out_dir: str | Path | None = None) -> str:
    """Encrypt a file for vault upload. Returns the path of the ciphertext.

    Streams the file in chunks, so memory use is bounded regardless of size.
    Blocking — call it via ``asyncio.to_thread``.
    """
    _require_healthy_db()
    key = _session_key_copy(folder_id)
    _reset_inactivity_timer(folder_id)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    file_size = Path(path).stat().st_size
    num_chunks = max(1, (file_size + _V2_CHUNK_SIZE - 1) // _V2_CHUNK_SIZE)
    base_nonce = os.urandom(12)
    header = (
        _CHUNKED_V2_MAGIC
        + base_nonce
        + struct.pack(">I", _V2_CHUNK_SIZE)
        + struct.pack(">Q", num_chunks)
    )
    aesgcm = AESGCM(key)

    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
        delete=False, suffix=".enc", dir=str(out_dir) if out_dir else None
    )
    try:
        tmp.write(header)
        with Path(path).open("rb") as f:
            for i in range(num_chunks):
                chunk = f.read(_V2_CHUNK_SIZE)
                aad = header + struct.pack(">QB", i, int(i == num_chunks - 1))
                ct = aesgcm.encrypt(_chunk_nonce(base_nonce, i), chunk, aad)
                tmp.write(struct.pack(">I", len(ct)))
                tmp.write(ct)
        tmp.close()
    except BaseException:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    return tmp.name


class _CorruptFileError(ValueError):
    """The ciphertext is structurally damaged (truncated or padded)."""


def _read_exact(f: Any, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise _CorruptFileError("Encrypted file is truncated")
    return data


def _decrypt_stream(f: Any, out: Any, key: bytes) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    magic = f.read(8)

    if magic == _CHUNKED_V2_MAGIC:
        base_nonce = _read_exact(f, 12)
        chunk_size_raw = _read_exact(f, 4)
        num_chunks_raw = _read_exact(f, 8)
        header = magic + base_nonce + chunk_size_raw + num_chunks_raw
        num_chunks = struct.unpack(">Q", num_chunks_raw)[0]
        for i in range(num_chunks):
            ct_len = struct.unpack(">I", _read_exact(f, 4))[0]
            ct = _read_exact(f, ct_len)
            aad = header + struct.pack(">QB", i, int(i == num_chunks - 1))
            out.write(aesgcm.decrypt(_chunk_nonce(base_nonce, i), ct, aad))
        if f.read(1):
            raise _CorruptFileError("Unexpected data after the last encrypted chunk")

    elif magic == _CHUNKED_MAGIC:
        base_nonce = _read_exact(f, 12)
        num_chunks = struct.unpack(">I", _read_exact(f, 4))[0]
        for i in range(num_chunks):
            ct_len = struct.unpack(">I", _read_exact(f, 4))[0]
            ct = _read_exact(f, ct_len)
            out.write(aesgcm.decrypt(_chunk_nonce(base_nonce, i), ct, None))

    elif magic == _HEADER_MAGIC:
        nonce = _read_exact(f, 12)
        out.write(aesgcm.decrypt(nonce, f.read(), None))
    else:
        raise ValueError("Not a vault-encrypted file")


def decrypt_file(path: str, folder_id: int, out_path: str | Path | None = None) -> str:
    """Decrypt a vault file after download. Returns the plaintext path.

    Writes to *out_path* (or a temp file when omitted). On authentication
    failure (corrupted or tampered ciphertext) the partial output is deleted,
    the encrypted file is preserved, and VAULT_DECRYPTION_FAILED is raised.
    Blocking — call it via ``asyncio.to_thread``.
    """
    _require_healthy_db()
    key = _session_key_copy(folder_id)
    _reset_inactivity_timer(folder_id)

    if out_path is None:
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".dec")  # noqa: SIM115
    else:
        out = Path(out_path).open("wb")  # noqa: SIM115
    try:
        with Path(path).open("rb") as f:
            _decrypt_stream(f, out, key)
        out.close()
    except (InvalidTag, struct.error, _CorruptFileError) as exc:
        out.close()
        Path(out.name).unlink(missing_ok=True)
        log.warning(
            "Vault decryption failed: authentication tag mismatch (folder_id=%s, file=%s)",
            folder_id,
            path,
        )
        raise BridgeError(
            code=ErrorCode.VAULT_DECRYPTION_FAILED,
            message="Decryption failed: the encrypted file is corrupted or has been tampered with.",
            detail=f"AES-GCM authentication tag mismatch for file: {Path(path).name}. "
            "The encrypted file has been preserved unchanged on disk.",
        ) from exc
    except BaseException:
        out.close()
        Path(out.name).unlink(missing_ok=True)
        raise
    return out.name


__all__ = [
    "cmd_create_vault",
    "cmd_unlock_vault",
    "cmd_lock_vault",
    "cmd_list_vaults",
    "cmd_get_vault_status",
    "cmd_delete_vault",
    "ensure_vault_known",
    "forget_vault",
    "reset_local_state",
    "is_vault",
    "is_unlocked",
    "encrypt_file",
    "decrypt_file",
    "vault_temp_dir",
    "purge_temp_files",
    "format_vault_tag",
    "parse_vault_tag",
    "strip_vault_tag",
    "set_auto_lock_timeout",
    "get_auto_lock_timeout",
]
