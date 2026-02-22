"""NAS server model — connection profiles."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    mac_address: Mapped[Optional[str]] = mapped_column(String(17), nullable=True)
    tapo_device_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    power_threshold: Mapped[float] = mapped_column(Float, default=30.0)
    is_online: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Server(id={self.id}, name='{self.name}', url='{self.url}')>"
