"""Tests for handshake endpoints — HMAC verification, snapshot, inbox."""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.routes.handshake import verify_hmac_signature
from app.main import create_app


def _sign_request(
    method: str,
    path: str,
    body: dict,
    secret: str = "test-secret-32-chars-long-enough!",
) -> tuple[str, str]:
    """Generate valid HMAC signature + timestamp for testing."""
    timestamp = str(int(time.time()))
    body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    message = f"{method}:{path}:{timestamp}:{body_hash}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return timestamp, signature


class TestHmacVerification:
    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_missing_secret_returns_500(self, mock_settings):
        from fastapi import Request
        from unittest.mock import MagicMock

        mock_settings.handshake_secret = ""

        request = MagicMock(spec=Request)
        request.headers = {"X-Balupi-Timestamp": "123", "X-Balupi-Signature": "abc"}

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_hmac_signature(request)
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_missing_headers_returns_401(self, mock_settings):
        from fastapi import Request
        from unittest.mock import MagicMock

        mock_settings.handshake_secret = "test-secret"
        request = MagicMock(spec=Request)
        request.headers = {}

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_hmac_signature(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_expired_timestamp_returns_401(self, mock_settings):
        from fastapi import Request
        from unittest.mock import MagicMock

        mock_settings.handshake_secret = "test-secret"
        request = MagicMock(spec=Request)
        request.headers = {
            "X-Balupi-Timestamp": str(int(time.time()) - 120),
            "X-Balupi-Signature": "abc",
        }

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_hmac_signature(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_wrong_signature_returns_401(self, mock_settings):
        from fastapi import Request
        from unittest.mock import MagicMock

        mock_settings.handshake_secret = "test-secret"
        request = MagicMock(spec=Request)
        request.headers = {
            "X-Balupi-Timestamp": str(int(time.time())),
            "X-Balupi-Signature": "wrong-signature",
        }
        request.body = AsyncMock(return_value=b'{"test": true}')
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/handshake/test"

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await verify_hmac_signature(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_valid_signature_passes(self, mock_settings):
        from fastapi import Request
        from unittest.mock import MagicMock

        secret = "test-secret-32-chars-long-enough!"
        mock_settings.handshake_secret = secret

        body = {"action": "shutdown"}
        body_bytes = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        method = "POST"
        path = "/api/handshake/nas-going-offline"

        timestamp, signature = _sign_request(method, path, body, secret)

        request = MagicMock(spec=Request)
        request.headers = {
            "X-Balupi-Timestamp": timestamp,
            "X-Balupi-Signature": signature,
        }
        request.body = AsyncMock(return_value=body_bytes)
        request.method = method
        request.url = MagicMock()
        request.url.path = path

        # Should not raise
        await verify_hmac_signature(request)


class TestInboxFlush:
    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_dev_mode_returns_zero(self, mock_settings):
        from app.api.routes.handshake import _flush_inbox

        mock_settings.is_dev_mode = True
        result = await _flush_inbox()
        assert result == 0

    @pytest.mark.asyncio
    @patch("app.api.routes.handshake.settings")
    async def test_empty_inbox_returns_zero(self, mock_settings, tmp_path):
        from app.api.routes.handshake import _flush_inbox, INBOX_DIR

        mock_settings.is_dev_mode = False
        # INBOX_DIR doesn't exist in test environment
        with patch("app.api.routes.handshake.INBOX_DIR", tmp_path):
            result = await _flush_inbox()
            assert result == 0
