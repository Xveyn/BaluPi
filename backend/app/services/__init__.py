"""Business logic services — singleton registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.services.energy_service import EnergyService
    from app.services.nas_detection_service import NasDetectionService
    from app.services.scheduler import EnergyScheduler
    from app.services.tapo_service import TapoService

logger = logging.getLogger(__name__)

_tapo_service: TapoService | None = None
_energy_service: EnergyService | None = None
_nas_detection_service: NasDetectionService | None = None
_scheduler: EnergyScheduler | None = None


async def init_services(db_session) -> None:
    """Create and wire up all service singletons."""
    global _tapo_service, _energy_service, _nas_detection_service, _scheduler

    from app.services.energy_service import EnergyService
    from app.services.nas_detection_service import NasDetectionService
    from app.services.scheduler import EnergyScheduler
    from app.services.tapo_service import TapoService

    _tapo_service = TapoService(
        username=settings.tapo_username,
        password=settings.tapo_password,
    )
    _energy_service = EnergyService()
    _nas_detection_service = NasDetectionService(_tapo_service)

    # Initialize device cache from DB
    await _tapo_service.initialize(db_session)

    # Start scheduler only if Tapo credentials are configured
    if settings.tapo_username:
        _scheduler = EnergyScheduler(_tapo_service, _energy_service)
        _scheduler.start()
        logger.info("Energy services initialized with scheduler")
    else:
        logger.warning(
            "Tapo credentials not configured (BALUPI_TAPO_USERNAME) — "
            "energy scheduler disabled"
        )


async def shutdown_services() -> None:
    """Stop scheduler and cleanup."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None


def get_tapo_service() -> TapoService:
    if _tapo_service is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _tapo_service


def get_energy_service() -> EnergyService:
    if _energy_service is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _energy_service


def get_nas_detection_service() -> NasDetectionService:
    if _nas_detection_service is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _nas_detection_service
