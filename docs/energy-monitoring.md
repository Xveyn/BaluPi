# Energy Monitoring

## Überblick

BaluPi misst den Stromverbrauch angeschlossener Geräte über Tapo P110/P115 Smart Plugs. Die Daten werden in drei Stufen gespeichert:

```
Tapo P110 ── python-kasa ── BaluPi ── Dashboard
  (30s Poll)                (SQLite)   (React)
                               │
                               ▼
                          Aggregation:
                          • 30s  → energy_samples  (7 Tage)
                          • 1h   → energy_hourly   (1 Jahr)
                          • 1d   → energy_daily    (unbegrenzt)
```

## Unterstützte Geräte

| Modell | Energiemessung | Schalten | Getestet |
|---|---|---|---|
| Tapo P110 | Ja (W, V, A, kWh) | Ja | Ja |
| Tapo P115 | Ja (W, V, A, kWh) | Ja | Geplant |
| Tapo P100 | Nein | Ja | — |

## Geräte-Rollen

Jedes Tapo-Gerät bekommt eine Rolle zugewiesen:

| Rolle | Bedeutung |
|---|---|
| `nas` | NAS-Steckdose — Leistung wird für NAS-Erkennung verwendet |
| `monitor` | Nur Monitoring — z.B. Monitor, Router |
| `generic` | Standard — nur Energiemessung |

Die Rolle `nas` ist besonders wichtig: Über die gemessene Leistung erkennt BaluPi den NAS-Zustand.

## NAS-Erkennung via Leistung

```
Leistung (Watt)    Zustand       Bedeutung
─────────────────────────────────────────────
  0 –   2 W        off          NAS komplett aus
  2 –  15 W        standby      S3 Sleep, WOL möglich
 30 –  60 W        idle         NAS bereit, kein I/O
 60 – 200 W        active       NAS unter Last
```

### Dual-Detection

BaluPi kombiniert zwei Signale für höchste Zuverlässigkeit:

1. **mDNS**: `_baluhost._tcp.local` — direkte Antwort wenn NAS-Software läuft
2. **Tapo Power**: Leistungsmessung des NAS-Plugs

| mDNS | Tapo Power | Konfidenz | Aktion |
|---|---|---|---|
| Online | > 30W | Hoch | NAS verfügbar |
| Online | < 5W | Niedrig | mDNS-Cache? Retry |
| Offline | > 30W | Mittel | NAS bootet noch |
| Offline | < 5W | Hoch | NAS schläft/aus |

## Mess-Intervalle & Speicherverbrauch

| Daten | Intervall | Retention | Speicher (3 Geräte) |
|---|---|---|---|
| Raw Samples | 30 Sekunden | 7 Tage | ~2.4 MB/Woche |
| Stunden-Aggregat | 1 Stunde | 1 Jahr | ~1.6 MB/Jahr |
| Tages-Aggregat | 1 Tag | Unbegrenzt | ~54 KB/Jahr |

Gesamtverbrauch bei 3 Geräten über 1 Jahr: **~20 MB** — vernachlässigbar für SQLite.

## Aggregation

### Stündlich (jede Stunde)

```sql
INSERT OR REPLACE INTO energy_hourly (device_id, hour, avg_power_w, max_power_w, min_power_w, energy_wh, sample_count)
SELECT
    device_id,
    strftime('%Y-%m-%dT%H:00:00', timestamp) as hour,
    AVG(power_mw) / 1000.0,
    MAX(power_mw) / 1000.0,
    MIN(power_mw) / 1000.0,
    SUM(power_mw) / 1000.0 / 120.0,  -- 30s Intervall = 120 Samples/Stunde
    COUNT(*)
FROM energy_samples
WHERE timestamp >= datetime('now', '-2 hours')
GROUP BY device_id, hour;
```

### Täglich (jeden Tag um 00:05)

```sql
INSERT OR REPLACE INTO energy_daily (device_id, date, avg_power_w, max_power_w, min_power_w, energy_wh, cost_cents)
SELECT
    device_id,
    date(hour) as date,
    AVG(avg_power_w),
    MAX(max_power_w),
    MIN(min_power_w),
    SUM(energy_wh),
    SUM(energy_wh) / 1000.0 * (SELECT price_per_kwh_cents FROM energy_price_config WHERE is_active = 1 LIMIT 1)
FROM energy_hourly
WHERE hour >= datetime('now', '-2 days')
GROUP BY device_id, date;
```

### Cleanup (täglich)

```sql
DELETE FROM energy_samples WHERE timestamp < datetime('now', '-7 days');
```

## Kostenberechnung

Kosten werden pro Gerät und Tag berechnet:

```
Kosten (ct) = Verbrauch (kWh) × Strompreis (ct/kWh)
```

Der Strompreis ist konfigurierbar über die `energy_price_config`-Tabelle. Mehrere Tarife möglich (z.B. Tag/Nacht).

### Beispielrechnung

```
NAS im Idle:     45W × 24h = 1.08 kWh/Tag × 32 ct/kWh = 34.6 ct/Tag = ~10.37 EUR/Monat
NAS aus, Pi an:   4W × 24h = 0.096 kWh/Tag × 32 ct/kWh = 3.1 ct/Tag = ~0.93 EUR/Monat
Ersparnis:                                                              ~9.44 EUR/Monat
```

## API-Endpoints

| Endpoint | Beschreibung |
|---|---|
| `GET /api/energy/current` | Aktuelle Leistung aller Geräte |
| `GET /api/energy/history?period=day` | Historische Daten |
| `GET /api/energy/costs?period=month` | Kostenberechnung |
| `GET /api/energy/summary` | Gesamtübersicht + NAS-State |
| `GET /api/tapo/devices` | Geräteliste |
| `POST /api/tapo/devices/discover` | Netzwerk-Scan |
| `PUT /api/tapo/devices/{id}` | Gerät konfigurieren |
| `POST /api/tapo/devices/{id}/toggle` | Ein-/Ausschalten |

## Konfiguration

```env
# Tapo-Account (TP-Link Cloud Login)
BALUPI_TAPO_USERNAME=email@example.com
BALUPI_TAPO_PASSWORD=password

# Messintervall (Standard: 30 Sekunden)
BALUPI_ENERGY_SAMPLE_INTERVAL_SECONDS=30

# Strompreis (Standard: 32 ct/kWh)
BALUPI_ENERGY_DEFAULT_PRICE_CENTS=32.0

# NAS-Erkennung Schwellenwert
BALUPI_NAS_POWER_THRESHOLD_WATTS=30.0
```

## python-kasa Verwendung

```python
from kasa import Discover, SmartPlug

# Alle Tapo-Geräte im Netzwerk finden
devices = await Discover.discover()

# Einzelnes Gerät abfragen
plug = SmartPlug("192.168.178.60")
await plug.update()

# Energiedaten lesen
emeter = plug.emeter_realtime
power_w = emeter["power_mw"] / 1000.0
voltage_v = emeter["voltage_mv"] / 1000.0
current_a = emeter["current_ma"] / 1000.0
```
