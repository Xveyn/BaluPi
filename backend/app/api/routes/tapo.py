"""Tapo smart plug management routes — P1 feature."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.tapo import TapoDeviceOut, TapoDeviceUpdate, TapoDiscoverResult, TapoToggleResult
from app.services import get_tapo_service

router = APIRouter()


@router.get("/devices", response_model=list[TapoDeviceOut])
async def list_tapo_devices(db: AsyncSession = Depends(get_db)):
    """List all known Tapo devices."""
    tapo = get_tapo_service()
    return await tapo.get_all_devices(db)


@router.post("/devices/discover", response_model=TapoDiscoverResult)
async def discover_tapo_devices(db: AsyncSession = Depends(get_db)):
    """Scan network for Tapo smart plugs."""
    tapo = get_tapo_service()
    return await tapo.discover_devices(db)


@router.put("/devices/{device_id}", response_model=TapoDeviceOut)
async def update_tapo_device(
    device_id: str,
    body: TapoDeviceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update Tapo device configuration (name, role)."""
    tapo = get_tapo_service()
    result = await tapo.update_device(db, device_id, body.name, body.role)
    if result is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return result


@router.post("/devices/{device_id}/toggle", response_model=TapoToggleResult)
async def toggle_tapo_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle Tapo device on/off."""
    tapo = get_tapo_service()
    try:
        return await tapo.toggle_device(db, device_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
