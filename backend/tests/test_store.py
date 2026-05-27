"""Unit tests for JsonStore corruption recovery.

Tests the store corruption detection and recovery behavior:
- Invalid JSON triggers quarantine rename
- Empty file triggers quarantine rename
- Valid JSON loads normally
- Missing file initializes empty without quarantine
"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the store module directly (avoid infra/__init__.py which imports webview)
import telegrab.infra.store as store_module
from telegrab.infra.store import JsonStore


class TestStoreCorruptionRecovery:
    """Tests for store corruption detection and recovery."""

    def _make_store(self, tmp_path, content: bytes | str | None = None):
        """Create a JsonStore with a temp file containing specified content."""
        store_file = tmp_path / "store.json"
        if content is not None:
            if isinstance(content, str):
                store_file.write_text(content, encoding="utf-8")
            else:
                store_file.write_bytes(content)

        with patch.object(store_module, "store_path", return_value=store_file):
            with patch.object(store_module, "_restrict_permissions"):
                obj = JsonStore()
        return obj, store_file

    def test_valid_json_loads_normally(self, tmp_path):
        """Valid JSON file should load data without any quarantine."""
        data = {"theme": "dark", "language": "en"}
        store, store_file = self._make_store(tmp_path, json.dumps(data))

        assert store.get("theme") == "dark"
        assert store.get("language") == "en"
        # No .corrupt file should exist
        corrupt_files = list(tmp_path.glob("*.corrupt.*"))
        assert len(corrupt_files) == 0

    def test_missing_file_initializes_empty(self, tmp_path):
        """Missing store file should initialize with empty dict, no quarantine."""
        store, store_file = self._make_store(tmp_path, None)

        assert store.entries() == {}
        # No .corrupt file should exist
        corrupt_files = list(tmp_path.glob("*.corrupt.*"))
        assert len(corrupt_files) == 0

    def test_invalid_json_triggers_quarantine(self, tmp_path):
        """Invalid JSON triggers rename to .corrupt.<timestamp> and empty init."""
        corrupt_content = "this is not valid json {{{["
        store, store_file = self._make_store(tmp_path, corrupt_content)

        # Store should be empty
        assert store.entries() == {}

        # Original file should no longer exist
        assert not store_file.exists()

        # A .corrupt.<timestamp> file should exist with the original content
        corrupt_files = list(tmp_path.glob("store.json.corrupt.*"))
        assert len(corrupt_files) == 1
        assert corrupt_files[0].read_text(encoding="utf-8") == corrupt_content

    def test_empty_file_triggers_quarantine(self, tmp_path):
        """Empty file (invalid JSON) should trigger quarantine."""
        store, store_file = self._make_store(tmp_path, "")

        assert store.entries() == {}
        assert not store_file.exists()

        corrupt_files = list(tmp_path.glob("store.json.corrupt.*"))
        assert len(corrupt_files) == 1

    def test_partial_json_triggers_quarantine(self, tmp_path):
        """Truncated/partial JSON should trigger quarantine."""
        store, store_file = self._make_store(tmp_path, '{"key": "val')

        assert store.entries() == {}
        assert not store_file.exists()

        corrupt_files = list(tmp_path.glob("store.json.corrupt.*"))
        assert len(corrupt_files) == 1
        assert corrupt_files[0].read_text(encoding="utf-8") == '{"key": "val'

    def test_corrupt_file_timestamp_suffix(self, tmp_path):
        """Quarantine file should have integer timestamp suffix."""
        before = int(time.time())
        store, store_file = self._make_store(tmp_path, "not json")
        after = int(time.time())

        corrupt_files = list(tmp_path.glob("store.json.corrupt.*"))
        assert len(corrupt_files) == 1

        # Extract timestamp from filename
        suffix = corrupt_files[0].name.split(".corrupt.")[1]
        timestamp = int(suffix)
        assert before <= timestamp <= after

    def test_binary_content_triggers_quarantine(self, tmp_path):
        """Binary content (not valid JSON) should trigger quarantine."""
        store, store_file = self._make_store(tmp_path, b"\x00\x01\x02\xff\xfe")

        assert store.entries() == {}
        assert not store_file.exists()

        corrupt_files = list(tmp_path.glob("store.json.corrupt.*"))
        assert len(corrupt_files) == 1

    def test_store_operable_after_corruption_recovery(self, tmp_path):
        """After corruption recovery, store should be fully operational."""
        store, store_file = self._make_store(tmp_path, "corrupt data")

        # Should be able to set/get values
        store.set("new_key", "new_value")
        assert store.get("new_key") == "new_value"
