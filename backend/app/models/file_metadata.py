"""File metadata cache — NAS file index cached locally."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class FileMetadataCache(Base):
    __tablename__ = "file_metadata_cache"
    __table_args__ = (
        UniqueConstraint("server_id", "nas_file_id", name="uq_metadata_nas_file"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    server_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    nas_file_id: Mapped[str] = mapped_column(String, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_directory: Mapped[int] = mapped_column(Integer, default=0)
    parent_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<FileMetadataCache(id={self.id}, path='{self.relative_path}')>"
