"""Unit tests for telegrab.infra.logger module.

Run with: python -m pytest tests/test_logger.py -v
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock webview before importing telegrab modules that transitively depend on it
sys.modules.setdefault("webview", MagicMock())

from telegrab.infra.logger import _sanitize_args, setup_logging


class TestSanitizeArgs:
    """Tests for _sanitize_args sensitive value redaction."""

    def test_redacts_password_key(self):
        args = {"password": "secret123", "username": "user"}
        result = _sanitize_args(args)
        assert "secret123" not in result
        assert "<redacted>" in result
        assert "user" in result

    def test_redacts_token_key(self):
        args = {"token": "abc-def-ghi", "name": "test"}
        result = _sanitize_args(args)
        assert "abc-def-ghi" not in result
        assert "<redacted>" in result

    def test_redacts_api_hash_key(self):
        args = {"apiHash": "myhash123", "other": "visible"}
        result = _sanitize_args(args)
        assert "myhash123" not in result
        assert "<redacted>" in result

    def test_redacts_api_hash_underscore_key(self):
        args = {"api_hash": "hashvalue", "data": "ok"}
        result = _sanitize_args(args)
        assert "hashvalue" not in result
        assert "<redacted>" in result

    def test_redacts_api_id_key(self):
        args = {"api_id": "12345678", "mode": "fast"}
        result = _sanitize_args(args)
        assert "12345678" not in result
        assert "<redacted>" in result

    def test_redacts_session_token_key(self):
        args = {"sessionToken": "tok-xyz", "flag": True}
        result = _sanitize_args(args)
        assert "tok-xyz" not in result
        assert "<redacted>" in result

    def test_truncates_long_string_values(self):
        long_value = "x" * 100
        args = {"description": long_value}
        result = _sanitize_args(args)
        assert long_value not in result
        assert "..." in result

    def test_truncates_output_to_200_chars(self):
        # Create many args to exceed 200 chars
        args = {f"key_{i}": f"value_{i}" for i in range(50)}
        result = _sanitize_args(args)
        assert len(result) <= 200

    def test_empty_dict(self):
        result = _sanitize_args({})
        assert result == "{}"

    def test_preserves_non_sensitive_values(self):
        args = {"folder_id": 42, "name": "docs"}
        result = _sanitize_args(args)
        assert "42" in result
        assert "docs" in result

    def test_case_insensitive_key_matching(self):
        args = {"Password": "secret", "TOKEN": "abc"}
        result = _sanitize_args(args)
        assert "secret" not in result
        assert "abc" not in result


class TestSetupLogging:
    """Tests for setup_logging configuration."""

    def test_creates_log_file(self, tmp_path):
        setup_logging(tmp_path, level="DEBUG")
        log_file = tmp_path / "telegrab.log"
        assert log_file.exists()

    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "sub" / "dir"
        setup_logging(nested, level="INFO")
        assert nested.exists()
        assert (nested / "telegrab.log").exists()

    def test_log_format_matches_spec(self, tmp_path):
        setup_logging(tmp_path, level="DEBUG")
        logger = logging.getLogger("test.format")
        logger.debug("test message")

        log_file = tmp_path / "telegrab.log"
        content = log_file.read_text(encoding="utf-8")

        # Check structured format: ISO-8601 | LEVEL | logger | message
        # The startup log is the first entry, then our test message
        lines = [line for line in content.strip().splitlines() if line]
        # At least the startup entry should exist
        assert len(lines) >= 1

        # Validate format of each line
        pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"  # ISO-8601 timestamp
            r"(,\d{3})?"  # optional milliseconds
            r" \| "  # separator
            r"(DEBUG|INFO|WARNING|ERROR|CRITICAL)"  # level
            r" \| "  # separator
            r"[\w.]+"  # logger name
            r" \| "  # separator
            r".+"  # message
        )
        for line in lines:
            assert pattern.match(line), f"Line does not match format: {line!r}"

    def test_startup_log_contains_version_info(self, tmp_path):
        setup_logging(tmp_path, level="INFO")

        log_file = tmp_path / "telegrab.log"
        content = log_file.read_text(encoding="utf-8")

        assert "Application started" in content
        assert "Python" in content
        assert "level=INFO" in content

    def test_respects_log_level(self, tmp_path):
        setup_logging(tmp_path, level="WARNING")
        logger = logging.getLogger("test.level")
        logger.debug("should not appear")
        logger.info("should not appear either")
        logger.warning("should appear")

        log_file = tmp_path / "telegrab.log"
        content = log_file.read_text(encoding="utf-8")

        assert "should not appear" not in content
        assert "should appear" in content

    def test_handles_invalid_level_gracefully(self, tmp_path):
        # Should default to INFO for invalid level strings
        setup_logging(tmp_path, level="INVALID_LEVEL")
        logger = logging.getLogger("test.invalid")
        logger.debug("debug msg")
        logger.info("info msg")

        log_file = tmp_path / "telegrab.log"
        content = log_file.read_text(encoding="utf-8")

        assert "debug msg" not in content
        assert "info msg" in content
