"""Tests for TapoService — with mocked python-kasa."""

from collections import deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.tapo_device import TapoDevice
from app.services.tapo_service import EnergyReading, TapoService


@pytest_asyncio.fixture
async def tapo_service():
    return TapoService(username="test@example.com", password="secret")


@pytest_asyncio.fixture
async def tapo_with_device(db_session, tapo_service):
    """TapoService with one device registered in DB."""
    dev = TapoDevice(
        id="dev-1",
        name="Test Plug",
        ip_address="192.168.1.100",
        model="P110",
        role="generic",
        is_online=1,
    )
    db_session.add(dev)
    await db_session.commit()

    await tapo_service.initialize(db_session)
    return tapo_service


@pytest.mark.asyncio
async def test_initialize_loads_devices(db_session, tapo_service):
    """initialize() loads devices from DB into memory."""
    dev = TapoDevice(
        id="dev-init",
        name="Init Test",
        ip_address="10.0.0.1",
        role="nas",
    )
    db_session.add(dev)
    await db_session.commit()

    await tapo_service.initialize(db_session)

    assert "dev-init" in tapo_service._device_map
    assert tapo_service._device_map["dev-init"]["role"] == "nas"
    assert "dev-init" in tapo_service._buffers


@pytest.mark.asyncio
async def test_poll_all_devices_success(db_session, tapo_with_device):
    """poll_all_devices returns readings when device responds."""
    mock_dev = AsyncMock()
    mock_dev.has_emeter = True
    mock_dev.emeter_realtime = {
        "power_mw": 45000,
        "voltage_mv": 230000,
        "current_ma": 196,
        "total_wh": 1234,
    }
    mock_dev.update = AsyncMock()

    with patch.object(
        tapo_with_device, "_connect_device", return_value=mock_dev
    ):
        readings = await tapo_with_device.poll_all_devices(db_session)

    assert len(readings) == 1
    assert readings[0].device_id == "dev-1"
    assert readings[0].power_mw == 45000
    assert readings[0].voltage_mv == 230000

    # Should be in buffer
    assert len(tapo_with_device._buffers["dev-1"]) == 1


@pytest.mark.asyncio
async def test_poll_device_offline_after_3_failures(db_session, tapo_with_device):
    """Device is marked offline after MAX_FAIL_COUNT consecutive failures."""
    with patch.object(
        tapo_with_device, "_connect_device", return_value=None
    ):
        for _ in range(3):
            await tapo_with_device.poll_all_devices(db_session)

    result = await db_session.execute(
        select(TapoDevice).where(TapoDevice.id == "dev-1")
    )
    dev = result.scalar_one()
    assert dev.is_online == 0


@pytest.mark.asyncio
async def test_flush_buffer_writes_samples(db_session, tapo_with_device):
    """flush_buffer writes buffered readings to DB."""
    from app.models.energy import EnergySample

    # Add readings to buffer manually
    tapo_with_device._buffers["dev-1"] = deque([
        EnergyReading(device_id="dev-1", power_mw=50000, timestamp=datetime.now(timezone.utc)),
        EnergyReading(device_id="dev-1", power_mw=51000, timestamp=datetime.now(timezone.utc)),
    ], maxlen=120)

    count = await tapo_with_device.flush_buffer(db_session)
    assert count == 2

    # Buffer should be empty now
    assert len(tapo_with_device._buffers["dev-1"]) == 0

    # Samples should be in DB
    result = await db_session.execute(select(EnergySample))
    samples = result.scalars().all()
    assert len(samples) == 2
    assert samples[0].power_mw == 50000


@pytest.mark.asyncio
async def test_get_current_readings_empty(tapo_service):
    """get_current_readings returns empty dict when no buffers."""
    readings = tapo_service.get_current_readings()
    assert readings == {}


@pytest.mark.asyncio
async def test_update_device(db_session, tapo_with_device):
    """update_device changes name and role."""
    result = await tapo_with_device.update_device(db_session, "dev-1", "NAS Plug", "nas")
    assert result is not None
    assert result["name"] == "NAS Plug"
    assert result["role"] == "nas"

    # Verify in-memory map updated
    assert tapo_with_device._device_map["dev-1"]["role"] == "nas"


@pytest.mark.asyncio
async def test_update_device_not_found(db_session, tapo_with_device):
    """update_device returns None for unknown device."""
    result = await tapo_with_device.update_device(db_session, "nonexistent", "X", None)
    assert result is None
