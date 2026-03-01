"""BaluPi configuration — Pydantic BaseSettings loaded from .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, compatible with BaluHost patterns."""

    app_name: str = "BaluPi"
    debug: bool = True
    environment: str = "development"
    log_level: str = "INFO"

    # Network
    host: str = "127.0.0.1"
    port: int = 8000
    api_prefix: str = "/api"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # Auth — Pi validates tokens against NAS or uses cached hashes
    secret_key: str = "change-me-in-prod"
    token_algorithm: str = "HS256"
    token_expire_minutes: int = 720  # 12 hours

    # NAS connection
    nas_url: str = "http://192.168.178.53"
    nas_mac_address: str = ""  # For WOL
    nas_username: str = ""
    nas_password: str = ""

    # Storage paths (relative resolved from project root at runtime)
    data_dir: str = "./data"
    cache_dir: str = "./data/cache/files"
    thumbnail_dir: str = "./data/cache/thumbnails"
    log_dir: str = "./data/logs"
    database_path: str = "./data/balupi.db"

    # Energy monitoring
    energy_sample_interval_seconds: int = 30
    energy_raw_retention_days: int = 7
    energy_default_price_cents: float = 32.0  # ct/kWh

    # Tapo credentials
    tapo_username: str = ""
    tapo_password: str = ""

    # NAS power detection
    nas_power_threshold_watts: float = 30.0

    # Mode: dev = mock data, prod = real hardware
    mode: str = "dev"

    # Handshake (NAS <-> Pi HMAC auth)
    handshake_secret: str = ""  # Shared HMAC secret (32+ chars)

    # Pi-hole DNS switching
    pihole_url: str = "http://localhost"
    pihole_password: str = ""
    pi_ip: str = ""  # Pi's own IP for DNS switching

    # NAS connection (extended)
    nas_ip: str = ""  # NAS IP for DNS switching
    nas_inbox_path: str = "/data/inbox"  # NAS-side inbox path for rsync
    nas_ssh_user: str = "baluhost"  # SSH user for rsync

    # Pi hardware limits
    uvicorn_workers: int = 1
    max_db_connections: int = 5

    @property
    def is_dev_mode(self) -> bool:
        return self.mode == "dev"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        env_prefix="BALUPI_",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: list[str] | str) -> list[str]:
        if isinstance(value, str) and not value.startswith("["):
            return [o.strip() for o in value.split(",") if o.strip()]
        if isinstance(value, list):
            return value
        return ["http://localhost:5173"]

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Ensure data directories are absolute."""
        base = Path(__file__).resolve().parent.parent  # backend/
        for field in ("data_dir", "cache_dir", "thumbnail_dir", "log_dir", "database_path"):
            val = getattr(self, field)
            if not Path(val).is_absolute():
                setattr(self, field, str(base / val))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
