"""Tests for NAS routes (status + WoL with state machine)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.nas_state_machine import NasState, NasStateMachine


def _mock_services(tmp_path):
    """Create mock services for NAS route tests."""
    sm = NasStateMachine(state_dir=str(tmp_path))
    sm.transition(NasState.OFFLINE)

    tapo = MagicMock()
    tapo.get_current_readings.return_value = {}
    tapo.get_device_info.return_value = None

    heartbeat = MagicMock()
    heartbeat.set_fast_poll = MagicMock()

    return sm, tapo, heartbeat


@pytest.mark.asyncio
async def test_nas_status(client: AsyncClient):
    """Status endpoint returns NAS state."""
    with patch("app.api.routes.nas.get_state_machine") as mock_sm:
        sm = MagicMock()
        sm.state = NasState.UNKNOWN
        sm.since = MagicMock()
        sm.since.isoformat.return_value = "2026-01-01T00:00:00"
        mock_sm.return_value = sm

        resp = await client.get("/api/nas/status")

    assert resp.status_code == 200
    data = resp.json()
    assert "online" in data
    assert "nas_state" in data


@pytest.mark.asyncio
async def test_wol_no_mac_configured(client: AsyncClient, tmp_path):
    """WoL should return 400 when no MAC is configured."""
    sm, tapo, heartbeat = _mock_services(tmp_path)

    from app.api.deps import get_current_user

    client._transport.app.dependency_overrides[get_current_user] = lambda: MagicMock()

    with (
        patch("app.api.routes.nas.settings") as mock_settings,
        patch("app.api.routes.nas.get_state_machine", return_value=sm),
    ):
        mock_settings.nas_mac_address = ""
        mock_settings.is_dev_mode = True

        resp = await client.post("/api/nas/wol")

    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wol_success(client: AsyncClient, tmp_path):
    """WoL sends packet and transitions state to BOOTING."""
    sm, tapo, heartbeat = _mock_services(tmp_path)

    from app.api.deps import get_current_user

    client._transport.app.dependency_overrides[get_current_user] = lambda: MagicMock()

    with (
        patch("app.api.routes.nas.settings") as mock_settings,
        patch("app.api.routes.nas.get_state_machine", return_value=sm),
        patch("app.api.routes.nas.get_tapo_service", return_value=tapo),
        patch("app.api.routes.nas.get_heartbeat_service", return_value=heartbeat),
        patch("app.api.routes.nas.send_wol") as mock_wol,
    ):
        mock_settings.nas_mac_address = "AA:BB:CC:DD:EE:FF"
        mock_settings.is_dev_mode = False
        mock_settings.nas_power_threshold_watts = 30.0

        resp = await client.post("/api/nas/wol")

    assert resp.status_code == 200
    data = resp.json()
    assert data["wol_sent"] is True
    assert data["nas_previous_state"] == "offline"
    assert sm.state == NasState.BOOTING
    mock_wol.assert_called_once_with("AA:BB:CC:DD:EE:FF")
    heartbeat.set_fast_poll.assert_called_once()
