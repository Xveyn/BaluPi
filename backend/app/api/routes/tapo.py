"""Tapo smart plug management routes — P1 feature."""

from fastapi import APIRouter

from app.schemas.tapo import TapoDeviceOut, TapoDeviceUpdate, TapoDiscoverResult

router = APIRouter()


@router.get("/devices", response_model=list[TapoDeviceOut])
async def list_tapo_devices():
    """List all known Tapo devices."""
    # TODO P1: query tapo_devices table
    return []


@router.post("/devices/discover", response_model=TapoDiscoverResult)
async def discover_tapo_devices():
    """Scan network for Tapo smart plugs."""
    # TODO P1: use python-kasa discovery
    return TapoDiscoverResult(discovered=0, new_devices=0, devices=[])


@router.put("/devices/{device_id}", response_model=TapoDeviceOut)
async def update_tapo_device(device_id: str, body: TapoDeviceUpdate):
    """Update Tapo device configuration (name, role)."""
    # TODO P1: update in DB
    raise NotImplementedError("P1 feature")


@router.post("/devices/{device_id}/toggle")
async def toggle_tapo_device(device_id: str):
    """Toggle Tapo device on/off."""
    # TODO P1: use python-kasa to toggle
    raise NotImplementedError("P1 feature")
