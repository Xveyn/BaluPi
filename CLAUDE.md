# CLAUDE.md — BaluPi

## Project Overview

**BaluPi** is a Raspberry Pi 3B+ based smart cache tier and energy monitor for the BaluHost NAS ecosystem.

### Architecture

```
BaluApp (Android) ──┐
                    ▼
               ┌─────────┐    WOL / REST     ┌──────────┐
               │ BaluPi  │ ◄───────────────► │ BaluHost │
               │ (Cache) │    Sync & Energy   │  (NAS)   │
               └─────────┘                    └──────────┘
                    ▲
BaluDesk (Desktop) ─┘
```

### Two Core Functions
1. **Smart Cache**: Mobile-first sync endpoint with 80/20 hot-cache strategy
2. **Energy Monitoring**: 24/7 power measurement via Tapo Smart Plugs

## Tech Stack

- **Python 3.11+** / **FastAPI** (async, API-compatible with BaluHost)
- **SQLAlchemy 2.0 + aiosqlite** (async SQLite with WAL mode)
- **Pydantic v2** (schema sharing with BaluHost)
- **httpx** (async HTTP client for NAS communication)
- **python-kasa** (Tapo P110/P115 energy measurement)
- **psutil** (Pi system monitoring)
- **APScheduler** (energy/sync scheduling)

## Directory Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings (Pydantic BaseSettings, BALUPI_ prefix)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── api/
│   │   ├── deps.py          # Auth & DB dependency injection
│   │   └── routes/          # API route handlers
│   ├── services/            # Business logic
│   └── utils/               # Hashing, WOL, storage helpers
├── tests/
└── pyproject.toml
deploy/                      # systemd, install.sh
data/                        # Runtime data (not in git)
```

## Commands

```bash
# Development (from backend/)
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Test
pytest

# Production (on Pi)
sudo systemctl start balupi
curl http://localhost:8000/api/health
```

## API Endpoints

### Core (P0 — implemented)
- `GET /api/health` — Health check (BaluHost-compatible)
- `GET /api/ping` — Ultra-lightweight ping
- `GET /api/system/status` — Pi CPU, RAM, temp, disk, uptime
- `POST /api/auth/login` — Forward to NAS

### Energy Monitoring (P1 — stubs)
- `GET /api/energy/current` — Current power readings
- `GET /api/energy/history` — Historical data
- `GET /api/energy/costs` — Cost calculations
- `GET /api/energy/summary` — Overall summary
- `GET /api/tapo/devices` — List Tapo devices
- `POST /api/tapo/devices/discover` — Network scan
- `PUT /api/tapo/devices/{id}` — Configure device
- `POST /api/tapo/devices/{id}/toggle` — Toggle on/off

### NAS Management (P2 — stubs)
- `GET /api/nas/status` — NAS reachability
- `POST /api/nas/wol` — Wake-on-LAN

### File & Cache (P3 — stubs)
- `GET /api/files/list` — File listing (cached + NAS)
- `GET /api/files/download/{id}` — Cache-hit or NAS proxy
- `POST /api/files/upload` — Store locally, queue sync
- `GET /api/files/sync/status` — Sync status
- `GET /api/cache/stats` — Cache statistics

## Configuration

All settings via env vars with `BALUPI_` prefix. See `.env.example`.

Key settings:
- `BALUPI_NAS_URL` — BaluHost NAS URL (default: http://192.168.178.53)
- `BALUPI_NAS_MAC_ADDRESS` — For Wake-on-LAN
- `BALUPI_TAPO_USERNAME` / `BALUPI_TAPO_PASSWORD` — Tapo account
- `BALUPI_SECRET_KEY` — JWT signing key

## Database

SQLite with WAL mode. Schema in `app/models/`. Tables:
- `users` — Cached auth data from NAS
- `servers` — NAS connection profiles
- `cached_files` — Locally cached files
- `upload_queue` — Pending NAS uploads
- `sync_log` — Sync operation history
- `conflicts` — File conflicts
- `file_metadata_cache` — NAS file index
- `tapo_devices` — Smart plug devices
- `energy_samples` — Raw measurements (30s, 7d retention)
- `energy_hourly` — Hourly aggregates (1 year)
- `energy_daily` — Daily aggregates (unlimited)
- `energy_price_config` — Electricity tariffs

## Related Projects

- **BaluHost**: NAS backend — https://github.com/Xveyn/BaluHost
- **BaluDesk**: Desktop client — https://github.com/Xveyn/BaluDesk
- **BaluApp**: Android app — https://github.com/Xveyn/BaluApp
