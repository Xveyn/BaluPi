"""NAS management routes — status, WOL with state machine integration."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.config import settings
from app.services import get_heartbeat_service, get_state_machine, get_tapo_service
from app.services.nas_state_machine import NasState
from app.utils.wol import send_wol

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def nas_status():
    """Check NAS state from state machine + live health check."""
    sm = get_state_machine()

    # Also do a live check
    online = False
    version = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.nas_url}/api/health")
        if resp.status_code == 200:
            data = resp.json()
            online = True
            version = data.get("version")
    except httpx.HTTPError:
        pass

    return {
        "online": online,
        "version": version,
        "url": settings.nas_url,
        "nas_state": sm.state.value,
        "since": sm.since.isoformat(),
    }


@router.post("/wol")
async def wake_on_lan(current_user=Depends(get_current_user)):
    """Send Wake-on-LAN packet to NAS with state machine integration."""
    sm = get_state_machine()

    if not settings.nas_mac_address:
        raise HTTPException(400, "NAS MAC address not configured")

    # Check if NAS is already online
    if sm.state == NasState.ONLINE:
        raise HTTPException(400, "NAS is already online")

    if sm.state == NasState.BOOTING:
        raise HTTPException(400, "NAS is already booting")

    # Check Tapo power reading
    try:
        tapo = get_tapo_service()
        readings = tapo.get_current_readings()
        power = None
        for device_id, reading in readings.items():
            info = tapo.get_device_info(device_id)
            if info and info.get("role") == "nas" and reading:
                power = reading.power_mw / 1000.0
                break

        if power is not None:
            if power > settings.nas_power_threshold_watts:
                raise HTTPException(400, "NAS appears to be already running (power: {:.1f}W)".format(power))
            if power < 2:
                raise HTTPException(
                    400,
                    "NAS has no power (plug off?). Turn on the smart plug first.",
                )
    except RuntimeError:
        pass  # Tapo service not initialized

    previous_state = sm.state.value

    # Send WoL
    if settings.is_dev_mode:
        logger.info("[DEV] WoL packet (not sent): %s", settings.nas_mac_address)
    else:
        try:
            send_wol(settings.nas_mac_address)
        except (ValueError, OSError) as e:
            raise HTTPException(500, f"Failed to send WoL packet: {e}")

    # Transition state
    sm.transition(NasState.BOOTING)

    # Switch heartbeat to fast polling
    try:
        heartbeat = get_heartbeat_service()
        heartbeat.set_fast_poll()
    except RuntimeError:
        pass

    return {
        "wol_sent": True,
        "nas_previous_state": previous_state,
        "estimated_boot_time_s": 60,
    }
