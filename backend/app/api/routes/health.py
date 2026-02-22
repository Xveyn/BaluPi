"""Health check — compatible with BaluHost /api/health."""

from fastapi import APIRouter

from app import __version__
from app.schemas.system import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Lightweight connectivity check — used by BaluApp & BaluDesk."""
    return HealthResponse(version=__version__)


@router.get("/ping")
async def ping():
    """Ultra-lightweight ping."""
    return {"status": "ok"}
