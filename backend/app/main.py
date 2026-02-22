"""BaluPi FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # === STARTUP ===
    _setup_logging()

    # Ensure data directories exist
    for d in (settings.data_dir, settings.cache_dir, settings.thumbnail_dir, settings.log_dir):
        Path(d).mkdir(parents=True, exist_ok=True)

    await init_db()
    logger.info("BaluPi v%s started — listening on %s:%s", __version__, settings.host, settings.port)

    # TODO P1: start energy scheduler
    # TODO P2: start NAS discovery
    # TODO P3: start sync scheduler

    try:
        yield
    finally:
        # === SHUTDOWN ===
        logger.info("BaluPi shutting down")
        # TODO: stop schedulers, close connections


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_app() -> FastAPI:
    """Application factory — mirrors BaluHost pattern."""
    from app.api.routes import api_router

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=_lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()


def run(**kwargs: Any) -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.uvicorn_workers,
        log_level=settings.log_level.lower(),
        **kwargs,
    )


if __name__ == "__main__":
    run()
