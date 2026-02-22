# BaluPi Architektur

## System-Kontext

BaluPi sitzt als Smart-Cache-Tier zwischen den Clients und dem BaluHost NAS:

```
┌──────────────────────────────────────────────────────────┐
│                       LAN (Wi-Fi / Ethernet)             │
│                                                          │
│  ┌──────────┐   ┌──────────┐            ┌──────────┐    │
│  │ BaluApp  │   │ BaluDesk │            │ BaluHost │    │
│  │ (Handy)  │   │ (Desktop)│            │  (NAS)   │    │
│  └────┬─────┘   └────┬─────┘            └────┬─────┘    │
│       │               │                      │          │
│       └───────┬───────┘                      │          │
│               ▼                              │          │
│          ┌─────────┐    REST / WOL           │          │
│          │ BaluPi  │ ◄──────────────────────►│          │
│          │ (Pi 3B+)│                         │          │
│          └─────────┘                         │          │
│           4W always-on              50-120W on-demand   │
└──────────────────────────────────────────────────────────┘
```

## Interne Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                    │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │                  API Layer                        │    │
│  │  health │ system │ auth │ energy │ tapo │ files  │    │
│  │  cache  │ nas    │ sync                          │    │
│  └──────────────────┬───────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────┴───────────────────────────────┐    │
│  │               Service Layer                       │    │
│  │  AuthService     │ EnergyService │ TapoService   │    │
│  │  CacheService    │ SyncService   │ NasService    │    │
│  │  UploadService   │ Scheduler     │               │    │
│  └──────────────────┬───────────────────────────────┘    │
│                     │                                    │
│  ┌──────────────────┴───────────────┐  ┌─────────────┐  │
│  │          Data Layer              │  │  External    │  │
│  │  SQLAlchemy Models (async)       │  │  httpx→NAS   │  │
│  │  SQLite WAL (aiosqlite)          │  │  kasa→Tapo   │  │
│  │                                  │  │  WOL→NAS     │  │
│  └──────────────────────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Schicht-Beschreibung

### API Layer (`app/api/routes/`)

FastAPI-Router, die HTTP-Requests entgegennehmen und an Services delegieren. Jeder Router entspricht einem Feature-Bereich. Dependency Injection über `app/api/deps.py` für Auth und DB-Sessions.

### Service Layer (`app/services/`)

Geschäftslogik, entkoppelt von HTTP. Services verwenden:
- **AsyncSession** für DB-Zugriff
- **httpx.AsyncClient** für NAS-Kommunikation
- **python-kasa** für Tapo-Geräte
- **APScheduler** für periodische Jobs

### Data Layer (`app/models/`, `app/database.py`)

SQLAlchemy 2.0 async ORM mit SQLite im WAL-Modus. Optimiert für den Pi:
- Max 5 DB-Connections
- 8 MB Cache, 32 MB mmap
- `PRAGMA synchronous=NORMAL` (schneller, WAL schützt vor Corruption)

### External Integrations

| Integration | Protokoll | Bibliothek |
|---|---|---|
| BaluHost NAS | REST/HTTP | httpx |
| Tapo Smart Plugs | Proprietär (TCP) | python-kasa |
| NAS Wake-on-LAN | UDP Magic Packet | Custom (`utils/wol.py`) |
| NAS Discovery | mDNS | zeroconf |

## Datenflüsse

### 1. Client-Request (Cache Hit)

```
Client ── GET /api/files/download/123 ──► BaluPi
                                           │
                                    [cached_files lookup]
                                           │
                                    ◄── 200 + File Stream ──
```

### 2. Client-Request (Cache Miss, NAS online)

```
Client ── GET /api/files/download/456 ──► BaluPi
                                           │
                                    [cached_files lookup → miss]
                                           │
                                    BaluPi ── GET /api/files/456 ──► NAS
                                           │                          │
                                           ◄── File Stream ───────────
                                           │
                                    [cache lokal + update cached_files]
                                           │
                                    ◄── 200 + File Stream ──
```

### 3. Mobile Upload

```
BaluApp ── POST /api/files/upload ──► BaluPi
                                       │
                                [Datei in cache_dir speichern]
                                [upload_queue Eintrag erstellen]
                                       │
                                ◄── 200 OK ──
                                       │
                           [Background: NAS online?]
                                       │
                              Ja ──► Sync zu NAS ──► NAS
                              Nein ─► Queue bleibt
```

### 4. Energy Monitoring

```
APScheduler (30s) ──► TapoService.poll_all()
                        │
                  [python-kasa → Tapo P110]
                        │
                  [energy_samples INSERT]
                        │
APScheduler (1h) ──► aggregate_hourly()
                        │
                  [energy_hourly UPSERT]
                        │
APScheduler (1d) ──► aggregate_daily() + cleanup_raw()
                        │
                  [energy_daily UPSERT]
                  [DELETE energy_samples WHERE age > 7d]
```

## Datenbank-Schema (Übersicht)

```
users ─────────────── Gecachte Auth-Daten vom NAS
servers ──────────── NAS-Verbindungsprofile
cached_files ──────── Lokal gecachte Dateien
upload_queue ──────── Ausstehende NAS-Uploads
sync_log ─────────── Sync-Operationshistorie
conflicts ─────────── Datei-Konflikte
file_metadata_cache ─ NAS-Dateiindex (Metadaten)
tapo_devices ──────── Smart Plug Geräte
energy_samples ────── Rohdaten (30s, 7d Retention)
energy_hourly ─────── Stunden-Aggregat (1 Jahr)
energy_daily ──────── Tages-Aggregat (unbegrenzt)
energy_price_config ─ Stromtarife
```

Vollständiges Schema: siehe `app/models/` oder [balupi-plan.md](../balupi-plan.md#5-datenbank-schema).

## Hardware-Constraints (Pi 3B+)

| Ressource | Limit | Strategie |
|---|---|---|
| RAM | 1 GB | 1 Uvicorn Worker, Streaming für große Dateien |
| CPU | 4x A53 @ 1.4 GHz | Kein Heavy Processing, Thumbnails limitiert |
| USB 2.0 → SSD | ~35 MB/s | Nicht der Bottleneck bei LAN-Sync |
| Netzwerk | ~300 Mbit/s | Ausreichend für LAN |
| Power | ~4W idle | ~1 kWh/Monat ≈ 0.30 EUR/Monat |

## BaluHost API-Kompatibilität

BaluPi implementiert eine Teilmenge der BaluHost-API. Clients (BaluApp, BaluDesk) können transparent zwischen Pi und NAS wechseln:

| Endpoint | BaluHost | BaluPi |
|---|---|---|
| `GET /api/health` | Ja | Ja |
| `POST /api/auth/login` | Ja | Ja (Forward) |
| `GET /api/files/list` | Ja | Ja (Cache + Metadata) |
| `GET /api/files/download/{id}` | Ja | Ja (Cache-Hit oder Proxy) |
| `POST /api/files/upload` | Ja | Ja (Cache + Queue) |
| `GET /api/shares/*` | Ja | Nein |
| `GET /api/admin/*` | Ja | Nein |

Pi-exklusive Endpoints: `/api/energy/*`, `/api/tapo/*`, `/api/system/status`, `/api/cache/stats`, `/api/nas/wol`.

## Sicherheit

- **Auth-Forwarding**: Pi validiert Tokens gegen NAS, cached Ergebnis lokal
- **Kein eigener User-Store**: Alle Nutzer werden über NAS verwaltet
- **CORS**: Konfigurierbar via `BALUPI_CORS_ORIGINS`
- **Secret Key**: Pflicht in Production (Validierung in `config.py`)
- **systemd Hardening**: NoNewPrivileges, ProtectSystem, ProtectHome, PrivateTmp
