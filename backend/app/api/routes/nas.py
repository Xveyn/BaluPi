"""NAS management routes — discovery, WOL, status."""

import logging

import httpx
from fastapi import APIRouter

from app.config import settings
from app.utils.wol import send_wol

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def nas_status():
    """Check if NAS is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.nas_url}/api/health")
        if resp.status_code == 200:
            data = resp.json()
            return {
                "online": True,
                "version": data.get("version"),
                "url": settings.nas_url,
            }
    except httpx.HTTPError:
        pass

    return {"online": False, "url": settings.nas_url}


@router.post("/wol")
async def wake_on_lan():
    """Send Wake-on-LAN packet to NAS."""
    if not settings.nas_mac_address:
        return {"success": False, "error": "NAS MAC address not configured"}

    try:
        send_wol(settings.nas_mac_address)
    except ValueError as e:
        return {"success": False, "error": f"Invalid MAC address: {e}"}
    except OSError as e:
        return {"success": False, "error": f"Failed to send WOL packet: {e}"}

    return {"success": True, "mac": settings.nas_mac_address}
