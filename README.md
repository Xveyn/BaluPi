# BaluPi

**Always-on Raspberry Pi Node** im BaluHost-NAS-Ökosystem — PiHole/DNS, Strommonitoring, Wake-on-LAN und View-Only-Dashboard.

## Was ist BaluPi?

BaluPi ist ein Raspberry Pi 3B+ (~3–5W), der **immer läuft** und als passiver Gegenpart zum BaluHost-NAS dient. Drei Kernaufgaben:

1. **PiHole/DNS** — Netzwerk-weites Ad-Blocking und DNS-Umschaltung (`baluhost.local` zeigt je nach NAS-Status auf NAS oder Pi)
2. **Strommonitoring** — 24/7 Messung des NAS-Verbrauchs via Tapo P110/P115 Smart Plugs
3. **Wake-on-LAN & Handshake** — NAS bei Bedarf aufwecken, automatischer DNS-Switch und Inbox-Flush beim Hoch-/Runterfahren

Zusätzlich: ein **abgespecktes View-Only-Dashboard** (vom NAS gebaut, auf dem Pi gehostet) und ein **eigenständiger SMB-Share** als immer verfügbarer Speicher.

```
Heimnetzwerk
│
├── NAS (BaluHost) ─ 192.168.x.10
│   • Volles Frontend + Backend
│   • Läuft nur bei Bedarf (30-50W)
│
└── Raspberry Pi 3B+ (BaluPi) ─ 192.168.x.20
    • View-Only Dashboard + PiHole
    • Tapo Strommonitoring
    • WoL + Handshake + DNS-Switch
    • SMB-Share (1TB HDD)
    • Läuft immer (~3-5W)
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
# One-click install (inkl. nginx, systemd)
curl -sSL https://raw.githubusercontent.com/Xveyn/BaluPi/main/deploy/install.sh | bash

# Dann konfigurieren
nano /opt/balupi/.env
sudo systemctl start balupi
```

Vollständige Einrichtungsanleitung: **[pi_setup.md](pi_setup.md)**

### Verify

```bash
curl http://localhost/api/health
# {"status":"ok","version":"0.1.0","service":"balupi"}

curl http://localhost/api/system/status
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
| Reverse Proxy | nginx (Port 80) |
| Server | Uvicorn (127.0.0.1:8000, 1 Worker) |

## Configuration

Alle Einstellungen via Umgebungsvariablen mit `BALUPI_`-Prefix. Siehe [.env.example](.env.example) und [pi_setup.md](pi_setup.md#konfiguration).

| Variable | Default | Beschreibung |
|---|---|---|
| `BALUPI_MODE` | `dev` | `dev` = Mock-Daten, `prod` = echte Hardware |
| `BALUPI_NAS_URL` | `http://192.168.178.53` | BaluHost NAS URL |
| `BALUPI_NAS_MAC_ADDRESS` | — | NAS MAC für Wake-on-LAN |
| `BALUPI_NAS_IP` | — | NAS-IP für DNS-Umschaltung |
| `BALUPI_HANDSHAKE_SECRET` | — | Shared HMAC-Secret (NAS + Pi identisch) |
| `BALUPI_PIHOLE_URL` | `http://localhost` | Pi-hole Admin-URL |
| `BALUPI_PI_IP` | — | Eigene Pi-IP für DNS-Switch |
| `BALUPI_TAPO_USERNAME` | — | Tapo-Account E-Mail |
| `BALUPI_TAPO_PASSWORD` | — | Tapo-Account Passwort |
| `BALUPI_SECRET_KEY` | — | JWT Signing Key |
| `BALUPI_ENERGY_DEFAULT_PRICE_CENTS` | `32` | Strompreis ct/kWh |

## API Overview

| Endpoint | Beschreibung | Phase |
|---|---|---|
| `GET /api/health` | Health Check | P0 |
| `GET /api/system/status` | Pi CPU, RAM, Temp, Disk | P0 |
| `POST /api/auth/login` | Login via NAS | P0 |
| `GET /api/energy/*` | Energiemessung & Kosten | P1 |
| `GET /api/tapo/*` | Smart Plug Verwaltung | P1 |
| `GET /api/nas/status` | NAS-Status (State Machine) | P2 |
| `POST /api/nas/wol` | Wake-on-LAN mit Power-Check | P2 |
| `POST /api/handshake/nas-going-offline` | NAS meldet sich ab (HMAC) | P2 |
| `POST /api/handshake/nas-coming-online` | NAS meldet sich an (HMAC) | P2 |
| `GET /api/handshake/status` | Handshake-Status & Inbox | P2 |
| `GET /api/handshake/snapshot` | Letzter NAS-Snapshot | P2 |

API-Dokumentation: [docs/api.md](docs/api.md)

## Handshake-Protokoll

Der Pi kontrolliert als DNS-Server den Eintrag `baluhost.local`:

**NAS fährt runter:**
```
NAS → Pi: POST /handshake/nas-going-offline (Snapshot + HMAC)
Pi: Speichert Snapshot, DNS → Pi-IP, State → OFFLINE
```

**NAS fährt hoch:**
```
User → Pi: POST /nas/wol (WoL-Paket senden)
NAS → Pi: POST /handshake/nas-coming-online (HMAC)
Pi: Inbox-Flush (rsync), DNS → NAS-IP, State → ONLINE
```

**Heartbeat:** Pi prüft alle 30s NAS-Health + Tapo-Power. 3× Ausfall → automatischer DNS-Switch.

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI App Factory
│   ├── config.py            # Settings (BALUPI_ Prefix)
│   ├── database.py          # Async SQLAlchemy + SQLite WAL
│   ├── models/              # ORM Models (User, Server, Tapo, Energy)
│   ├── schemas/             # Pydantic Request/Response
│   ├── api/routes/          # Route Modules (health, nas, handshake, energy, tapo, ...)
│   ├── services/            # State Machine, Heartbeat, DNS, Tapo, Energy
│   └── utils/               # WOL, Hashing
├── tests/                   # pytest + pytest-asyncio
└── pyproject.toml
deploy/                      # nginx.conf, balupi.service, install.sh, update.sh
dist/                        # Frontend (von sync_frontend.py deployed)
pi_setup.md                  # Vollständige Pi-Einrichtungsanleitung
BALUPI_PLAN.md               # Projektplan & Architektur
```

## Phasen

| Phase | Scope | Status |
|---|---|---|
| P0 | Foundation (FastAPI, DB, Health, System, Auth) | Done |
| P1 | Energy Monitoring (Tapo, Messung, Kosten) | Done |
| P2 | NAS Handshake (State Machine, Heartbeat, DNS, WoL) | Done |
| P3 | Pi-Frontend & SMB-Share | Next |
| P4 | Snapshot (NAS-Metadaten für View-Only-Dashboard) | Planned |

## Hardware

- Raspberry Pi 3B+ (1 GB RAM, 4x A53 @ 1.4 GHz)
- microSD 32 GB+ (OS)
- USB-SSD 128–512 GB (Daten/Cache)
- 1 TB HDD (SMB-Share)
- Tapo P110/P115 Smart Plugs
- Power: ~3–5W idle (~3 kWh/Monat, ~1 EUR/Monat)

## Related Projects

- [BaluHost](https://github.com/Xveyn/BaluHost) — NAS Backend & Web UI
- [BaluDesk](https://github.com/Xveyn/BaluDesk) — Desktop Sync Client
- [BaluApp](https://github.com/Xveyn/BaluApp) — Android App

## License

MIT
