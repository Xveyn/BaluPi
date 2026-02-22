"""Upload queue model — pending uploads to NAS."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class UploadQueueItem(Base):
    __tablename__ = "upload_queue"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    server_id: Mapped[str] = mapped_column(String, nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    remote_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<UploadQueueItem(id={self.id}, status='{self.status}')>"
