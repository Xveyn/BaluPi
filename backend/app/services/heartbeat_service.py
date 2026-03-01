"""NAS heartbeat — polls /api/health with dual detection (HTTP + Tapo power)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import httpx

from app.config import settings
from app.services.nas_state_machine import NasState

if TYPE_CHECKING:
    from app.services.dns_service import PiholeClient
    from app.services.nas_state_machine import NasStateMachine
    from app.services.tapo_service import TapoService

logger = logging.getLogger(__name__)


class HeartbeatService:
    """Periodically polls NAS health and updates state machine."""

    POLL_INTERVAL = 30  # seconds, normal mode
    FAST_POLL_INTERVAL = 5  # seconds, after WoL
    FAILURE_THRESHOLD = 3  # consecutive failures = offline
    POLL_TIMEOUT = 5  # seconds per request

    def __init__(
        self,
        state_machine: NasStateMachine,
        tapo_service: TapoService,
        dns_client: PiholeClient,
    ):
        self._sm = state_machine
        self._tapo = tapo_service
        self._dns = dns_client
        self._consecutive_failures = 0
        self._fast_poll = False
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the heartbeat background loop."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Heartbeat service started")

    async def stop(self) -> None:
        """Stop the heartbeat background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat service stopped")

    def set_fast_poll(self) -> None:
        """Switch to fast polling (after WoL)."""
        self._fast_poll = True
        self._consecutive_failures = 0
        logger.info("Heartbeat: fast poll enabled")

    def set_normal_poll(self) -> None:
        """Switch back to normal polling interval."""
        self._fast_poll = False

    async def poll_nas_health(self) -> bool:
        """Check NAS /api/health. Returns True if reachable."""
        if settings.is_dev_mode:
            return True

        try:
            async with httpx.AsyncClient(timeout=self.POLL_TIMEOUT) as client:
                resp = await client.get(f"{settings.nas_url}/api/health")
                return resp.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    def _get_nas_power(self) -> float | None:
        """Get current NAS power reading from Tapo buffer."""
        readings = self._tapo.get_current_readings()
        for device_id, reading in readings.items():
            info = self._tapo.get_device_info(device_id)
            if info and info.get("role") == "nas" and reading:
                return reading.power_mw / 1000.0
        return None

    async def _handle_detection(self, http_ok: bool) -> None:
        """Combine HTTP health + Tapo power for dual NAS detection."""
        power = self._get_nas_power()
        current_state = self._sm.state

        if http_ok:
            self._consecutive_failures = 0
            if current_state != NasState.ONLINE:
                self._sm.transition(NasState.ONLINE)
                await self._dns.switch_baluhost_dns(settings.nas_ip or settings.nas_url.split("//")[-1])
                self.set_normal_poll()
            return

        # HTTP failed
        self._consecutive_failures += 1

        if self._consecutive_failures < self.FAILURE_THRESHOLD:
            return  # Not enough failures yet

        # Dual detection: combine HTTP failure with power reading
        if power is not None:
            if power < 2:
                # Definitely off
                if current_state not in (NasState.OFFLINE,):
                    self._sm.transition(NasState.OFFLINE)
                    await self._dns.switch_baluhost_dns(settings.pi_ip)
                    self.set_normal_poll()
            elif power < 15:
                # Standby/sleep — treat as offline for DNS purposes
                if current_state not in (NasState.OFFLINE,):
                    self._sm.transition(NasState.OFFLINE)
                    await self._dns.switch_baluhost_dns(settings.pi_ip)
            elif power > settings.nas_power_threshold_watts:
                # Hardware on but service crashed — stay in current state
                logger.warning(
                    "NAS HTTP down but power=%.1fW — service may have crashed", power,
                )
        else:
            # No power data, rely on HTTP only
            if current_state not in (NasState.OFFLINE, NasState.SHUTTING_DOWN):
                self._sm.transition(NasState.OFFLINE)
                await self._dns.switch_baluhost_dns(settings.pi_ip)
                self.set_normal_poll()

    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        # Initial delay to let services start
        await asyncio.sleep(5)

        while self._running:
            try:
                http_ok = await self.poll_nas_health()
                await self._handle_detection(http_ok)
            except Exception as e:
                logger.error("Heartbeat error: %s", e)

            interval = self.FAST_POLL_INTERVAL if self._fast_poll else self.POLL_INTERVAL
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
