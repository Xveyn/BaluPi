"""Sync log model — history of sync operations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    server_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # push | pull
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # create | update | delete
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success | failed | conflict
    bytes_transferred: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SyncLog(id={self.id}, {self.direction} {self.action} {self.status})>"
