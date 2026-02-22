"""Conflict model — detected file conflicts between Pi and NAS."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Conflict(Base):
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    server_id: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    local_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Conflict(id={self.id}, path='{self.file_path}', resolution={self.resolution})>"
