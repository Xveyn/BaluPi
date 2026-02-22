"""Tests for NasDetectionService — power threshold classification."""

from collections import deque
from datetime import datetime, timezone

import pytest

from app.services.nas_detection_service import NasDetectionService, _classify_power
from app.services.tapo_service import EnergyReading, TapoService


@pytest.fixture
def tapo_service():
    return TapoService()


@pytest.fixture
def nas_service(tapo_service):
    return NasDetectionService(tapo_service)


def test_classify_off():
    state, conf = _classify_power(0.5)
    assert state == "off"
    assert conf > 0.9


def test_classify_standby():
    state, conf = _classify_power(8.0)
    assert state == "standby"
    assert conf > 0.8


def test_classify_idle():
    state, conf = _classify_power(45.0)
    assert state == "idle"
    assert conf > 0.7


def test_classify_active():
    state, conf = _classify_power(120.0)
    assert state == "active"
    assert conf > 0.8


def test_classify_very_high():
    state, conf = _classify_power(300.0)
    assert state == "active"
    assert conf > 0.5


def test_detect_no_nas_device(nas_service):
    """No device with role='nas' → unknown."""
    result = nas_service.detect_state()
    assert result.state == "unknown"
    assert result.power_w == 0.0
    assert result.confidence == 0.0


def test_detect_nas_off(nas_service, tapo_service):
    """NAS device reading below 2W → off."""
    tapo_service._device_map["nas-1"] = {"ip": "10.0.0.1", "name": "NAS", "role": "nas"}
    tapo_service._buffers["nas-1"] = deque([
        EnergyReading(device_id="nas-1", power_mw=1200, timestamp=datetime.now(timezone.utc)),
    ], maxlen=120)

    result = nas_service.detect_state()
    assert result.state == "off"
    assert result.power_w == 1.2


def test_detect_nas_active(nas_service, tapo_service):
    """NAS device reading 80W → active."""
    tapo_service._device_map["nas-2"] = {"ip": "10.0.0.2", "name": "NAS", "role": "nas"}
    tapo_service._buffers["nas-2"] = deque([
        EnergyReading(device_id="nas-2", power_mw=80000, timestamp=datetime.now(timezone.utc)),
    ], maxlen=120)

    result = nas_service.detect_state()
    assert result.state == "active"
    assert result.power_w == 80.0


def test_detect_nas_no_reading(nas_service, tapo_service):
    """NAS device exists but no reading → unknown with 0.5 confidence."""
    tapo_service._device_map["nas-3"] = {"ip": "10.0.0.3", "name": "NAS", "role": "nas"}
    tapo_service._buffers["nas-3"] = deque(maxlen=120)

    result = nas_service.detect_state()
    assert result.state == "unknown"
    assert result.confidence == 0.5
