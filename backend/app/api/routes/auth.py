"""Auth routes — forwards to NAS for validation."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, status

from fastapi.responses import JSONResponse

from app.config import settings
from app.schemas.auth import LoginRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login")
async def login(body: LoginRequest):
    """
    Forward login to NAS.

    BaluPi does not manage users itself — it proxies auth to BaluHost
    and returns the NAS response as-is (including user object).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.nas_url}/api/auth/login",
                json={"username": body.username, "password": body.password},
            )
        if resp.status_code == 200:
            return JSONResponse(content=resp.json())

        detail = "Invalid credentials"
        try:
            detail = resp.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)

    except httpx.HTTPError as exc:
        logger.warning("NAS unreachable for login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NAS is not reachable. Login requires NAS connectivity.",
        )
