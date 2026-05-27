"""Structured logging with rotation and sensitive-value sanitization.

Configures Python's standard logging with:
- Structured format: <ISO-8601 timestamp> | <LEVEL> | <logger.name> | <message>
- File rotation: 50 MB max per file, 3 backup files
- Sensitive value redaction for password, token, apiHash, api_hash, api_id, sessionToken

Usage:
    from telegrab.infra.logger import setup_logging
    setup_logging(app_data_dir, level="INFO")
"""

from __future__ import annotations

import logging
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegrab import __version__

# Maximum log file size in bytes (50 MB)
_MAX_BYTES = 50 * 1024 * 1024

# Number of rotated backup files to keep
_BACKUP_COUNT = 3

# Structured log format
_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# ISO-8601 timestamp format
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Keys whose values must never appear in logs
_SENSITIVE_KEYS = frozenset(
    {"password", "token", "apihash", "api_hash", "api_id", "sessiontoken"}
)


def _sanitize_args(args: dict) -> str:
    """Produce a loggable summary of arguments, redacting sensitive values.

    Sensitive keys (password, token, apiHash, api_hash, api_id, sessionToken)
    are replaced with '<redacted>'. Long string values are truncated to 50
    characters. The final output is truncated to 200 characters.
    """
    if not args:
        return "{}"

    sanitized = {}
    for k, v in args.items():
        key_lower = k.lower()
        if key_lower in _SENSITIVE_KEYS or any(
            s in key_lower for s in ("password", "token", "key", "hash")
        ):
            sanitized[k] = "<redacted>"
        elif isinstance(v, str) and len(v) > 50:
            sanitized[k] = v[:50] + "..."
        else:
            sanitized[k] = v

    result = str(sanitized)
    return result[:200]


def setup_logging(app_data_dir: Path, level: str = "INFO") -> None:
    """Configure structured logging with file rotation.

    Sets up the root logger with:
    - A RotatingFileHandler writing to ``app_data_dir/telegrab.log``
    - A StreamHandler for console output (stderr)
    - The structured format: ``<ISO-8601> | <LEVEL> | <logger> | <message>``

    After configuration, logs a startup entry at INFO level with the
    application version, Python version, platform, and active log level.

    Parameters
    ----------
    app_data_dir:
        Directory where the log file will be created. Created if it does
        not exist.
    level:
        Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        Defaults to INFO.
    """
    app_data_dir = Path(app_data_dir)
    app_data_dir.mkdir(parents=True, exist_ok=True)

    log_file = app_data_dir / "telegrab.log"
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup entry
    logger = logging.getLogger("telegrab.app")
    logger.info(
        "Application started v%s Python %s %s level=%s",
        __version__,
        platform.python_version(),
        sys.platform,
        level.upper(),
    )
