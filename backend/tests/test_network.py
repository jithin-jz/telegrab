"""Unit tests for ExponentialBackoff in telegrab.services.network."""

import sys
from unittest.mock import MagicMock

# Mock webview module before importing telegrab packages
if "webview" not in sys.modules:
    sys.modules["webview"] = MagicMock()

from telegrab.services.network import ExponentialBackoff


class TestExponentialBackoff:
    """Tests for the ExponentialBackoff retry delay calculator."""

    def test_default_parameters(self):
        backoff = ExponentialBackoff()
        assert backoff.base_delay == 1.0
        assert backoff.max_delay == 30.0
        assert backoff.max_attempts == 10

    def test_first_attempt_returns_base_delay(self):
        backoff = ExponentialBackoff()
        assert backoff.next_delay(0) == 1.0

    def test_second_attempt_doubles(self):
        backoff = ExponentialBackoff()
        assert backoff.next_delay(1) == 2.0

    def test_delays_follow_formula(self):
        backoff = ExponentialBackoff()
        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0, 30.0, 30.0]
        for attempt, expected_delay in enumerate(expected):
            assert backoff.next_delay(attempt) == expected_delay

    def test_delay_capped_at_max(self):
        backoff = ExponentialBackoff()
        # 2^5 = 32 > 30, so attempt 5 onward should be capped at 30
        assert backoff.next_delay(5) == 30.0
        assert backoff.next_delay(9) == 30.0

    def test_custom_parameters(self):
        backoff = ExponentialBackoff(base_delay=0.5, max_delay=10.0, max_attempts=5)
        assert backoff.base_delay == 0.5
        assert backoff.max_delay == 10.0
        assert backoff.max_attempts == 5
        # 0.5 * 2^3 = 4.0
        assert backoff.next_delay(3) == 4.0
        # 0.5 * 2^5 = 16.0 > 10.0 → capped
        assert backoff.next_delay(5) == 10.0
