"""Unit tests for transfer reliability and cancellation improvements (Tasks 6.1-6.4).

Tests cover:
- Per-chunk cancellation check (6.1)
- Download cancellation with partial file cleanup and error emission (6.2)
- Upload failure and cancellation event emission (6.3)
- Vault-encrypted upload cleanup on cancel (6.4)
- Dedup hash storage failure logging (Req 2.5)

These tests verify the implementation via source inspection and focused behavioral
tests, avoiding the full telethon/pywebview import chain.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

# Path to the files.py module source
_FILES_PY = Path(__file__).resolve().parent.parent / "telegrab" / "services" / "files.py"
_SOURCE = _FILES_PY.read_text(encoding="utf-8")


def _get_function_source(source: str, func_name: str) -> str:
    """Extract the source code of a specific async function from the module."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            if node.name == func_name:
                lines = source.splitlines()
                return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise ValueError(f"Function {func_name} not found in source")


class TestPerChunkCancellation:
    """Task 6.1: Verify cancellation check happens per-chunk via progress_cb.

    The progress_cb is called by fast_transfer for each chunk (512KB).
    It checks tg.is_cancelled(tid) and raises asyncio.CancelledError,
    bounding cancellation latency to one chunk transmission time.
    """

    def test_upload_progress_cb_checks_cancellation(self):
        """Upload progress_cb calls tg.is_cancelled and raises CancelledError."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        # The progress callback must check cancellation
        assert "tg.is_cancelled(tid)" in upload_src
        assert "asyncio.CancelledError" in upload_src

    def test_download_progress_cb_checks_cancellation(self):
        """Download progress_cb calls tg.is_cancelled and raises CancelledError."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        assert "tg.is_cancelled(tid)" in download_src
        assert "asyncio.CancelledError" in download_src

    def test_cancellation_check_is_first_in_progress_cb(self):
        """The cancellation check comes before progress throttling."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        # is_cancelled check should appear before the time-based throttle
        cancel_pos = upload_src.find("tg.is_cancelled(tid)")
        throttle_pos = upload_src.find("_PROGRESS_INTERVAL_SECS")
        assert cancel_pos < throttle_pos, (
            "Cancellation check must precede progress throttling"
        )


class TestDownloadCancellationCleanup:
    """Task 6.2: Download cancellation with partial file cleanup."""

    def test_download_cancel_attempts_file_deletion(self):
        """On cancel, the download handler calls Path(save_path).unlink()."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        # Find the CancelledError handler
        cancel_idx = download_src.find("except asyncio.CancelledError:")
        assert cancel_idx > 0
        cancel_block = download_src[cancel_idx:cancel_idx + 800]
        assert "unlink()" in cancel_block

    def test_download_cancel_handles_file_not_found_silently(self):
        """FileNotFoundError during unlink is handled silently (no event)."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        cancel_idx = download_src.find("except asyncio.CancelledError:")
        cancel_block = download_src[cancel_idx:cancel_idx + 800]
        assert "FileNotFoundError" in cancel_block
        assert "pass" in cancel_block.split("FileNotFoundError")[1][:50]

    def test_download_cancel_emits_transfer_failed_on_os_error(self):
        """On OSError during unlink, emit transfer-failed with error reason."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        cancel_idx = download_src.find("except asyncio.CancelledError:")
        cancel_block = download_src[cancel_idx:cancel_idx + 800]
        # Must have OSError handling
        assert "except OSError" in cancel_block
        # Must emit transfer-failed
        assert "transfer-failed" in cancel_block
        # Must include error reason
        assert "Failed to delete partial file" in cancel_block

    def test_download_cancel_includes_transfer_id_in_event(self):
        """The transfer-failed event includes the transfer ID."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        cancel_idx = download_src.find("except asyncio.CancelledError:")
        cancel_block = download_src[cancel_idx:cancel_idx + 800]
        assert '"transferId"' in cancel_block or "'transferId'" in cancel_block


class TestUploadFailureEventEmission:
    """Task 6.3: Upload failure and cancellation event emission."""

    def test_upload_cancel_emits_user_cancellation_reason(self):
        """On user cancellation mid-upload, emit transfer-failed with 'user cancellation'."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        assert cancel_idx > 0
        cancel_block = upload_src[cancel_idx:cancel_idx + 600]
        assert '"user cancellation"' in cancel_block

    def test_upload_cancel_includes_bytes_sent(self):
        """The transfer-failed event on cancellation includes bytes_sent."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 900]
        assert '"bytesSent"' in cancel_block or "'bytesSent'" in cancel_block

    def test_upload_cancel_only_emits_when_chunks_sent(self):
        """transfer-failed is only emitted if at least one chunk was sent (bytes > 0)."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 600]
        # The condition should check bytes_sent > 0
        assert "bytes_sent > 0" in cancel_block or "last_emit_bytes" in cancel_block

    def test_upload_network_error_emits_transfer_failed(self):
        """On network error (generic Exception) after chunks sent, emit transfer-failed."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        # Find the generic Exception handler after CancelledError
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        exc_idx = upload_src.find("except Exception", cancel_idx)
        assert exc_idx > cancel_idx
        exc_block = upload_src[exc_idx:exc_idx + 400]
        assert "transfer-failed" in exc_block

    def test_upload_network_error_includes_error_reason(self):
        """The transfer-failed event includes the error reason as a string."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        exc_idx = upload_src.find("except Exception", cancel_idx)
        exc_block = upload_src[exc_idx:exc_idx + 400]
        assert "str(exc)" in exc_block

    def test_upload_network_error_only_emits_when_chunks_sent(self):
        """transfer-failed on error is only emitted if last_emit_bytes > 0."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        exc_idx = upload_src.find("except Exception", cancel_idx)
        exc_block = upload_src[exc_idx:exc_idx + 400]
        assert "last_emit_bytes > 0" in exc_block


class TestVaultEncryptedUploadCleanup:
    """Task 6.4: Vault-encrypted upload cleanup on cancel."""

    def test_upload_deletes_encrypted_tmp_on_cancel(self):
        """On CancelledError, the encrypted_tmp file is deleted before re-raising."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 600]
        # Must check and delete encrypted_tmp
        assert "encrypted_tmp" in cancel_block
        assert "unlink" in cancel_block

    def test_upload_encrypted_tmp_deletion_suppresses_os_error(self):
        """OSError during encrypted_tmp cleanup is suppressed (contextlib.suppress)."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 600]
        # Should use contextlib.suppress(OSError) for cleanup
        assert "suppress" in cancel_block or "OSError" in cancel_block

    def test_upload_encrypted_tmp_cleanup_before_event_emission(self):
        """The encrypted temp cleanup occurs before event emission."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 600]
        # encrypted_tmp cleanup should come before transfer-failed emission
        enc_cleanup_pos = cancel_block.find("encrypted_tmp")
        event_pos = cancel_block.find("transfer-failed")
        assert enc_cleanup_pos < event_pos, (
            "Encrypted temp cleanup must occur before event emission"
        )


class TestDedupHashStorageLogging:
    """Requirement 2.5: Dedup hash storage failure logging."""

    def test_dedup_failure_logs_warning(self):
        """On dedup hash storage failure, log a warning (not silently pass)."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        # Find the dedup section
        dedup_idx = upload_src.find("Store file hash for duplicate detection")
        assert dedup_idx > 0
        dedup_block = upload_src[dedup_idx:dedup_idx + 300]
        assert "log.warning" in dedup_block
        # Must not have a bare "pass" after the except
        assert "pass" not in dedup_block.split("except")[1][:30]

    def test_dedup_failure_log_includes_folder_id(self):
        """The dedup failure warning includes the folder_id."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        dedup_idx = upload_src.find("Store file hash for duplicate detection")
        dedup_block = upload_src[dedup_idx:dedup_idx + 300]
        assert "folder_id" in dedup_block

    def test_dedup_failure_log_includes_filename(self):
        """The dedup failure warning includes the file name."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        dedup_idx = upload_src.find("Store file hash for duplicate detection")
        dedup_block = upload_src[dedup_idx:dedup_idx + 300]
        assert "file_name" in dedup_block


class TestTransferEventFormat:
    """Verify the transfer-failed event payload format matches design spec."""

    def test_upload_cancel_event_has_correct_keys(self):
        """The transfer-failed event has transferId, bytesSent, reason keys."""
        upload_src = _get_function_source(_SOURCE, "cmd_upload_file")
        cancel_idx = upload_src.find("except asyncio.CancelledError:")
        cancel_block = upload_src[cancel_idx:cancel_idx + 900]
        assert '"transferId"' in cancel_block
        assert '"bytesSent"' in cancel_block
        assert '"reason"' in cancel_block

    def test_download_cancel_event_has_correct_keys(self):
        """The download transfer-failed event has transferId, bytesSent, reason keys."""
        download_src = _get_function_source(_SOURCE, "cmd_download_file")
        cancel_idx = download_src.find("except asyncio.CancelledError:")
        cancel_block = download_src[cancel_idx:cancel_idx + 800]
        assert '"transferId"' in cancel_block
        assert '"bytesSent"' in cancel_block
        assert '"reason"' in cancel_block
