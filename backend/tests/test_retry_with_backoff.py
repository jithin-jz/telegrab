"""Unit tests for retry_with_backoff in telegrab.services.network."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

# Mock webview and telethon before importing telegrab packages
if "webview" not in sys.modules:
    sys.modules["webview"] = MagicMock()

# Mock telethon.errors with a real FloodWaitError-like exception
_mock_telethon = MagicMock()


class _MockFloodWaitError(Exception):
    """Simulates telethon.errors.FloodWaitError."""

    def __init__(self, seconds: int = 5):
        self.seconds = seconds
        super().__init__(f"A wait of {seconds} seconds is required")


_mock_telethon.errors.FloodWaitError = _MockFloodWaitError
_mock_telethon.FloodWaitError = _MockFloodWaitError

# Temporarily mock telethon to import network module without polluting other tests during collection
_orig_telethon = sys.modules.get("telethon")
_orig_telethon_errors = sys.modules.get("telethon.errors")

sys.modules["telethon"] = _mock_telethon
sys.modules["telethon.errors"] = _mock_telethon.errors
sys.modules["telethon.errors"].FloodWaitError = _MockFloodWaitError

import pytest

from telegrab.services.network import ExponentialBackoff, retry_with_backoff

# Restore original sys.modules immediately after import
if _orig_telethon is not None:
    sys.modules["telethon"] = _orig_telethon
else:
    sys.modules.pop("telethon", None)

if _orig_telethon_errors is not None:
    sys.modules["telethon.errors"] = _orig_telethon_errors
else:
    sys.modules.pop("telethon.errors", None)


@pytest.fixture(autouse=True)
def mock_telethon_during_test():
    """Autouse fixture to temporarily mock telethon in sys.modules during each test."""
    with patch.dict(sys.modules, {
        "telethon": _mock_telethon,
        "telethon.errors": _mock_telethon.errors
    }):
        yield


@pytest.fixture
def fast_backoff():
    """A backoff with zero delays for fast tests."""
    return ExponentialBackoff(base_delay=0.0, max_delay=0.0, max_attempts=3)


class TestRetryWithBackoffSuccess:
    """Tests where the operation eventually succeeds."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(operation, backoff=fast_backoff)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_timeout_retry(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("request timed out")
            return "recovered"

        result = await retry_with_backoff(operation, backoff=fast_backoff)
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_succeeds_after_connection_error_retry(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("connection reset")
            return "connected"

        result = await retry_with_backoff(operation, backoff=fast_backoff)
        assert result == "connected"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_after_flood_wait_retry(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise _MockFloodWaitError(seconds=1)
            return "unblocked"

        result = await retry_with_backoff(operation, backoff=fast_backoff)
        assert result == "unblocked"
        assert call_count == 2


class TestRetryWithBackoffExhaustion:
    """Tests where retries are exhausted."""

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts_timeout(self, fast_backoff):
        async def operation():
            raise TimeoutError("always times out")

        with pytest.raises(TimeoutError):
            await retry_with_backoff(operation, backoff=fast_backoff)

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts_connection(self, fast_backoff):
        async def operation():
            raise ConnectionError("always disconnected")

        with pytest.raises(ConnectionError):
            await retry_with_backoff(operation, backoff=fast_backoff)

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts_flood(self, fast_backoff):
        async def operation():
            raise _MockFloodWaitError(seconds=0)

        with pytest.raises(_MockFloodWaitError):
            await retry_with_backoff(operation, backoff=fast_backoff)


class TestRetryWithBackoffEvents:
    """Tests for event emission during retries."""

    @pytest.mark.asyncio
    async def test_emits_rate_limited_on_flood_wait(self, fast_backoff):
        emitted_events = []

        async def operation():
            raise _MockFloodWaitError(seconds=5)

        with patch("telegrab.services.network.bus") as mock_bus:
            mock_bus.emit = lambda event, payload: emitted_events.append(
                (event, payload)
            )
            with pytest.raises(_MockFloodWaitError):
                await retry_with_backoff(operation, backoff=fast_backoff)

        # Should have emitted rate-limited for each attempt
        rate_limited_events = [
            (e, p) for e, p in emitted_events if e == "rate-limited"
        ]
        assert len(rate_limited_events) == 3  # max_attempts = 3
        for _, payload in rate_limited_events:
            assert "wait_seconds" in payload

    @pytest.mark.asyncio
    async def test_emits_transfer_failed_after_exhaustion(self, fast_backoff):
        emitted_events = []

        async def operation():
            raise TimeoutError("network timeout")

        with patch("telegrab.services.network.bus") as mock_bus:
            mock_bus.emit = lambda event, payload: emitted_events.append(
                (event, payload)
            )
            with pytest.raises(TimeoutError):
                await retry_with_backoff(
                    operation, transfer_id="test-transfer-123", backoff=fast_backoff
                )

        # Should have emitted transfer-failed
        failed_events = [
            (e, p) for e, p in emitted_events if e == "transfer-failed"
        ]
        assert len(failed_events) == 1
        event_name, payload = failed_events[0]
        assert payload["transferId"] == "test-transfer-123"
        assert payload["bytesSent"] == 0
        assert "Max retries" in payload["reason"]

    @pytest.mark.asyncio
    async def test_no_transfer_failed_without_transfer_id(self, fast_backoff):
        emitted_events = []

        async def operation():
            raise ConnectionError("dropped")

        with patch("telegrab.services.network.bus") as mock_bus:
            mock_bus.emit = lambda event, payload: emitted_events.append(
                (event, payload)
            )
            with pytest.raises(ConnectionError):
                await retry_with_backoff(operation, backoff=fast_backoff)

        # No transfer-failed since no transfer_id was provided
        failed_events = [
            (e, p) for e, p in emitted_events if e == "transfer-failed"
        ]
        assert len(failed_events) == 0


class TestRetryWithBackoffNonRetriable:
    """Tests that non-transient errors are not retried."""

    @pytest.mark.asyncio
    async def test_value_error_not_retried(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise ValueError("bad argument")

        with pytest.raises(ValueError):
            await retry_with_backoff(operation, backoff=fast_backoff)

        # Should have been called only once — not retried
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_runtime_error_not_retried(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("unexpected")

        with pytest.raises(RuntimeError):
            await retry_with_backoff(operation, backoff=fast_backoff)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cancelled_error_not_retried(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError("upload cancelled")

        with pytest.raises(asyncio.CancelledError):
            await retry_with_backoff(operation, backoff=fast_backoff)

        assert call_count == 1


class TestRetryWithBackoffOSError:
    """Tests for OSError (parent of ConnectionError) handling."""

    @pytest.mark.asyncio
    async def test_connection_reset_error_retried(self, fast_backoff):
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionResetError("reset by peer")
            return "ok"

        result = await retry_with_backoff(operation, backoff=fast_backoff)
        assert result == "ok"
        assert call_count == 3


