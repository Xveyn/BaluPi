"""Tapo device schemas."""

from datetime import datetime

from pydantic import BaseModel


class TapoDeviceOut(BaseModel):
    """Tapo device info."""
    id: str
    name: str
    ip_address: str
    mac_address: str | None = None
    model: str | None = None
    role: str = "generic"
    is_online: bool = True
    firmware: str | None = None
    last_seen: datetime | None = None


class TapoDeviceUpdate(BaseModel):
    """Update a Tapo device config."""
    name: str | None = None
    role: str | None = None  # nas, monitor, generic


class TapoDiscoverResult(BaseModel):
    """Result of a Tapo discovery scan."""
    discovered: int
    new_devices: int
    devices: list[TapoDeviceOut]
