"""Energy monitoring API routes — P1 feature."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.energy import EnergyCurrentAll, EnergySummary, PriceConfigCreate, PriceConfigOut
from app.services import get_energy_service, get_nas_detection_service, get_tapo_service

router = APIRouter()


@router.get("/current", response_model=EnergyCurrentAll)
async def energy_current(db: AsyncSession = Depends(get_db)):
    """Current power readings from all Tapo devices."""
    energy = get_energy_service()
    tapo = get_tapo_service()
    return await energy.get_current_all(db, tapo)


@router.get("/history")
async def energy_history(
    device_id: str | None = None,
    period: str = "day",
    db: AsyncSession = Depends(get_db),
):
    """Historical energy data (day/week/month)."""
    energy = get_energy_service()
    data = await energy.get_history(db, device_id, period)

    # Get device name for response
    device_name = "all"
    if device_id:
        tapo = get_tapo_service()
        info = tapo.get_device_info(device_id)
        device_name = info["name"] if info else device_id

    return {
        "device_id": device_id or "all",
        "device_name": device_name,
        "period": period,
        "data": data,
    }


@router.get("/costs")
async def energy_costs(
    device_id: str | None = None,
    period: str = "month",
    db: AsyncSession = Depends(get_db),
):
    """Energy cost calculations."""
    energy = get_energy_service()
    return await energy.calculate_cost(db, device_id, period)


@router.get("/summary", response_model=EnergySummary)
async def energy_summary(db: AsyncSession = Depends(get_db)):
    """Overall energy summary."""
    energy = get_energy_service()
    tapo = get_tapo_service()
    nas_detection = get_nas_detection_service()

    nas_state = nas_detection.detect_state()
    return await energy.get_summary(db, tapo, nas_state.state)


@router.get("/prices", response_model=list[PriceConfigOut])
async def list_prices(db: AsyncSession = Depends(get_db)):
    """List all electricity price configurations."""
    energy = get_energy_service()
    return await energy.get_prices(db)


@router.post("/prices", response_model=PriceConfigOut, status_code=201)
async def create_price(body: PriceConfigCreate, db: AsyncSession = Depends(get_db)):
    """Create a new electricity price configuration."""
    energy = get_energy_service()
    return await energy.create_price(db, body.model_dump())
