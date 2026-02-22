"""System status — Pi hardware monitoring."""

import time

import psutil
from fastapi import APIRouter

from app.schemas.system import SystemStatus

router = APIRouter()

_boot_time = psutil.boot_time()


def _get_cpu_temp() -> float | None:
    """Read CPU temperature (Linux/Pi only)."""
    try:
        temps = getattr(psutil, "sensors_temperatures", None)
        if temps is None:
            return None
        temps = temps()
        if "cpu_thermal" in temps:
            return temps["cpu_thermal"][0].current
        if "coretemp" in temps:
            return temps["coretemp"][0].current
    except (AttributeError, IndexError, KeyError):
        pass
    return None


@router.get("/status", response_model=SystemStatus)
async def system_status():
    """Pi system resources: CPU, RAM, disk, temperature."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    load_avg: list[float] = []
    try:
        load_avg = list(psutil.getloadavg())
    except (AttributeError, OSError):
        pass

    return SystemStatus(
        cpu_percent=psutil.cpu_percent(interval=0.5),
        cpu_temp_celsius=_get_cpu_temp(),
        memory_total_mb=round(mem.total / 1024 / 1024, 1),
        memory_used_mb=round(mem.used / 1024 / 1024, 1),
        memory_percent=mem.percent,
        disk_total_gb=round(disk.total / 1024 / 1024 / 1024, 2),
        disk_used_gb=round(disk.used / 1024 / 1024 / 1024, 2),
        disk_percent=disk.percent,
        uptime_seconds=round(time.time() - _boot_time, 0),
        load_avg=load_avg,
    )
