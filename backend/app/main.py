"""BaluPi FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.database import async_session, init_db
from app.services import init_services, shutdown_services

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

    # Initialize all services (Phase 1: energy + Phase 2: NAS handshake)
    async with async_session() as db:
        await init_services(db)

    try:
        yield
    finally:
        # === SHUTDOWN ===
        await shutdown_services()
        logger.info("BaluPi shutting down")


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Noisy third-party loggers auf WARNING setzen
    for noisy in ("aiosqlite", "kasa", "kasa.smart.smartmodule", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


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

    # Serve BaluHost frontend (synced via sync_frontend.py -> dist/)
    static_dir = Path(__file__).resolve().parent.parent.parent / "dist"
    if static_dir.is_dir() and (static_dir / "index.html").exists():
        # Serve static assets (js, css, images, etc.)
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="frontend-assets")

        _index = static_dir / "index.html"

        # SPA fallback: any non-API route serves index.html
        @app.get("/", include_in_schema=False)
        async def _spa_root():
            return FileResponse(_index)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str):
            # Try to serve the exact file first (favicon.ico, etc.)
            file_path = static_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(_index)

        logger.info("Frontend mounted from %s", static_dir)
    else:
        logger.info("No frontend found at %s — API-only mode", static_dir)

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
