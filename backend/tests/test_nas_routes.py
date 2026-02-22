"""Tests for NAS WOL route."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_wol_no_mac_configured(client: AsyncClient):
    """WOL should fail gracefully when no MAC is configured."""
    with patch("app.api.routes.nas.settings") as mock_settings:
        mock_settings.nas_mac_address = ""
        resp = await client.post("/api/nas/wol")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not configured" in data["error"]


@pytest.mark.asyncio
async def test_wol_success(client: AsyncClient):
    """WOL should send packet and return success."""
    with (
        patch("app.api.routes.nas.settings") as mock_settings,
        patch("app.api.routes.nas.send_wol") as mock_wol,
    ):
        mock_settings.nas_mac_address = "AA:BB:CC:DD:EE:FF"
        resp = await client.post("/api/nas/wol")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["mac"] == "AA:BB:CC:DD:EE:FF"
    mock_wol.assert_called_once_with("AA:BB:CC:DD:EE:FF")


@pytest.mark.asyncio
async def test_wol_invalid_mac(client: AsyncClient):
    """WOL should handle invalid MAC address."""
    with (
        patch("app.api.routes.nas.settings") as mock_settings,
        patch("app.api.routes.nas.send_wol", side_effect=ValueError("bad mac")),
    ):
        mock_settings.nas_mac_address = "INVALID"
        resp = await client.post("/api/nas/wol")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Invalid MAC" in data["error"]
