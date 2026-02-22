"""Energy monitoring API routes — P1 feature."""

from fastapi import APIRouter

from app.schemas.energy import EnergyCurrentAll, EnergySummary

router = APIRouter()


@router.get("/current", response_model=EnergyCurrentAll)
async def energy_current():
    """Current power readings from all Tapo devices."""
    # TODO P1: implement with TapoService
    return EnergyCurrentAll(devices=[], total_power_w=0.0)


@router.get("/history")
async def energy_history(device_id: str | None = None, period: str = "day"):
    """Historical energy data (day/week/month)."""
    # TODO P1: query energy_hourly / energy_daily
    return {"device_id": device_id, "period": period, "data": []}


@router.get("/costs")
async def energy_costs(device_id: str | None = None, period: str = "month"):
    """Energy cost calculations."""
    # TODO P1: calculate from energy_daily + price_config
    return {"device_id": device_id, "period": period, "total_kwh": 0, "cost_cents": 0}


@router.get("/summary", response_model=EnergySummary)
async def energy_summary():
    """Overall energy summary."""
    # TODO P1: aggregate all devices
    return EnergySummary(
        total_devices=0,
        total_power_w=0.0,
        avg_daily_kwh=0.0,
        monthly_cost_estimate_cents=0.0,
        nas_state="unknown",
    )
