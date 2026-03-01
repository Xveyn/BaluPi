# CLAUDE.md — BaluPi

## Project Overview

**BaluPi** is a Raspberry Pi 3B+ based always-on node for the BaluHost NAS ecosystem. It provides PiHole/DNS, energy monitoring via Tapo smart plugs, Wake-on-LAN with automated handshake, and a view-only dashboard.

### Architecture

```
Heimnetzwerk
│
├── NAS (BaluHost) ─ 192.168.x.10
│   • Volles Frontend + Backend (FastAPI + PostgreSQL)
│   • Läuft nur bei Bedarf (30-50W)
│
└── Raspberry Pi 3B+ (BaluPi) ─ 192.168.x.20
    • View-Only Dashboard + PiHole/DNS
    • Tapo Strommonitoring
    • WoL + Handshake + DNS-Switch
    • SMB-Share (1TB HDD)
    • Läuft immer (~3-5W)
```

### Core Functions
1. **PiHole/DNS** — Ad-blocking and `baluhost.local` DNS switching (NAS online → NAS-IP, offline → Pi-IP)
2. **Energy Monitoring** — 24/7 power measurement via Tapo P110/P115 Smart Plugs
3. **Wake-on-LAN & Handshake** — NAS lifecycle management with state machine, heartbeat, and inbox flush

## Tech Stack

- **Python 3.11+** / **FastAPI** (async)
- **SQLAlchemy 2.0 + aiosqlite** (async SQLite with WAL mode)
- **Pydantic v2** (schema sharing with BaluHost)
- **httpx** (async HTTP client for NAS communication)
- **python-kasa** (Tapo P110/P115 energy measurement)
- **psutil** (Pi system monitoring)
- **APScheduler** (energy scheduling)
- **nginx** (reverse proxy, port 80)

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
│   ├── services/            # State machine, heartbeat, DNS, Tapo, energy
│   └── utils/               # WOL, hashing
├── tests/
└── pyproject.toml
deploy/                      # nginx.conf, balupi.service, install.sh, update.sh
dist/                        # Frontend (deployed via sync_frontend.py)
pi_setup.md                  # Vollständige Pi-Einrichtungsanleitung
BALUPI_PLAN.md               # Projektplan & Architektur
```

## Commands

```bash
# Development (from backend/)
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Test
pytest

# Production (on Pi, via nginx)
sudo systemctl start balupi
curl http://localhost/api/health
```

## API Endpoints

### Core (P0 — done)
- `GET /api/health` — Health check (BaluHost-compatible)
- `GET /api/ping` — Ultra-lightweight ping
- `GET /api/system/status` — Pi CPU, RAM, temp, disk, uptime
- `POST /api/auth/login` — Forward to NAS

### Energy Monitoring (P1 — done)
- `GET /api/energy/current` — Current power readings
- `GET /api/energy/history` — Historical data
- `GET /api/energy/costs` — Cost calculations
- `GET /api/energy/summary` — Overall summary
- `GET /api/tapo/devices` — List Tapo devices
- `POST /api/tapo/devices/discover` — Network scan
- `PUT /api/tapo/devices/{id}` — Configure device
- `POST /api/tapo/devices/{id}/toggle` — Toggle on/off

### NAS Management & Handshake (P2 — done)
- `GET /api/nas/status` — NAS state (state machine + live check)
- `POST /api/nas/wol` — Wake-on-LAN with power check (auth required)
- `POST /api/handshake/nas-going-offline` — NAS shutdown notification (HMAC)
- `POST /api/handshake/nas-coming-online` — NAS boot notification (HMAC)
- `GET /api/handshake/status` — Handshake status & inbox info (auth required)
- `GET /api/handshake/snapshot` — Last NAS snapshot (auth required)

## Configuration

All settings via env vars with `BALUPI_` prefix. See `.env.example` and `pi_setup.md`.

Key settings:
- `BALUPI_MODE` — `dev` (mock data) or `prod` (real hardware)
- `BALUPI_NAS_URL` — BaluHost NAS URL (default: http://192.168.178.53)
- `BALUPI_NAS_MAC_ADDRESS` — For Wake-on-LAN
- `BALUPI_NAS_IP` — NAS IP for DNS switching
- `BALUPI_HANDSHAKE_SECRET` — Shared HMAC secret (must match NAS)
- `BALUPI_PIHOLE_URL` / `BALUPI_PIHOLE_PASSWORD` — Pi-hole DNS control
- `BALUPI_PI_IP` — Pi's own IP for DNS switching
- `BALUPI_TAPO_USERNAME` / `BALUPI_TAPO_PASSWORD` — Tapo account
- `BALUPI_SECRET_KEY` — JWT signing key
- `BALUPI_NAS_SSH_USER` / `BALUPI_NAS_INBOX_PATH` — rsync inbox flush

## Database

SQLite with WAL mode. Schema in `app/models/`. Tables:
- `users` — Cached auth data from NAS
- `servers` — NAS connection profiles
- `tapo_devices` — Smart plug devices
- `energy_samples` — Raw measurements (30s, 7d retention)
- `energy_hourly` — Hourly aggregates (1 year)
- `energy_daily` — Daily aggregates (unlimited)
- `energy_price_config` — Electricity tariffs

NAS state is persisted as JSON in `data/handshake/nas_state.json` (not in DB).

## Related Projects

- **BaluHost**: NAS backend — https://github.com/Xveyn/BaluHost
- **BaluDesk**: Desktop client — https://github.com/Xveyn/BaluDesk
- **BaluApp**: Android app — https://github.com/Xveyn/BaluApp
