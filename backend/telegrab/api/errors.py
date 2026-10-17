"""Structured error types for the pywebview Bridge layer.

Every Bridge error is represented as a :class:`BridgeError` exception
with a machine-readable code, a user-facing message, and a technical
detail string for debugging. Error codes follow the ``CATEGORY_DETAIL``
naming convention (e.g. ``NETWORK_TIMEOUT``, ``VALIDATION_MISSING_FIELD``).
"""

from __future__ import annotations

import re

# Regex that all error codes must satisfy
ERROR_CODE_PATTERN = re.compile(r"^[A-Z]+_[A-Z_]+$")

# Maximum lengths for message and detail fields
MAX_MESSAGE_LENGTH = 200
MAX_DETAIL_LENGTH = 1000


class BridgeError(Exception):
    """Structured error returned by Bridge calls to the frontend.

    Inherits from Exception so it can be raised and caught in Python's
    exception handling flow while also being serializable for the frontend.
    The three fields are immutable once constructed.

    (This used to be a frozen dataclass, but a frozen dataclass forbids the
    interpreter-level ``__traceback__`` assignment that ``contextlib`` makes
    when an exception passes through a ``@contextmanager`` — which turned
    the error into an unrelated TypeError.)

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

    _FIELDS = ("code", "message", "detail")

    code: str
    message: str
    detail: str

    def __init__(self, code: str, message: str, detail: str) -> None:
        # Validate code format
        if not ERROR_CODE_PATTERN.match(code):
            raise ValueError(
                f"Error code must match {ERROR_CODE_PATTERN.pattern!r}, got {code!r}"
            )
        # Truncate message and detail to their max lengths
        message = message[:MAX_MESSAGE_LENGTH]
        detail = detail[:MAX_DETAIL_LENGTH]
        super().__init__(message)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "detail", detail)

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._FIELDS:
            raise AttributeError(f"BridgeError.{name} is read-only")
        super().__setattr__(name, value)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BridgeError):
            return NotImplemented
        return (self.code, self.message, self.detail) == (
            other.code,
            other.message,
            other.detail,
        )

    def __hash__(self) -> int:
        return hash((self.code, self.message, self.detail))

    def __repr__(self) -> str:
        return (
            f"BridgeError(code={self.code!r}, message={self.message!r}, "
            f"detail={self.detail!r})"
        )

    def __str__(self) -> str:
        return self.message

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

    # ── Telegram / command errors ───────────────────────────────────────────
    TELEGRAM_NOT_CONNECTED = "TELEGRAM_NOT_CONNECTED"
    TELEGRAM_RPC_ERROR = "TELEGRAM_RPC_ERROR"
    COMMAND_FAILED = "COMMAND_FAILED"

    # ── Bridge infrastructure errors ────────────────────────────────────────
    BRIDGE_TIMEOUT = "BRIDGE_TIMEOUT"
    BRIDGE_NOT_READY = "BRIDGE_NOT_READY"
    BRIDGE_INTERNAL_ERROR = "BRIDGE_INTERNAL_ERROR"
