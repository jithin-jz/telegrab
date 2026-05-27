"""Structured error types for the pywebview Bridge layer.

Every Bridge error is represented as a :class:`BridgeError` dataclass
with a machine-readable code, a user-facing message, and a technical
detail string for debugging. Error codes follow the ``CATEGORY_DETAIL``
naming convention (e.g. ``NETWORK_TIMEOUT``, ``VALIDATION_MISSING_FIELD``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Regex that all error codes must satisfy
ERROR_CODE_PATTERN = re.compile(r"^[A-Z]+_[A-Z_]+$")

# Maximum lengths for message and detail fields
MAX_MESSAGE_LENGTH = 200
MAX_DETAIL_LENGTH = 1000


@dataclass(frozen=True, slots=True)
class BridgeError(Exception):
    """Structured error returned by Bridge calls to the frontend.

    Inherits from Exception so it can be raised and caught in Python's
    exception handling flow while also being serializable for the frontend.

    Parameters
    ----------
    code : str
        Machine-readable error code in ``CATEGORY_DETAIL`` format.
        Must match the regex ``^[A-Z]+_[A-Z_]+$``.
    message : str
        User-facing description, capped at 200 characters.
    detail : str
        Technical detail for debugging, capped at 1000 characters.
    """

    code: str
    message: str
    detail: str

    def __post_init__(self) -> None:
        # Validate code format
        if not ERROR_CODE_PATTERN.match(self.code):
            raise ValueError(
                f"Error code must match {ERROR_CODE_PATTERN.pattern!r}, "
                f"got {self.code!r}"
            )
        # Truncate message and detail to their max lengths
        if len(self.message) > MAX_MESSAGE_LENGTH:
            object.__setattr__(self, "message", self.message[:MAX_MESSAGE_LENGTH])
        if len(self.detail) > MAX_DETAIL_LENGTH:
            object.__setattr__(self, "detail", self.detail[:MAX_DETAIL_LENGTH])

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for returning to the frontend."""
        return {
            "__error": True,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


class ErrorCode:
    """Constants for all Bridge error codes.

    Naming convention: ``CATEGORY_DETAIL`` where category identifies the
    subsystem and detail describes the specific failure mode.
    """

    # ── Network errors ──────────────────────────────────────────────────────
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_DISCONNECTED = "NETWORK_DISCONNECTED"
    NETWORK_FLOOD_WAIT = "NETWORK_FLOOD_WAIT"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"

    # ── Validation errors ───────────────────────────────────────────────────
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_TYPE = "VALIDATION_INVALID_TYPE"

    # ── Transfer errors ─────────────────────────────────────────────────────
    TRANSFER_CANCELLED = "TRANSFER_CANCELLED"
    TRANSFER_NETWORK_ERROR = "TRANSFER_NETWORK_ERROR"
    TRANSFER_FILE_NOT_FOUND = "TRANSFER_FILE_NOT_FOUND"
    TRANSFER_CLEANUP_FAILED = "TRANSFER_CLEANUP_FAILED"

    # ── Vault errors ────────────────────────────────────────────────────────
    VAULT_LOCKED = "VAULT_LOCKED"
    VAULT_DECRYPTION_FAILED = "VAULT_DECRYPTION_FAILED"
    VAULT_DB_CORRUPT = "VAULT_DB_CORRUPT"
    VAULT_WRONG_PASSWORD = "VAULT_WRONG_PASSWORD"

    # ── Store errors ────────────────────────────────────────────────────────
    STORE_CORRUPT = "STORE_CORRUPT"
    STORE_PERMISSION_ERROR = "STORE_PERMISSION_ERROR"

    # ── Bridge infrastructure errors ────────────────────────────────────────
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    BRIDGE_NOT_READY = "BRIDGE_NOT_READY"
