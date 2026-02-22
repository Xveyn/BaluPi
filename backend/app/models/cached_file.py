"""Cached file model — locally stored files from NAS."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class CachedFile(Base):
    __tablename__ = "cached_files"
    __table_args__ = (
        UniqueConstraint("server_id", "relative_path", name="uq_cached_file_path"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    nas_file_id: Mapped[str] = mapped_column(String, nullable=False)
    server_id: Mapped[str] = mapped_column(String, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_dirty: Mapped[int] = mapped_column(Integer, default=0)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<CachedFile(id={self.id}, path='{self.relative_path}')>"
