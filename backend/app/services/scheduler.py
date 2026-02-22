"""APScheduler-based background jobs for energy monitoring."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session

if TYPE_CHECKING:
    from app.services.energy_service import EnergyService
    from app.services.tapo_service import TapoService

logger = logging.getLogger(__name__)


class EnergyScheduler:
    """Manages periodic energy monitoring jobs."""

    def __init__(
        self,
        tapo_service: TapoService,
        energy_service: EnergyService,
    ):
        self._tapo = tapo_service
        self._energy = energy_service
        self._scheduler = AsyncIOScheduler(
            job_defaults={"coalesce": True, "max_instances": 1}
        )

    def start(self) -> None:
        """Register and start all energy jobs."""
        interval = settings.energy_sample_interval_seconds

        # Job 1: Poll all Tapo devices
        self._scheduler.add_job(
            self._poll_energy,
            "interval",
            seconds=interval,
            id="poll_energy",
            name="Poll energy readings",
        )

        # Job 2: Flush buffer to DB
        self._scheduler.add_job(
            self._flush_buffer,
            "interval",
            seconds=60,
            id="flush_buffer",
            name="Flush energy buffer to DB",
        )

        # Job 3: Hourly aggregation (at :05 past the hour)
        self._scheduler.add_job(
            self._aggregate_hourly,
            "cron",
            minute=5,
            id="aggregate_hourly",
            name="Aggregate hourly energy data",
        )

        # Job 4: Daily aggregation + cleanup (at 00:05)
        self._scheduler.add_job(
            self._aggregate_daily,
            "cron",
            hour=0,
            minute=5,
            id="aggregate_daily",
            name="Aggregate daily energy data + cleanup",
        )

        self._scheduler.start()
        logger.info(
            "Energy scheduler started — polling every %ds, flush every 60s",
            interval,
        )

    async def stop(self) -> None:
        """Stop scheduler and flush remaining buffer."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Energy scheduler stopped")

        # Final flush
        try:
            async with async_session() as db:
                flushed = await self._tapo.flush_buffer(db)
                if flushed:
                    logger.info("Final flush: %d samples written", flushed)
        except Exception as e:
            logger.error("Final flush failed: %s", e)

    async def _poll_energy(self) -> None:
        """Poll all devices for current readings."""
        try:
            async with async_session() as db:
                readings = await self._tapo.poll_all_devices(db)
                if readings:
                    logger.debug("Polled %d device readings", len(readings))
        except Exception as e:
            logger.error("Energy poll failed: %s", e)

    async def _flush_buffer(self) -> None:
        """Flush buffered readings to database."""
        try:
            async with async_session() as db:
                count = await self._tapo.flush_buffer(db)
                if count:
                    logger.debug("Flushed %d samples", count)
        except Exception as e:
            logger.error("Buffer flush failed: %s", e)

    async def _aggregate_hourly(self) -> None:
        """Aggregate samples into hourly buckets."""
        try:
            async with async_session() as db:
                count = await self._energy.aggregate_hourly(db)
                logger.info("Hourly aggregation: %d buckets", count)
        except Exception as e:
            logger.error("Hourly aggregation failed: %s", e)

    async def _aggregate_daily(self) -> None:
        """Aggregate hourly into daily + cleanup old samples."""
        try:
            async with async_session() as db:
                count = await self._energy.aggregate_daily(db)
                deleted = await self._energy.cleanup_old_samples(db)
                logger.info("Daily aggregation: %d buckets, cleaned %d samples", count, deleted)
        except Exception as e:
            logger.error("Daily aggregation failed: %s", e)
