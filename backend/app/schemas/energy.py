"""Energy monitoring schemas."""

from datetime import datetime

from pydantic import BaseModel


class EnergyCurrent(BaseModel):
    """Current power reading from a single device."""
    device_id: str
    device_name: str
    power_w: float
    voltage_v: float | None = None
    current_a: float | None = None
    is_online: bool = True
    timestamp: datetime


class EnergyCurrentAll(BaseModel):
    """Current power readings for all devices."""
    devices: list[EnergyCurrent]
    total_power_w: float


class EnergyHistoryPoint(BaseModel):
    """Single point in energy history."""
    timestamp: str
    avg_power_w: float
    max_power_w: float
    min_power_w: float
    energy_wh: float


class EnergyHistory(BaseModel):
    """Historical energy data."""
    device_id: str
    device_name: str
    period: str  # day, week, month
    data: list[EnergyHistoryPoint]


class EnergyCostSummary(BaseModel):
    """Energy cost calculation."""
    device_id: str
    device_name: str
    period: str
    total_kwh: float
    cost_cents: float
    price_per_kwh_cents: float


class EnergySummary(BaseModel):
    """Overall energy summary."""
    total_devices: int
    total_power_w: float
    avg_daily_kwh: float
    monthly_cost_estimate_cents: float
    nas_state: str  # off, standby, idle, active, unknown


class PriceConfigCreate(BaseModel):
    """Create an electricity price configuration."""
    name: str
    price_per_kwh_cents: float
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool = True


class PriceConfigOut(BaseModel):
    """Electricity price configuration response."""
    id: int
    name: str
    price_per_kwh_cents: float
    valid_from: str | None = None
    valid_to: str | None = None
    is_active: bool = True
    created_at: str | None = None
