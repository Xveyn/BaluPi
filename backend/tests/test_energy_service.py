"""Tests for EnergyService — aggregation, cost, cleanup."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.energy import EnergyDaily, EnergyHourly, EnergyPriceConfig, EnergySample
from app.services.energy_service import EnergyService


@pytest_asyncio.fixture
async def energy_service():
    return EnergyService()


@pytest_asyncio.fixture
async def seeded_samples(db_session):
    """Insert sample energy data for aggregation tests."""
    now = datetime.now(timezone.utc)
    hour_str = now.strftime("%Y-%m-%dT%H:00:00")

    samples = []
    for i in range(10):
        samples.append(EnergySample(
            device_id="dev-test",
            power_mw=50000 + i * 1000,  # 50W - 59W
            voltage_mv=230000,
            current_ma=220 + i,
            timestamp=now - timedelta(seconds=30 * i),
        ))
    db_session.add_all(samples)
    await db_session.commit()
    return samples


@pytest.mark.asyncio
async def test_aggregate_hourly(db_session, energy_service, seeded_samples):
    """aggregate_hourly creates hourly buckets from raw samples."""
    count = await energy_service.aggregate_hourly(db_session)
    assert count >= 1

    result = await db_session.execute(
        select(EnergyHourly).where(EnergyHourly.device_id == "dev-test")
    )
    hourly = result.scalars().all()
    assert len(hourly) >= 1

    h = hourly[0]
    assert h.avg_power_w > 0
    assert h.max_power_w >= h.avg_power_w
    assert h.min_power_w <= h.avg_power_w
    assert h.sample_count == 10
    assert h.energy_wh > 0


@pytest.mark.asyncio
async def test_aggregate_daily(db_session, energy_service):
    """aggregate_daily creates daily summary from hourly data."""
    # Insert hourly data for yesterday
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    for hour in range(24):
        db_session.add(EnergyHourly(
            device_id="dev-daily",
            hour=f"{yesterday}T{hour:02d}:00:00",
            avg_power_w=45.0,
            max_power_w=60.0,
            min_power_w=30.0,
            energy_wh=45.0,  # 45Wh per hour
            sample_count=120,
        ))
    await db_session.commit()

    count = await energy_service.aggregate_daily(db_session)
    assert count == 1

    result = await db_session.execute(
        select(EnergyDaily).where(EnergyDaily.device_id == "dev-daily")
    )
    daily = result.scalar_one()
    assert daily.date == yesterday
    assert daily.avg_power_w == 45.0
    assert daily.energy_wh == 45.0 * 24  # 1080 Wh
    assert daily.cost_cents is not None
    assert daily.cost_cents > 0


@pytest.mark.asyncio
async def test_cleanup_old_samples(db_session, energy_service):
    """cleanup_old_samples deletes samples older than retention period."""
    now = datetime.now(timezone.utc)

    # Old sample (8 days ago)
    old = EnergySample(
        device_id="dev-old",
        power_mw=10000,
        timestamp=now - timedelta(days=8),
    )
    # Recent sample (1 day ago)
    recent = EnergySample(
        device_id="dev-recent",
        power_mw=20000,
        timestamp=now - timedelta(days=1),
    )
    db_session.add_all([old, recent])
    await db_session.commit()

    deleted = await energy_service.cleanup_old_samples(db_session)
    assert deleted == 1

    # Recent should still exist
    result = await db_session.execute(select(EnergySample))
    remaining = result.scalars().all()
    assert len(remaining) == 1
    assert remaining[0].device_id == "dev-recent"


@pytest.mark.asyncio
async def test_calculate_cost_with_price(db_session, energy_service):
    """calculate_cost uses active price config."""
    # Set up price
    price = EnergyPriceConfig(
        name="Test Tariff",
        price_per_kwh_cents=30.0,
        is_active=1,
    )
    db_session.add(price)

    # Add daily data for last 30 days
    for i in range(5):
        date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        db_session.add(EnergyDaily(
            device_id="dev-cost",
            date=date,
            avg_power_w=100.0,
            max_power_w=150.0,
            min_power_w=50.0,
            energy_wh=2400.0,  # 2.4 kWh/day
        ))
    await db_session.commit()

    result = await energy_service.calculate_cost(db_session, "dev-cost", "month")
    assert result["total_kwh"] > 0
    assert result["cost_cents"] > 0
    assert result["price_per_kwh_cents"] == 30.0


@pytest.mark.asyncio
async def test_calculate_cost_default_price(db_session, energy_service):
    """calculate_cost falls back to default price when no config exists."""
    result = await energy_service.calculate_cost(db_session, None, "month")
    # Should use settings.energy_default_price_cents (32.0)
    assert result["price_per_kwh_cents"] == 32.0


@pytest.mark.asyncio
async def test_get_prices_and_create(db_session, energy_service):
    """Test price config CRUD."""
    # Initially empty
    prices = await energy_service.get_prices(db_session)
    assert prices == []

    # Create price
    created = await energy_service.create_price(db_session, {
        "name": "Normal",
        "price_per_kwh_cents": 32.0,
    })
    assert created["name"] == "Normal"
    assert created["price_per_kwh_cents"] == 32.0
    assert created["is_active"] is True

    # List should have one entry
    prices = await energy_service.get_prices(db_session)
    assert len(prices) == 1
