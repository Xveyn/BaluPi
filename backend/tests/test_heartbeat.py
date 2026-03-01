"""Tests for heartbeat service — polling, failure counting, dual detection."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.services.heartbeat_service import HeartbeatService
from app.services.nas_state_machine import NasState, NasStateMachine


@pytest.fixture
def state_machine(tmp_path):
    return NasStateMachine(state_dir=str(tmp_path))


@pytest.fixture
def mock_tapo():
    tapo = MagicMock()
    tapo.get_current_readings.return_value = {}
    tapo.get_device_info.return_value = None
    return tapo


@pytest.fixture
def mock_dns():
    dns = MagicMock()
    dns.switch_baluhost_dns = AsyncMock(return_value=True)
    return dns


@pytest.fixture
def heartbeat(state_machine, mock_tapo, mock_dns):
    return HeartbeatService(
        state_machine=state_machine,
        tapo_service=mock_tapo,
        dns_client=mock_dns,
    )


class TestPolling:
    @pytest.mark.asyncio
    @patch("app.services.heartbeat_service.settings")
    async def test_poll_dev_mode_returns_true(self, mock_settings, heartbeat):
        mock_settings.is_dev_mode = True
        assert await heartbeat.poll_nas_health() is True

    @pytest.mark.asyncio
    @patch("app.services.heartbeat_service.settings")
    @patch("app.services.heartbeat_service.httpx.AsyncClient")
    async def test_poll_success(self, mock_client_cls, mock_settings, heartbeat):
        mock_settings.is_dev_mode = False
        mock_settings.nas_url = "http://nas"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client_cls.return_value = mock_client

        assert await heartbeat.poll_nas_health() is True


class TestDetection:
    @pytest.mark.asyncio
    async def test_http_ok_transitions_online(self, heartbeat, state_machine, mock_dns):
        state_machine.transition(NasState.OFFLINE)
        await heartbeat._handle_detection(http_ok=True)
        assert state_machine.state == NasState.ONLINE
        mock_dns.switch_baluhost_dns.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_failure_does_not_transition(self, heartbeat, state_machine):
        state_machine.transition(NasState.ONLINE)
        await heartbeat._handle_detection(http_ok=False)
        assert state_machine.state == NasState.ONLINE  # Not enough failures

    @pytest.mark.asyncio
    async def test_three_failures_transitions_offline(self, heartbeat, state_machine, mock_dns):
        state_machine.transition(NasState.ONLINE)
        for _ in range(3):
            await heartbeat._handle_detection(http_ok=False)
        assert state_machine.state == NasState.OFFLINE
        mock_dns.switch_baluhost_dns.assert_called()

    @pytest.mark.asyncio
    async def test_http_ok_resets_failure_count(self, heartbeat, state_machine):
        state_machine.transition(NasState.ONLINE)
        heartbeat._consecutive_failures = 2
        await heartbeat._handle_detection(http_ok=True)
        assert heartbeat._consecutive_failures == 0


class TestFastPoll:
    def test_set_fast_poll(self, heartbeat):
        heartbeat.set_fast_poll()
        assert heartbeat._fast_poll is True

    def test_set_normal_poll(self, heartbeat):
        heartbeat.set_fast_poll()
        heartbeat.set_normal_poll()
        assert heartbeat._fast_poll is False
