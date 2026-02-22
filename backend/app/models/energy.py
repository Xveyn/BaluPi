"""Energy monitoring models — samples, hourly/daily aggregates, price config."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class EnergySample(Base):
    """Raw energy measurement every 30 seconds."""
    __tablename__ = "energy_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    power_mw: Mapped[int] = mapped_column(Integer, nullable=False)  # Milliwatt
    voltage_mv: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_ma: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    energy_wh: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class EnergyHourly(Base):
    """Hourly aggregated energy data."""
    __tablename__ = "energy_hourly"
    __table_args__ = (
        UniqueConstraint("device_id", "hour", name="uq_energy_hourly"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    hour: Mapped[str] = mapped_column(String(25), nullable=False)  # ISO datetime
    avg_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    max_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    min_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    energy_wh: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)


class EnergyDaily(Base):
    """Daily aggregated energy data."""
    __tablename__ = "energy_daily"
    __table_args__ = (
        UniqueConstraint("device_id", "date", name="uq_energy_daily"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    avg_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    max_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    min_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    energy_wh: Mapped[float] = mapped_column(Float, nullable=False)
    cost_cents: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class EnergyPriceConfig(Base):
    """Electricity price configuration."""
    __tablename__ = "energy_price_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_per_kwh_cents: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[Optional[str]] = mapped_column(String(25), nullable=True)
    valid_to: Mapped[Optional[str]] = mapped_column(String(25), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
