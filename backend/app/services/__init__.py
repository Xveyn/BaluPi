"""Business logic services — singleton registry."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.services.dns_service import PiholeClient
    from app.services.energy_service import EnergyService
    from app.services.heartbeat_service import HeartbeatService
    from app.services.nas_detection_service import NasDetectionService
    from app.services.nas_state_machine import NasStateMachine
    from app.services.scheduler import EnergyScheduler
    from app.services.tapo_service import TapoService

logger = logging.getLogger(__name__)

_tapo_service: TapoService | None = None
_energy_service: EnergyService | None = None
_nas_detection_service: NasDetectionService | None = None
_scheduler: EnergyScheduler | None = None
_state_machine: NasStateMachine | None = None
_dns_service: PiholeClient | None = None
_heartbeat_service: HeartbeatService | None = None


async def init_services(db_session) -> None:
    """Create and wire up all service singletons."""
    global _tapo_service, _energy_service, _nas_detection_service, _scheduler
    global _state_machine, _dns_service, _heartbeat_service

    from app.services.dns_service import PiholeClient
    from app.services.energy_service import EnergyService
    from app.services.heartbeat_service import HeartbeatService
    from app.services.nas_detection_service import NasDetectionService
    from app.services.nas_state_machine import NasStateMachine
    from app.services.scheduler import EnergyScheduler
    from app.services.tapo_service import TapoService

    # Phase 1: Energy monitoring
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

    # Phase 2: NAS handshake, heartbeat, DNS
    _state_machine = NasStateMachine()
    _dns_service = PiholeClient()
    _heartbeat_service = HeartbeatService(
        state_machine=_state_machine,
        tapo_service=_tapo_service,
        dns_client=_dns_service,
    )
    _heartbeat_service.start()
    logger.info("Phase 2 services initialized (state machine, heartbeat, DNS)")


async def shutdown_services() -> None:
    """Stop scheduler, heartbeat, and cleanup."""
    global _scheduler, _heartbeat_service
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
    if _heartbeat_service:
        await _heartbeat_service.stop()
        _heartbeat_service = None


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


def get_state_machine() -> NasStateMachine:
    if _state_machine is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _state_machine


def get_dns_service() -> PiholeClient:
    if _dns_service is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _dns_service


def get_heartbeat_service() -> HeartbeatService:
    if _heartbeat_service is None:
        raise RuntimeError("Services not initialized — call init_services() first")
    return _heartbeat_service
