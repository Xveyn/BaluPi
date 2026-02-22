"""Energy aggregation, queries, and cost calculation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.energy import EnergyDaily, EnergyHourly, EnergyPriceConfig, EnergySample
from app.models.tapo_device import TapoDevice

logger = logging.getLogger(__name__)


class EnergyService:
    """Aggregation, history queries, and cost calculation."""

    async def aggregate_hourly(self, db: AsyncSession) -> int:
        """Aggregate raw samples into hourly buckets (UPSERT)."""
        # Get samples not yet aggregated (last 2 hours to catch stragglers)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)

        stmt = (
            select(
                EnergySample.device_id,
                func.strftime("%Y-%m-%dT%H:00:00", EnergySample.timestamp).label("hour"),
                func.avg(EnergySample.power_mw / 1000.0).label("avg_power"),
                func.max(EnergySample.power_mw / 1000.0).label("max_power"),
                func.min(EnergySample.power_mw / 1000.0).label("min_power"),
                func.count().label("cnt"),
            )
            .where(EnergySample.timestamp >= cutoff)
            .group_by(EnergySample.device_id, "hour")
        )
        result = await db.execute(stmt)
        rows = result.all()

        upserted = 0
        for row in rows:
            device_id, hour, avg_power, max_power, min_power, cnt = row
            # energy_wh = avg_power_w * (cnt * 30s / 3600)
            energy_wh = avg_power * (cnt * settings.energy_sample_interval_seconds / 3600.0)

            existing = await db.execute(
                select(EnergyHourly).where(
                    EnergyHourly.device_id == device_id,
                    EnergyHourly.hour == hour,
                )
            )
            hourly = existing.scalar_one_or_none()

            if hourly:
                hourly.avg_power_w = round(avg_power, 2)
                hourly.max_power_w = round(max_power, 2)
                hourly.min_power_w = round(min_power, 2)
                hourly.energy_wh = round(energy_wh, 2)
                hourly.sample_count = cnt
            else:
                db.add(EnergyHourly(
                    device_id=device_id,
                    hour=hour,
                    avg_power_w=round(avg_power, 2),
                    max_power_w=round(max_power, 2),
                    min_power_w=round(min_power, 2),
                    energy_wh=round(energy_wh, 2),
                    sample_count=cnt,
                ))
            upserted += 1

        if upserted:
            await db.commit()
            logger.info("Aggregated %d hourly buckets", upserted)
        return upserted

    async def aggregate_daily(self, db: AsyncSession) -> int:
        """Aggregate hourly data into daily summaries with cost."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        stmt = (
            select(
                EnergyHourly.device_id,
                func.substr(EnergyHourly.hour, 1, 10).label("date"),
                func.avg(EnergyHourly.avg_power_w).label("avg_power"),
                func.max(EnergyHourly.max_power_w).label("max_power"),
                func.min(EnergyHourly.min_power_w).label("min_power"),
                func.sum(EnergyHourly.energy_wh).label("total_energy"),
            )
            .where(func.substr(EnergyHourly.hour, 1, 10) == yesterday)
            .group_by(EnergyHourly.device_id, "date")
        )
        result = await db.execute(stmt)
        rows = result.all()

        # Get active price
        price_cents = await self._get_active_price(db)
        upserted = 0

        for row in rows:
            device_id, date, avg_power, max_power, min_power, total_energy = row
            cost = (total_energy / 1000.0) * price_cents if total_energy else 0

            existing = await db.execute(
                select(EnergyDaily).where(
                    EnergyDaily.device_id == device_id,
                    EnergyDaily.date == date,
                )
            )
            daily = existing.scalar_one_or_none()

            if daily:
                daily.avg_power_w = round(avg_power, 2)
                daily.max_power_w = round(max_power, 2)
                daily.min_power_w = round(min_power, 2)
                daily.energy_wh = round(total_energy, 2)
                daily.cost_cents = round(cost, 2)
            else:
                db.add(EnergyDaily(
                    device_id=device_id,
                    date=date,
                    avg_power_w=round(avg_power, 2),
                    max_power_w=round(max_power, 2),
                    min_power_w=round(min_power, 2),
                    energy_wh=round(total_energy, 2),
                    cost_cents=round(cost, 2),
                ))
            upserted += 1

        if upserted:
            await db.commit()
            logger.info("Aggregated %d daily buckets for %s", upserted, yesterday)
        return upserted

    async def cleanup_old_samples(self, db: AsyncSession) -> int:
        """Delete raw samples older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.energy_raw_retention_days)
        result = await db.execute(
            delete(EnergySample).where(EnergySample.timestamp < cutoff)
        )
        deleted = result.rowcount
        if deleted:
            await db.commit()
            logger.info("Cleaned up %d old energy samples", deleted)
        return deleted

    async def get_current_all(
        self, db: AsyncSession, tapo_service: Any
    ) -> dict[str, Any]:
        """Get live readings from TapoService buffer (in-memory)."""
        readings = tapo_service.get_current_readings()
        devices = []
        total_power = 0.0

        for device_id, reading in readings.items():
            info = tapo_service.get_device_info(device_id)
            name = info["name"] if info else device_id

            if reading:
                power_w = reading.power_mw / 1000.0
                total_power += power_w
                devices.append({
                    "device_id": device_id,
                    "device_name": name,
                    "power_w": round(power_w, 2),
                    "voltage_v": round(reading.voltage_mv / 1000.0, 1) if reading.voltage_mv else None,
                    "current_a": round(reading.current_ma / 1000.0, 3) if reading.current_ma else None,
                    "is_online": True,
                    "timestamp": reading.timestamp.isoformat(),
                })
            else:
                devices.append({
                    "device_id": device_id,
                    "device_name": name,
                    "power_w": 0.0,
                    "voltage_v": None,
                    "current_a": None,
                    "is_online": False,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return {"devices": devices, "total_power_w": round(total_power, 2)}

    async def get_history(
        self, db: AsyncSession, device_id: str | None, period: str
    ) -> list[dict[str, Any]]:
        """Query historical energy data."""
        now = datetime.now(timezone.utc)

        if period == "day":
            cutoff = now - timedelta(days=1)
            stmt = select(EnergyHourly).where(EnergyHourly.hour >= cutoff.strftime("%Y-%m-%dT%H:00:00"))
        elif period == "week":
            cutoff = now - timedelta(weeks=1)
            stmt = select(EnergyHourly).where(EnergyHourly.hour >= cutoff.strftime("%Y-%m-%dT%H:00:00"))
        else:  # month
            cutoff = now - timedelta(days=30)
            stmt = select(EnergyDaily).where(EnergyDaily.date >= cutoff.strftime("%Y-%m-%d"))

        if device_id:
            if period in ("day", "week"):
                stmt = stmt.where(EnergyHourly.device_id == device_id)
            else:
                stmt = stmt.where(EnergyDaily.device_id == device_id)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        data = []
        for row in rows:
            if isinstance(row, EnergyHourly):
                data.append({
                    "timestamp": row.hour,
                    "avg_power_w": row.avg_power_w,
                    "max_power_w": row.max_power_w,
                    "min_power_w": row.min_power_w,
                    "energy_wh": row.energy_wh,
                })
            else:
                data.append({
                    "timestamp": row.date,
                    "avg_power_w": row.avg_power_w,
                    "max_power_w": row.max_power_w,
                    "min_power_w": row.min_power_w,
                    "energy_wh": row.energy_wh,
                })
        return data

    async def calculate_cost(
        self, db: AsyncSession, device_id: str | None, period: str
    ) -> dict[str, Any]:
        """Calculate energy cost for a device/period."""
        price_cents = await self._get_active_price(db)
        now = datetime.now(timezone.utc)

        if period == "day":
            cutoff = now - timedelta(days=1)
            stmt = select(func.sum(EnergyHourly.energy_wh)).where(
                EnergyHourly.hour >= cutoff.strftime("%Y-%m-%dT%H:00:00")
            )
            if device_id:
                stmt = stmt.where(EnergyHourly.device_id == device_id)
        elif period == "week":
            cutoff = now - timedelta(weeks=1)
            stmt = select(func.sum(EnergyHourly.energy_wh)).where(
                EnergyHourly.hour >= cutoff.strftime("%Y-%m-%dT%H:00:00")
            )
            if device_id:
                stmt = stmt.where(EnergyHourly.device_id == device_id)
        else:  # month
            cutoff = now - timedelta(days=30)
            stmt = select(func.sum(EnergyDaily.energy_wh)).where(
                EnergyDaily.date >= cutoff.strftime("%Y-%m-%d")
            )
            if device_id:
                stmt = stmt.where(EnergyDaily.device_id == device_id)

        result = await db.execute(stmt)
        total_wh = result.scalar() or 0.0
        total_kwh = total_wh / 1000.0
        cost = total_kwh * price_cents

        # Get device name
        dev_name = "all"
        if device_id:
            dev_result = await db.execute(
                select(TapoDevice.name).where(TapoDevice.id == device_id)
            )
            dev_name = dev_result.scalar() or device_id

        return {
            "device_id": device_id or "all",
            "device_name": dev_name,
            "period": period,
            "total_kwh": round(total_kwh, 3),
            "cost_cents": round(cost, 2),
            "price_per_kwh_cents": price_cents,
        }

    async def get_summary(
        self, db: AsyncSession, tapo_service: Any, nas_state: str
    ) -> dict[str, Any]:
        """Aggregate summary: total devices, power, daily kWh, monthly cost estimate."""
        # Current power from buffer
        current = await self.get_current_all(db, tapo_service)
        total_power = current["total_power_w"]
        total_devices = len(current["devices"])

        # Average daily kWh from last 7 days
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        result = await db.execute(
            select(func.avg(EnergyDaily.energy_wh))
            .where(EnergyDaily.date >= week_ago)
        )
        avg_daily_wh = result.scalar() or 0.0
        avg_daily_kwh = avg_daily_wh / 1000.0

        # Monthly estimate
        price_cents = await self._get_active_price(db)
        monthly_kwh = avg_daily_kwh * 30
        monthly_cost = monthly_kwh * price_cents

        return {
            "total_devices": total_devices,
            "total_power_w": round(total_power, 2),
            "avg_daily_kwh": round(avg_daily_kwh, 3),
            "monthly_cost_estimate_cents": round(monthly_cost, 2),
            "nas_state": nas_state,
        }

    async def get_prices(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List all price configurations."""
        result = await db.execute(
            select(EnergyPriceConfig).order_by(EnergyPriceConfig.created_at.desc())
        )
        return [
            {
                "id": p.id,
                "name": p.name,
                "price_per_kwh_cents": p.price_per_kwh_cents,
                "valid_from": p.valid_from,
                "valid_to": p.valid_to,
                "is_active": bool(p.is_active),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in result.scalars().all()
        ]

    async def create_price(self, db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new price configuration."""
        price = EnergyPriceConfig(
            name=data["name"],
            price_per_kwh_cents=data["price_per_kwh_cents"],
            valid_from=data.get("valid_from"),
            valid_to=data.get("valid_to"),
            is_active=1 if data.get("is_active", True) else 0,
        )
        db.add(price)
        await db.commit()
        await db.refresh(price)
        return {
            "id": price.id,
            "name": price.name,
            "price_per_kwh_cents": price.price_per_kwh_cents,
            "valid_from": price.valid_from,
            "valid_to": price.valid_to,
            "is_active": bool(price.is_active),
            "created_at": price.created_at.isoformat() if price.created_at else None,
        }

    async def _get_active_price(self, db: AsyncSession) -> float:
        """Get current active price in cents/kWh."""
        result = await db.execute(
            select(EnergyPriceConfig.price_per_kwh_cents)
            .where(EnergyPriceConfig.is_active == 1)
            .order_by(EnergyPriceConfig.created_at.desc())
            .limit(1)
        )
        price = result.scalar()
        return price if price is not None else settings.energy_default_price_cents
