# BaluPi

**Smart Cache & Energy Monitor** for the BaluHost NAS ecosystem, running on a Raspberry Pi 3B+.

## What is BaluPi?

BaluPi is an always-on Raspberry Pi (~4W) that acts as a smart intermediary between your clients (BaluApp, BaluDesk) and your BaluHost NAS (~50–120W). It provides:

1. **Smart Cache** — Mobile-first sync endpoint with 80/20 hot-cache strategy. Frequently accessed files are stored locally on the Pi's SSD for instant access, while the NAS only wakes when needed.

2. **Energy Monitoring** — 24/7 power measurement of the NAS (and other devices) via Tapo P110/P115 smart plugs. Tracks consumption, calculates costs, and detects NAS power state.

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

## Quick Start

### Development (Windows/Linux/macOS)

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Server läuft auf `http://localhost:8000`. API-Docs: `http://localhost:8000/docs`

### Production (Raspberry Pi)

```bash
# One-click install
curl -sSL https://raw.githubusercontent.com/Xveyn/BaluPi/main/deploy/install.sh | bash

# Or manual
git clone https://github.com/Xveyn/BaluPi.git /opt/balupi
cd /opt/balupi
cp .env.example .env
# Edit .env with your NAS URL, Tapo credentials, etc.
bash deploy/install.sh
```

### Verify

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0","service":"balupi","cache_enabled":true,"energy_enabled":true}

curl http://localhost:8000/api/system/status
# {"cpu_percent":12.3,"cpu_temp_celsius":42.5,"memory_total_mb":926.1,...}
```

## Tech Stack

| Komponente | Technologie |
|---|---|
| Runtime | Python 3.11+ |
| Framework | FastAPI (async) |
| Database | SQLite + aiosqlite (WAL-Modus) |
| ORM | SQLAlchemy 2.0 (async) |
| HTTP Client | httpx (NAS-Kommunikation) |
| Energy | python-kasa (Tapo P110/P115) |
| Scheduler | APScheduler |
| Server | Uvicorn (1 Worker) |

## Configuration

All settings via environment variables with `BALUPI_` prefix. See [.env.example](.env.example).

| Variable | Default | Description |
|---|---|---|
| `BALUPI_NAS_URL` | `http://192.168.178.53` | BaluHost NAS URL |
| `BALUPI_NAS_MAC_ADDRESS` | — | NAS MAC for Wake-on-LAN |
| `BALUPI_TAPO_USERNAME` | — | Tapo account email |
| `BALUPI_TAPO_PASSWORD` | — | Tapo account password |
| `BALUPI_SECRET_KEY` | — | JWT signing key |
| `BALUPI_CACHE_MAX_SIZE_GB` | `200` | Max file cache size |
| `BALUPI_ENERGY_DEFAULT_PRICE_CENTS` | `32` | Electricity price ct/kWh |

## API Overview

| Endpoint | Description | Status |
|---|---|---|
| `GET /api/health` | Health check (BaluHost-kompatibel) | P0 |
| `GET /api/system/status` | Pi CPU, RAM, Temp, Disk | P0 |
| `POST /api/auth/login` | Login via NAS | P0 |
| `GET /api/energy/*` | Energiemessung | P1 |
| `GET /api/tapo/*` | Smart Plug Verwaltung | P1 |
| `GET /api/nas/status` | NAS-Erreichbarkeit | P2 |
| `POST /api/nas/wol` | Wake-on-LAN | P2 |
| `GET /api/files/*` | Dateizugriff (Cache) | P3 |
| `GET /api/cache/stats` | Cache-Statistiken | P3 |

Full API documentation: [docs/api.md](docs/api.md)

## Project Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app factory
│   ├── config.py         # Settings (BALUPI_ env prefix)
│   ├── database.py       # Async SQLAlchemy + SQLite WAL
│   ├── models/           # 10 ORM models
│   ├── schemas/          # Pydantic request/response
│   ├── api/routes/       # 8 route modules
│   ├── services/         # Business logic
│   └── utils/            # Hashing, WOL, storage
├── tests/                # pytest + pytest-asyncio
└── pyproject.toml
deploy/                   # systemd, install.sh, update.sh
docs/                     # Technical documentation
```

## Development Roadmap

| Phase | Scope | Status |
|---|---|---|
| P0 | Foundation (FastAPI, DB, Health, System) | Done |
| P1 | Energy Monitoring (Tapo, Messung, Kosten) | Next |
| P2 | NAS Discovery (mDNS, WOL, Handshake) | Planned |
| P3 | Smart Cache & File Sync | Planned |
| P4 | Client-Integration (BaluApp, BaluDesk) | Planned |
| P5 | Hardening (Watchdog, Logs, Auto-Update) | Planned |

## Hardware

- Raspberry Pi 3B+ (1 GB RAM, 4x A53 @ 1.4 GHz)
- 256 GB USB-SSD (Cache Storage)
- Power: ~4W idle (~1 kWh/Monat, ~0.30 EUR/Monat)

## Related Projects

- [BaluHost](https://github.com/Xveyn/BaluHost) — NAS Backend & Web UI
- [BaluDesk](https://github.com/Xveyn/BaluDesk) — Desktop Sync Client
- [BaluApp](https://github.com/Xveyn/BaluApp) — Android App

## License

MIT
