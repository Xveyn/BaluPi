"""Tapo smart plug hardware abstraction — discovery, polling, buffering."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast

from kasa import Device, Discover
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import EnergySample
from app.models.tapo_device import TapoDevice

logger = logging.getLogger(__name__)

MAX_BUFFER_SIZE = 120  # per device
MAX_FAIL_COUNT = 3


@dataclass
class EnergyReading:
    device_id: str
    power_mw: int
    voltage_mv: int | None = None
    current_ma: int | None = None
    energy_wh: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TapoService:
    """Manages Tapo smart plug connections, polling, and buffering."""

    def __init__(self, username: str = "", password: str = ""):
        self._username = username
        self._password = password
        self._devices: dict[str, Device] = {}  # ip -> Device
        self._buffers: dict[str, deque[EnergyReading]] = {}  # device_id -> readings
        self._fail_counts: dict[str, int] = {}  # device_id -> consecutive failures
        self._device_map: dict[str, dict[str, Any]] = {}  # device_id -> {ip, name, ...}
        self._initialized = False

    async def initialize(self, db: AsyncSession) -> None:
        """Load known devices from DB and connect."""
        result = await db.execute(select(TapoDevice))
        devices = result.scalars().all()
        for dev in devices:
            self._device_map[dev.id] = {
                "ip": dev.ip_address,
                "name": dev.name,
                "role": dev.role,
            }
            self._buffers.setdefault(dev.id, deque(maxlen=MAX_BUFFER_SIZE))
            self._fail_counts.setdefault(dev.id, 0)
        self._initialized = True
        logger.info("TapoService initialized with %d known devices", len(devices))

    async def _connect_device(self, ip: str) -> Device | None:
        """Connect to a single Tapo device."""
        try:
            dev = await Discover.discover_single(
                ip, credentials=self._get_credentials()
            )
            if dev is None:
                return None
            await dev.update()
            return dev
        except Exception as e:
            logger.debug("Failed to connect to %s: %s", ip, e)
            return None

    def _get_credentials(self):
        """Build kasa Credentials if username/password set."""
        if self._username and self._password:
            from kasa import Credentials
            return Credentials(self._username, self._password)
        return None

    async def poll_all_devices(self, db: AsyncSession) -> list[EnergyReading]:
        """Poll all known devices for current energy readings."""
        readings: list[EnergyReading] = []
        device_ids = list(self._device_map.keys())

        for device_id in device_ids:
            info = self._device_map[device_id]
            ip = info["ip"]
            reading = await self._poll_single(device_id, ip)
            if reading:
                readings.append(reading)
                self._buffers.setdefault(device_id, deque(maxlen=MAX_BUFFER_SIZE))
                self._buffers[device_id].append(reading)
                self._fail_counts[device_id] = 0
                # Update last_seen
                await self._update_online_status(db, device_id, True)
            else:
                self._fail_counts[device_id] = self._fail_counts.get(device_id, 0) + 1
                if self._fail_counts[device_id] >= MAX_FAIL_COUNT:
                    await self._update_online_status(db, device_id, False)
                    logger.warning(
                        "Device %s (%s) marked offline after %d failures",
                        device_id, ip, MAX_FAIL_COUNT,
                    )

        if readings:
            await db.commit()

        return readings

    async def _poll_single(self, device_id: str, ip: str) -> EnergyReading | None:
        """Read energy data from one device."""
        try:
            # Get or create connection
            if ip not in self._devices:
                dev = await self._connect_device(ip)
                if not dev:
                    return None
                self._devices[ip] = dev
            else:
                dev = self._devices[ip]
                try:
                    await dev.update()
                except Exception:
                    # Reconnect on stale connection
                    del self._devices[ip]
                    dev = await self._connect_device(ip)
                    if not dev:
                        return None
                    self._devices[ip] = dev

            if not dev.has_emeter:
                logger.debug("Device %s has no energy meter", device_id)
                return None

            # python-kasa types incomplete — emeter_realtime exists on energy-capable devices
            emeter: dict[str, Any] = cast(dict[str, Any], getattr(dev, "emeter_realtime"))
            # python-kasa may return values in mW/mV/mA or W/V/A depending on device
            if "power_mw" in emeter:
                power_mw = int(emeter["power_mw"])
            else:
                power_mw = int(emeter.get("power", 0) * 1000)

            if "voltage_mv" in emeter:
                voltage_mv = _safe_int(emeter["voltage_mv"])
            else:
                voltage_mv = _safe_int(emeter.get("voltage"), 1000)

            if "current_ma" in emeter:
                current_ma = _safe_int(emeter["current_ma"])
            else:
                current_ma = _safe_int(emeter.get("current"), 1000)

            energy_wh = _safe_int(emeter.get("total_wh", emeter.get("total")))

            return EnergyReading(
                device_id=device_id,
                power_mw=power_mw,
                voltage_mv=voltage_mv,
                current_ma=current_ma,
                energy_wh=energy_wh,
            )
        except Exception as e:
            logger.debug("Poll failed for %s (%s): %s", device_id, ip, e)
            # Invalidate cached connection
            self._devices.pop(ip, None)
            return None

    async def _update_online_status(
        self, db: AsyncSession, device_id: str, is_online: bool
    ) -> None:
        result = await db.execute(select(TapoDevice).where(TapoDevice.id == device_id))
        dev = result.scalar_one_or_none()
        if dev:
            dev.is_online = 1 if is_online else 0
            if is_online:
                dev.last_seen = datetime.now(timezone.utc)

    async def flush_buffer(self, db: AsyncSession) -> int:
        """Write buffered readings to DB and clear buffers."""
        total = 0
        for device_id, buffer in self._buffers.items():
            if not buffer:
                continue
            samples = []
            while buffer:
                r = buffer.popleft()
                samples.append(EnergySample(
                    device_id=r.device_id,
                    power_mw=r.power_mw,
                    voltage_mv=r.voltage_mv,
                    current_ma=r.current_ma,
                    energy_wh=r.energy_wh,
                    timestamp=r.timestamp,
                ))
            db.add_all(samples)
            total += len(samples)

        if total > 0:
            await db.commit()
            logger.debug("Flushed %d energy samples to DB", total)
        return total

    async def discover_devices(self, db: AsyncSession) -> dict[str, Any]:
        """Scan network for Tapo devices, register new ones in DB."""
        try:
            discovered = await Discover.discover(credentials=self._get_credentials())
        except Exception as e:
            logger.error("Discovery failed: %s", e)
            return {"discovered": 0, "new_devices": 0, "devices": []}

        new_count = 0
        all_devices = []

        # Get existing devices by IP
        result = await db.execute(select(TapoDevice))
        existing = {d.ip_address: d for d in result.scalars().all()}

        for ip, dev in discovered.items():
            try:
                await dev.update()
            except Exception:
                continue

            if ip in existing:
                # Update existing
                db_dev = existing[ip]
                db_dev.is_online = 1
                db_dev.last_seen = datetime.now(timezone.utc)
                if dev.model:
                    db_dev.model = dev.model
                if hasattr(dev, "hw_info") and dev.hw_info.get("fw_ver"):
                    db_dev.firmware = dev.hw_info["fw_ver"]
                all_devices.append(db_dev)
            else:
                # Create new
                dev_id = str(uuid.uuid4())
                alias = getattr(dev, "alias", None) or f"Tapo {ip}"
                mac = getattr(dev, "mac", None)
                model = getattr(dev, "model", None)
                fw = None
                if hasattr(dev, "hw_info"):
                    fw = dev.hw_info.get("fw_ver")

                new_dev = TapoDevice(
                    id=dev_id,
                    name=alias,
                    ip_address=ip,
                    mac_address=mac,
                    model=model,
                    firmware=fw,
                    is_online=1,
                    last_seen=datetime.now(timezone.utc),
                )
                db.add(new_dev)
                new_count += 1
                all_devices.append(new_dev)

                # Register in memory
                self._device_map[dev_id] = {"ip": ip, "name": alias, "role": "generic"}
                self._buffers[dev_id] = deque(maxlen=MAX_BUFFER_SIZE)
                self._fail_counts[dev_id] = 0

        await db.commit()
        logger.info("Discovery: %d found, %d new", len(discovered), new_count)

        return {
            "discovered": len(discovered),
            "new_devices": new_count,
            "devices": [_device_to_dict(d) for d in all_devices],
        }

    async def get_all_devices(self, db: AsyncSession) -> list[dict[str, Any]]:
        """List all known Tapo devices from DB."""
        result = await db.execute(select(TapoDevice))
        return [_device_to_dict(d) for d in result.scalars().all()]

    async def update_device(
        self, db: AsyncSession, device_id: str, name: str | None, role: str | None
    ) -> dict[str, Any] | None:
        """Update device name/role."""
        result = await db.execute(select(TapoDevice).where(TapoDevice.id == device_id))
        dev = result.scalar_one_or_none()
        if not dev:
            return None
        if name is not None:
            dev.name = name
        if role is not None:
            dev.role = role
        await db.commit()
        await db.refresh(dev)

        # Update in-memory map
        if device_id in self._device_map:
            if name is not None:
                self._device_map[device_id]["name"] = name
            if role is not None:
                self._device_map[device_id]["role"] = role

        return _device_to_dict(dev)

    async def toggle_device(self, db: AsyncSession, device_id: str) -> dict[str, Any]:
        """Toggle a Tapo device on/off."""
        result = await db.execute(select(TapoDevice).where(TapoDevice.id == device_id))
        dev = result.scalar_one_or_none()
        if not dev:
            raise ValueError(f"Device {device_id} not found")

        ip = dev.ip_address
        smart_dev = self._devices.get(ip) or await self._connect_device(ip)
        if not smart_dev:
            raise ConnectionError(f"Cannot connect to device at {ip}")
        self._devices[ip] = smart_dev

        if smart_dev.is_on:
            await smart_dev.turn_off()
            state = "off"
        else:
            await smart_dev.turn_on()
            state = "on"

        await smart_dev.update()
        dev.last_seen = datetime.now(timezone.utc)
        await db.commit()

        return {"device_id": device_id, "new_state": state, "success": True}

    def get_current_readings(self) -> dict[str, EnergyReading | None]:
        """Get latest buffered reading per device (in-memory, no DB)."""
        result: dict[str, EnergyReading | None] = {}
        for device_id, buffer in self._buffers.items():
            result[device_id] = buffer[-1] if buffer else None
        return result

    def get_device_info(self, device_id: str) -> dict[str, Any] | None:
        """Get in-memory device info."""
        return self._device_map.get(device_id)


def _device_to_dict(dev: TapoDevice) -> dict[str, Any]:
    return {
        "id": dev.id,
        "name": dev.name,
        "ip_address": dev.ip_address,
        "mac_address": dev.mac_address,
        "model": dev.model,
        "role": dev.role,
        "is_online": bool(dev.is_online),
        "firmware": dev.firmware,
        "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
    }


def _safe_int(value: Any, multiplier: int = 1) -> int | None:
    """Convert value to int, optionally multiplying (e.g. V -> mV)."""
    if value is None:
        return None
    try:
        return int(float(value) * multiplier)
    except (TypeError, ValueError):
        return None
