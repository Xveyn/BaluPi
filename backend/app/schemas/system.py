"""System status schemas."""

from pydantic import BaseModel


class SystemStatus(BaseModel):
    """Pi system resource status."""
    cpu_percent: float
    cpu_temp_celsius: float | None = None
    memory_total_mb: float
    memory_used_mb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    uptime_seconds: float
    load_avg: list[float] = []


class HealthResponse(BaseModel):
    """Health check response — compatible with BaluHost."""
    status: str = "ok"
    version: str
    service: str = "balupi"
    cache_enabled: bool = True
    energy_enabled: bool = True
