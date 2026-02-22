"""SQLAlchemy async engine & session for SQLite (WAL mode)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base

logger = logging.getLogger(__name__)


def _configure_sqlite(dbapi_conn, _connection_record):
    """Apply SQLite PRAGMAs for optimal Pi performance."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-8000")  # 8 MB
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA mmap_size=33554432")  # 32 MB
    cursor.close()


# Ensure DB directory exists
db_path = Path(settings.database_path)
db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug and settings.log_level == "DEBUG",
    pool_size=settings.max_db_connections,
    max_overflow=0,
)

# Apply SQLite PRAGMAs on each new connection
event.listen(engine.sync_engine, "connect", _configure_sqlite)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables (dev/first-run). Production uses Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified at %s", db_path)
