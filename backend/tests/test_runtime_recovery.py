"""Tests for AsyncRuntime crash recovery logic."""

from __future__ import annotations

import sys
import threading
import time
from unittest.mock import MagicMock, patch

from telegrab.infra.runtime import _MAX_RESTARTS, _RESTART_WINDOW, AsyncRuntime


class TestAsyncRuntimeCrashRecovery:
    """Tests for runtime crash detection and recovery."""

    def test_clean_stop_does_not_trigger_recovery(self):
        """A normal stop() call should NOT trigger recovery."""
        runtime = AsyncRuntime()
        runtime.start()
        assert runtime._loop is not None

        with patch.object(runtime, "_attempt_recovery") as mock_recovery:
            runtime.stop()
            # Give a moment for thread cleanup
            time.sleep(0.1)
            mock_recovery.assert_not_called()

    def test_stopping_flag_set_on_clean_stop(self):
        """stop() sets _stopping to True so recovery is not triggered."""
        runtime = AsyncRuntime()
        runtime.start()
        assert runtime._stopping is False
        runtime.stop()
        assert runtime._stopping is True

    def test_crash_triggers_recovery(self):
        """If the loop crashes (not a clean stop), recovery should be triggered."""
        runtime = AsyncRuntime()
        runtime.start()
        assert runtime._loop is not None

        recovery_called = threading.Event()

        def mock_recovery():
            recovery_called.set()

        runtime._attempt_recovery = mock_recovery  # type: ignore[assignment]

        # Simulate a crash by stopping the loop without setting _stopping flag
        loop = runtime._loop
        loop.call_soon_threadsafe(loop.stop)

        # Wait for recovery to be triggered
        assert recovery_called.wait(timeout=3.0), "Recovery was not triggered after crash"

    def test_recovery_restarts_loop(self):
        """_attempt_recovery should create a new functioning loop."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._loop = None
        runtime._thread = None
        runtime._ready.clear()

        with patch.object(runtime, "_reconnect_telegram"):
            runtime._attempt_recovery()

        # The runtime should have a new working loop
        assert runtime._loop is not None
        assert runtime._loop.is_running()

        # Verify it works
        async def simple():
            return 42

        result = runtime.run_coro(simple(), timeout=5.0)
        assert result == 42

        runtime.stop()

    def test_recovery_calls_reconnect_telegram(self):
        """On successful restart, _reconnect_telegram should be called."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._loop = None
        runtime._thread = None
        runtime._ready.clear()

        with patch.object(runtime, "_reconnect_telegram") as mock_reconnect:
            runtime._attempt_recovery()
            mock_reconnect.assert_called_once()

        runtime.stop()

    def test_recovery_emits_toast_on_success(self):
        """On successful recovery, a recovery toast should be emitted via bus."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._loop = None
        runtime._thread = None
        runtime._ready.clear()

        # We need to patch the bus at the module level where it's imported
        mock_bus = MagicMock()

        with patch.object(runtime, "_reconnect_telegram"), patch.dict(sys.modules, {}):
            # Patch the bus object that gets imported
            import telegrab.infra.events as events_mod
            original_bus = events_mod.bus
            events_mod.bus = mock_bus
            try:
                runtime._attempt_recovery()
            finally:
                events_mod.bus = original_bus

        # Check that recovery toast was emitted
        mock_bus.emit.assert_called()
        call_args = mock_bus.emit.call_args
        assert call_args[0][0] == "toast"
        payload = call_args[0][1]
        assert payload["type"] == "recovery"
        assert "restored" in payload["title"].lower() or "restored" in payload["message"].lower()

        runtime.stop()

    def test_recovery_exhausted_emits_fatal_toast(self):
        """When all restart attempts are exhausted, emit a fatal toast."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._restart_count = _MAX_RESTARTS  # Already at max
        runtime._restart_window_start = time.monotonic()  # Within window

        mock_bus = MagicMock()

        import telegrab.infra.events as events_mod
        original_bus = events_mod.bus
        events_mod.bus = mock_bus
        try:
            runtime._attempt_recovery()
        finally:
            events_mod.bus = original_bus

        mock_bus.emit.assert_called_once()
        event_name, payload = mock_bus.emit.call_args[0]
        assert event_name == "toast"
        assert payload["type"] == "fatal"
        assert "restart" in payload["message"].lower()

    def test_restart_counter_resets_after_window(self):
        """The restart counter should reset when outside the time window."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._restart_count = _MAX_RESTARTS
        # Set the window start to well beyond the window
        runtime._restart_window_start = time.monotonic() - _RESTART_WINDOW - 1.0

        with patch.object(runtime, "_reconnect_telegram"):
            runtime._attempt_recovery()

        # Counter should have been reset and then incremented to 1
        assert runtime._restart_count == 1

        runtime.stop()

    def test_max_restarts_is_3(self):
        """The maximum restart count should be 3."""
        assert _MAX_RESTARTS == 3

    def test_restart_window_is_5_seconds(self):
        """The restart window should be 5 seconds."""
        assert _RESTART_WINDOW == 5.0

    def test_max_restarts_within_window_emits_fatal(self):
        """Exceeding _MAX_RESTARTS within window should emit fatal toast."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._restart_count = _MAX_RESTARTS
        runtime._restart_window_start = time.monotonic()

        mock_bus = MagicMock()
        import telegrab.infra.events as events_mod
        original_bus = events_mod.bus
        events_mod.bus = mock_bus
        try:
            runtime._attempt_recovery()
        finally:
            events_mod.bus = original_bus

        # Should have emitted a fatal toast (not attempted restart)
        mock_bus.emit.assert_called_once()
        payload = mock_bus.emit.call_args[0][1]
        assert payload["type"] == "fatal"

    def test_reconnect_telegram_skips_without_credentials(self):
        """If no Telegram credentials stored, reconnect should skip."""
        runtime = AsyncRuntime()
        runtime.start()

        from telegrab.telegram.client import _state

        # Save original state
        orig_api_id = _state.api_id
        orig_api_hash = _state.api_hash
        orig_client = _state.client

        try:
            _state.api_id = None
            _state.api_hash = None
            _state.client = None

            # Should not raise, just skip
            runtime._reconnect_telegram()
        finally:
            _state.api_id = orig_api_id
            _state.api_hash = orig_api_hash
            _state.client = orig_client

        runtime.stop()

    def test_reconnect_telegram_attempts_ensure_client(self):
        """If credentials exist, reconnect should attempt to call ensure_client."""
        runtime = AsyncRuntime()
        runtime.start()

        from telegrab.telegram.client import _state

        # Save original state
        orig_api_id = _state.api_id
        orig_api_hash = _state.api_hash
        orig_client = _state.client

        try:
            _state.api_id = 12345
            _state.api_hash = "test_hash"
            _state.client = None

            async def fake_ensure(*args, **kwargs):
                return MagicMock()

            with patch("telegrab.telegram.client.ensure_client", side_effect=fake_ensure) as mock_ensure:
                runtime._reconnect_telegram()
                # ensure_client should have been called
                mock_ensure.assert_called_once_with(12345, "test_hash")
        finally:
            _state.api_id = orig_api_id
            _state.api_hash = orig_api_hash
            _state.client = orig_client

        runtime.stop()

    def test_reconnect_telegram_handles_failure_gracefully(self):
        """If reconnect fails, it should log but not crash."""
        runtime = AsyncRuntime()
        runtime.start()

        from telegrab.telegram.client import _state

        orig_api_id = _state.api_id
        orig_api_hash = _state.api_hash
        orig_client = _state.client

        try:
            _state.api_id = 12345
            _state.api_hash = "test_hash"
            _state.client = None

            async def failing_ensure(*args, **kwargs):
                raise ConnectionError("test failure")

            with patch("telegrab.telegram.client.ensure_client", side_effect=failing_ensure):
                # Should not raise
                runtime._reconnect_telegram()
        finally:
            _state.api_id = orig_api_id
            _state.api_hash = orig_api_hash
            _state.client = orig_client

        runtime.stop()

    def test_run_coro_works_after_recovery(self):
        """After recovery, run_coro should work on the new loop."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._loop = None
        runtime._thread = None
        runtime._ready.clear()

        with patch.object(runtime, "_reconnect_telegram"):
            runtime._attempt_recovery()

        # The runtime should be functional again
        async def simple_coro():
            return 42

        result = runtime.run_coro(simple_coro(), timeout=5.0)
        assert result == 42

        runtime.stop()

    def test_recovery_increments_restart_count(self):
        """Each recovery attempt should increment the restart count."""
        runtime = AsyncRuntime()
        runtime._stopping = False
        runtime._loop = None
        runtime._thread = None
        runtime._ready.clear()
        runtime._restart_count = 0
        runtime._restart_window_start = time.monotonic()

        with patch.object(runtime, "_reconnect_telegram"):
            runtime._attempt_recovery()

        assert runtime._restart_count == 1

        runtime.stop()
