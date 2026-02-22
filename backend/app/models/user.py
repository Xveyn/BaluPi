"""User model — cached auth data from BaluHost NAS."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nas_user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_auth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
