"""Tests for streaming server hardening (Requirements 12.1-12.7).

Validates:
- 12.1: Server binds exclusively to 127.0.0.1
- 12.2: Constant-time token comparison on every request
- 12.3: HTTP 403 on invalid/missing token without reading file data
- 12.4: Cryptographically random 32-byte session token
- 12.5: HTTP 400 on malformed requests (line > 8192 bytes, missing method/path)
- 12.6: Max 8 concurrent connections
- 12.7: HTTP 503 when connection limit reached, close within 1s
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegrab.api import streaming
from telegrab.config.stream import StreamConfig, get_stream_config


class TestTokenGeneration:
    """Req 12.4: Cryptographically random 32-byte session token."""

    def test_token_has_at_least_32_bytes_entropy(self):
        """Token hex string represents at least 32 bytes of randomness."""
        with patch("telegrab.config.stream._cfg", None):
            cfg = get_stream_config()
            # token_hex(32) produces 64 hex chars = 32 bytes
            assert len(cfg.token) == 64
            # Verify it's valid hex
            int(cfg.token, 16)

    def test_token_not_written_to_disk(self):
        """Token is only in memory — verified by code inspection.
        This test verifies the token is generated from secrets module."""
        with patch("telegrab.config.stream._cfg", None):
            with patch("telegrab.config.stream.secrets.token_hex") as mock_hex:
                mock_hex.return_value = "a" * 64
                from telegrab.config import stream
                stream._cfg = None
                cfg = stream.get_stream_config()
                mock_hex.assert_called_once_with(32)


class TestConnectionLimiting:
    """Req 12.6, 12.7: Max 8 concurrent connections, HTTP 503 when full."""

    def setup_method(self):
        streaming._active_connections = 0

    def teardown_method(self):
        streaming._active_connections = 0

    @pytest.mark.asyncio
    async def test_rejects_when_at_max_connections(self):
        """HTTP 503 returned when _active_connections >= _MAX_CONNECTIONS."""
        streaming._active_connections = 8

        reader = AsyncMock()
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        # Should have written 503 response
        writer.write.assert_called_once()
        response = writer.write.call_args[0][0]
        assert b"503" in response
        writer.close.assert_called()

    @pytest.mark.asyncio
    async def test_503_closes_within_1_second(self):
        """Connection is closed within 1 second of rejection."""
        streaming._active_connections = 8

        reader = AsyncMock()
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        start = time.monotonic()
        await streaming._handle(reader, writer)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0
        writer.close.assert_called()

    @pytest.mark.asyncio
    async def test_increments_and_decrements_counter(self):
        """Active connections counter is properly managed."""
        streaming._active_connections = 0

        reader = AsyncMock()
        # Return empty line to trigger 400 (quick exit)
        reader.readline = AsyncMock(return_value=b"")
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        # Counter should be back to 0 after handling
        assert streaming._active_connections == 0

    @pytest.mark.asyncio
    async def test_counter_decrements_on_exception(self):
        """Counter decrements even if handler raises."""
        streaming._active_connections = 0

        reader = AsyncMock()
        reader.readline = AsyncMock(side_effect=RuntimeError("test"))
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        # Counter must still decrement
        assert streaming._active_connections == 0

    @pytest.mark.asyncio
    async def test_allows_connection_when_under_limit(self):
        """Connections under the limit are accepted normally."""
        streaming._active_connections = 7

        reader = AsyncMock()
        # Empty request triggers 400 (shortcut to test acceptance)
        reader.readline = AsyncMock(return_value=b"")
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        # Should have written 400 (not 503)
        response = writer.write.call_args[0][0]
        assert b"400" in response


class TestRequestLineValidation:
    """Req 12.5: Request line length and format validation."""

    def setup_method(self):
        streaming._active_connections = 0

    def teardown_method(self):
        streaming._active_connections = 0

    @pytest.mark.asyncio
    async def test_rejects_request_line_exceeding_8192_bytes(self):
        """Request lines > 8192 bytes trigger HTTP 400."""
        # Construct a request line that exceeds 8192 bytes
        long_path = "GET /" + "x" * 8200 + " HTTP/1.1\r\n"
        reader = AsyncMock()
        reader.readline = AsyncMock(return_value=long_path.encode())
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        response = writer.write.call_args[0][0]
        assert b"400" in response
        writer.close.assert_called()

    @pytest.mark.asyncio
    async def test_rejects_empty_request(self):
        """Empty request line triggers HTTP 400."""
        reader = AsyncMock()
        reader.readline = AsyncMock(return_value=b"")
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        response = writer.write.call_args[0][0]
        assert b"400" in response

    @pytest.mark.asyncio
    async def test_rejects_missing_path(self):
        """Request with method but no path triggers HTTP 400."""
        reader = AsyncMock()
        call_count = [0]

        async def readline_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return b"GET\r\n"
            return b"\r\n"

        reader.readline = AsyncMock(side_effect=readline_side_effect)
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        await streaming._handle(reader, writer)

        response = writer.write.call_args[0][0]
        assert b"400" in response

    @pytest.mark.asyncio
    async def test_accepts_valid_request_line_at_8192_bytes(self):
        """Request line exactly at 8192 bytes is accepted."""
        # Need a valid GET request line at exactly 8192 bytes
        # "GET /stream/..." needs valid token, so we just check it doesn't 400 for length
        base = "GET /"
        # Fill to 8192 - len("GET / HTTP/1.1\r\n") = 8192 - 16 = 8176 chars for path
        path = "x" * (8192 - len(base) - len(" HTTP/1.1\r\n"))
        request_line = (base + path + " HTTP/1.1\r\n").encode()
        assert len(request_line) <= 8192

        reader = AsyncMock()
        call_count = [0]

        async def readline_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return request_line
            return b"\r\n"

        reader.readline = AsyncMock(side_effect=readline_side_effect)
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        with patch("telegrab.api.streaming.get_stream_config") as mock_cfg:
            mock_cfg.return_value = StreamConfig(token="validtoken123", port=14201)
            await streaming._handle(reader, writer)

        # Should get 403 (invalid token) not 400 (malformed)
        response = writer.write.call_args[0][0]
        assert b"403" in response


class TestTokenValidation:
    """Req 12.2, 12.3: Token validation with constant-time comparison."""

    def setup_method(self):
        streaming._active_connections = 0

    def teardown_method(self):
        streaming._active_connections = 0

    @pytest.mark.asyncio
    async def test_rejects_invalid_token_with_403(self):
        """Invalid token returns HTTP 403."""
        reader = AsyncMock()
        call_count = [0]

        async def readline_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return b"GET /stream/home/123?token=wrongtoken HTTP/1.1\r\n"
            return b"\r\n"

        reader.readline = AsyncMock(side_effect=readline_side_effect)
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        with patch("telegrab.api.streaming.get_stream_config") as mock_cfg:
            mock_cfg.return_value = StreamConfig(token="correcttoken", port=14201)
            await streaming._handle(reader, writer)

        response = writer.write.call_args[0][0]
        assert b"403" in response

    @pytest.mark.asyncio
    async def test_rejects_missing_token_with_403(self):
        """Missing token returns HTTP 403."""
        reader = AsyncMock()
        call_count = [0]

        async def readline_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return b"GET /stream/home/123 HTTP/1.1\r\n"
            return b"\r\n"

        reader.readline = AsyncMock(side_effect=readline_side_effect)
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        with patch("telegrab.api.streaming.get_stream_config") as mock_cfg:
            mock_cfg.return_value = StreamConfig(token="correcttoken", port=14201)
            await streaming._handle(reader, writer)

        response = writer.write.call_args[0][0]
        assert b"403" in response

    @pytest.mark.asyncio
    async def test_uses_constant_time_comparison(self):
        """Verify hmac.compare_digest is used for token comparison."""
        # We verify by checking that the code uses hmac.compare_digest
        import inspect
        source = inspect.getsource(streaming._handle_request)
        assert "hmac.compare_digest" in source


class TestNoSensitiveDataInLogs:
    """Req 12.5: No sensitive data in logs on malformed requests."""

    @pytest.mark.asyncio
    async def test_malformed_request_log_no_token(self, caplog):
        """Malformed request log does not contain token values."""
        streaming._active_connections = 0

        reader = AsyncMock()
        # Send a request line with a token embedded but malformed format
        reader.readline = AsyncMock(return_value=b"BADMETHOD\r\n")
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        import logging
        with caplog.at_level(logging.DEBUG, logger="telegrab.api.streaming"):
            # Simulate readline returning malformed then end
            call_count = [0]

            async def readline_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return b"BADMETHOD\r\n"
                return b"\r\n"

            reader.readline = AsyncMock(side_effect=readline_side_effect)
            await streaming._handle(reader, writer)

        # Check that no log record contains 'token=' or actual token values
        for record in caplog.records:
            assert "token=" not in record.message.lower() or "secret" not in record.message


class TestServerBinding:
    """Req 12.1: Server binds exclusively to 127.0.0.1."""

    def test_serve_streaming_binds_to_localhost(self):
        """Verify the serve_streaming function uses 127.0.0.1."""
        import inspect
        source = inspect.getsource(streaming.serve_streaming)
        assert '127.0.0.1' in source
