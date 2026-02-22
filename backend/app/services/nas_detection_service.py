"""NAS state detection via Tapo smart plug power readings."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.tapo_service import TapoService

logger = logging.getLogger(__name__)

# Power thresholds in watts
THRESHOLD_OFF = 2.0
THRESHOLD_STANDBY = 15.0
THRESHOLD_IDLE = 60.0
THRESHOLD_ACTIVE = 200.0


@dataclass
class NasState:
    state: str  # off, standby, idle, active, unknown
    power_w: float
    confidence: float  # 0.0 - 1.0


class NasDetectionService:
    """Detects NAS power state from Tapo smart plug readings."""

    def __init__(self, tapo_service: TapoService):
        self._tapo_service = tapo_service

    def detect_state(self) -> NasState:
        """Determine NAS state from the device with role='nas'."""
        readings = self._tapo_service.get_current_readings()
        device_map = self._tapo_service._device_map

        # Find device with role="nas"
        nas_device_id = None
        for device_id, info in device_map.items():
            if info.get("role") == "nas":
                nas_device_id = device_id
                break

        if not nas_device_id:
            return NasState(state="unknown", power_w=0.0, confidence=0.0)

        reading = readings.get(nas_device_id)
        if not reading:
            return NasState(state="unknown", power_w=0.0, confidence=0.5)

        power_w = reading.power_mw / 1000.0
        state, confidence = _classify_power(power_w)

        return NasState(state=state, power_w=round(power_w, 2), confidence=confidence)


def _classify_power(power_w: float) -> tuple[str, float]:
    """Classify power consumption into NAS state."""
    if power_w < THRESHOLD_OFF:
        return "off", 0.95
    elif power_w < THRESHOLD_STANDBY:
        return "standby", 0.85
    elif power_w < THRESHOLD_IDLE:
        return "idle", 0.80
    elif power_w < THRESHOLD_ACTIVE:
        return "active", 0.85
    else:
        # Very high power — still active but unusual
        return "active", 0.70
