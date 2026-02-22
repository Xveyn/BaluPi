# BaluPi API-Dokumentation

Base URL: `http://<pi-ip>:8000/api`

Interaktive Docs: `http://<pi-ip>:8000/docs` (Swagger UI, automatisch von FastAPI generiert)

---

## Health & System

### `GET /api/health`

Health Check — kompatibel mit BaluHost. Wird von BaluApp/BaluDesk zur Server-Erkennung verwendet.

**Response 200:**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "service": "balupi",
  "cache_enabled": true,
  "energy_enabled": true
}
```

### `GET /api/ping`

Ultra-Lightweight Ping für Connectivity-Tests.

**Response 200:**
```json
{ "status": "ok" }
```

### `GET /api/system/status`

Raspberry Pi Systemressourcen.

**Response 200:**
```json
{
  "cpu_percent": 12.3,
  "cpu_temp_celsius": 42.5,
  "memory_total_mb": 926.1,
  "memory_used_mb": 312.4,
  "memory_percent": 33.7,
  "disk_total_gb": 238.47,
  "disk_used_gb": 45.12,
  "disk_percent": 18.9,
  "uptime_seconds": 86400.0,
  "load_avg": [0.52, 0.41, 0.38]
}
```

---

## Authentication

### `POST /api/auth/login`

Login — wird an NAS weitergeleitet. BaluPi verwaltet keine eigenen User.

**Request:**
```json
{
  "username": "admin",
  "password": "secret"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Response 503** (NAS nicht erreichbar):
```json
{
  "detail": "NAS is not reachable. Login requires NAS connectivity."
}
```

---

## Energy Monitoring (P1)

### `GET /api/energy/current`

Aktuelle Leistungswerte aller Tapo-Geräte.

**Response 200:**
```json
{
  "devices": [
    {
      "device_id": "abc123",
      "device_name": "NAS Plug",
      "power_w": 45.2,
      "voltage_v": 230.1,
      "current_a": 0.196,
      "is_online": true,
      "timestamp": "2026-02-22T14:30:00"
    }
  ],
  "total_power_w": 45.2
}
```

### `GET /api/energy/history`

Historische Energiedaten.

**Query Parameters:**
- `device_id` (optional) — Filter auf ein Gerät
- `period` — `day` | `week` | `month` (default: `day`)

**Response 200:**
```json
{
  "device_id": "abc123",
  "device_name": "NAS Plug",
  "period": "day",
  "data": [
    {
      "timestamp": "2026-02-22T00:00:00",
      "avg_power_w": 42.3,
      "max_power_w": 95.1,
      "min_power_w": 3.2,
      "energy_wh": 42.3
    }
  ]
}
```

### `GET /api/energy/costs`

Kostenberechnung.

**Query Parameters:**
- `device_id` (optional)
- `period` — `day` | `week` | `month` (default: `month`)

**Response 200:**
```json
{
  "device_id": "abc123",
  "period": "month",
  "total_kwh": 32.5,
  "cost_cents": 1040,
  "price_per_kwh_cents": 32.0
}
```

### `GET /api/energy/summary`

Gesamtübersicht aller Geräte.

**Response 200:**
```json
{
  "total_devices": 3,
  "total_power_w": 67.8,
  "avg_daily_kwh": 1.63,
  "monthly_cost_estimate_cents": 1566,
  "nas_state": "idle"
}
```

---

## Tapo Smart Plugs (P1)

### `GET /api/tapo/devices`

Liste aller bekannten Tapo-Geräte.

**Response 200:**
```json
[
  {
    "id": "abc123",
    "name": "NAS Plug",
    "ip_address": "192.168.178.60",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "model": "P110",
    "role": "nas",
    "is_online": true,
    "firmware": "1.3.0",
    "last_seen": "2026-02-22T14:30:00"
  }
]
```

### `POST /api/tapo/devices/discover`

Netzwerk nach Tapo-Geräten scannen.

**Response 200:**
```json
{
  "discovered": 3,
  "new_devices": 1,
  "devices": [...]
}
```

### `PUT /api/tapo/devices/{device_id}`

Gerät konfigurieren.

**Request:**
```json
{
  "name": "NAS Plug",
  "role": "nas"
}
```

Gültige Rollen: `nas`, `monitor`, `generic`

### `POST /api/tapo/devices/{device_id}/toggle`

Gerät ein-/ausschalten.

**Response 200:**
```json
{ "success": true, "new_state": "on" }
```

---

## NAS Management (P2)

### `GET /api/nas/status`

NAS-Erreichbarkeit prüfen.

**Response 200:**
```json
{
  "online": true,
  "version": "1.8.2",
  "url": "http://192.168.178.53"
}
```

### `POST /api/nas/wol`

Wake-on-LAN Magic Packet an NAS senden.

**Response 200:**
```json
{ "success": true, "mac_address": "AA:BB:CC:DD:EE:FF" }
```

---

## Files & Cache (P3)

### `GET /api/files/list`

Dateiliste — kombiniert gecachte Metadaten mit NAS-Index.

**Query Parameters:**
- `path` — Verzeichnispfad (default: `/`)

**Response 200:**
```json
{
  "path": "/photos",
  "files": [
    {
      "id": "file123",
      "filename": "vacation.jpg",
      "relative_path": "/photos/vacation.jpg",
      "mime_type": "image/jpeg",
      "size_bytes": 4521340,
      "is_directory": false,
      "modified_at": "2026-02-20T10:15:00",
      "is_cached": true
    }
  ]
}
```

### `GET /api/files/download/{file_id}`

Datei herunterladen. Cache-Hit liefert lokal, Cache-Miss proxyt zum NAS.

**Response 200:** File Stream mit Content-Type Header

**Response 404:** Datei nicht gefunden (weder Cache noch NAS)

**Response 503:** NAS nicht erreichbar und nicht im Cache

### `POST /api/files/upload`

Datei hochladen. Wird lokal gespeichert und der NAS-Sync gequeued.

**Request:** `multipart/form-data` mit Datei

**Response 200:**
```json
{
  "id": "upload123",
  "filename": "document.pdf",
  "size_bytes": 1234567,
  "status": "queued"
}
```

### `GET /api/files/sync/status`

Aktueller Sync-Status.

**Response 200:**
```json
{
  "is_syncing": false,
  "pending_uploads": 3,
  "pending_downloads": 0,
  "conflicts": 0,
  "nas_online": true
}
```

### `GET /api/cache/stats`

Cache-Nutzungsstatistiken.

**Response 200:**
```json
{
  "total_files": 1247,
  "total_size_mb": 45230.5,
  "max_size_gb": 200.0,
  "usage_percent": 22.1,
  "dirty_files": 3,
  "hit_rate_percent": 87.3
}
```

---

## Authentifizierung

Alle Endpoints außer `/api/health`, `/api/ping` und `/api/auth/login` erfordern einen Bearer Token:

```
Authorization: Bearer eyJ...
```

Der Token wird über `/api/auth/login` (Forward an NAS) bezogen. BaluPi validiert Tokens gegen den NAS und cached das Ergebnis lokal.

## Fehler-Responses

Alle Fehler folgen dem Standard-Format:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Bedeutung |
|---|---|
| 400 | Ungültige Request-Parameter |
| 401 | Fehlender oder ungültiger Token |
| 403 | Keine Berechtigung |
| 404 | Ressource nicht gefunden |
| 503 | NAS nicht erreichbar |
