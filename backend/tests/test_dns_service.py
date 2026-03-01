"""Tests for DNS service — Pi-hole v6 API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dns_service import PiholeClient


@pytest.fixture
def client():
    return PiholeClient(base_url="http://pihole", password="testpass")


class TestAuth:
    @pytest.mark.asyncio
    @patch("app.services.dns_service.httpx.AsyncClient")
    async def test_auth_stores_sid(self, mock_client_cls, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"session": {"sid": "test-sid-123"}}
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_resp)
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock()
        mock_client_cls.return_value = mock_http

        sid = await client._auth()
        assert sid == "test-sid-123"
        assert client._sid == "test-sid-123"


class TestDnsOperations:
    @pytest.mark.asyncio
    @patch("app.services.dns_service.settings")
    async def test_switch_dev_mode_skips_api(self, mock_settings, client):
        mock_settings.is_dev_mode = True

        result = await client.switch_baluhost_dns("192.168.1.100")
        assert result is True

    @pytest.mark.asyncio
    @patch("app.services.dns_service.settings")
    async def test_switch_error_returns_false(self, mock_settings, client):
        mock_settings.is_dev_mode = False
        mock_settings.nas_ip = "192.168.1.1"
        mock_settings.pi_ip = "192.168.1.2"

        client.remove_dns_host = AsyncMock(side_effect=Exception("API down"))
        client.set_dns_host = AsyncMock(side_effect=Exception("API down"))

        result = await client.switch_baluhost_dns("192.168.1.100")
        assert result is False
