"""Tapo smart plug device model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class TapoDevice(Base):
    __tablename__ = "tapo_devices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="generic")  # nas, monitor, generic
    is_online: Mapped[int] = mapped_column(Integer, default=1)
    firmware: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TapoDevice(id={self.id}, name='{self.name}', role='{self.role}')>"
