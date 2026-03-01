# BaluPi — Raspberry Pi Einrichtung

Komplettanleitung zur Einrichtung eines Raspberry Pi 3B+ als BaluPi-Node (Smart Cache & Energy Monitor).

---

## Inhaltsverzeichnis

1. [Hardware-Voraussetzungen](#hardware-voraussetzungen)
2. [OS-Vorbereitung](#os-vorbereitung)
3. [USB-SSD einrichten](#usb-ssd-einrichten)
4. [Statische IP](#statische-ip)
5. [Installation](#installation)
6. [Konfiguration](#konfiguration)
7. [nginx (Reverse Proxy)](#nginx-reverse-proxy)
8. [systemd Service](#systemd-service)
9. [Frontend-Sync](#frontend-sync)
10. [SSH-Key für rsync](#ssh-key-für-rsync)
11. [Firewall](#firewall)
12. [Monitoring](#monitoring)
13. [Backup](#backup)
14. [Updates](#updates)
15. [Troubleshooting](#troubleshooting)
16. [Verifizierung](#verifizierung)

---

## Hardware-Voraussetzungen

| Komponente | Empfehlung |
|---|---|
| Raspberry Pi | 3B+ oder neuer |
| microSD | 32 GB+ mit Raspberry Pi OS Lite (Bookworm, 64-bit) |
| USB-SSD | 128–512 GB für Cache/Daten |
| Netzwerk | Ethernet (empfohlen) oder Wi-Fi |
| Tapo Smart Plugs | P110 oder P115 (für Energy Monitoring) |

---

## OS-Vorbereitung

### Headless SSH aktivieren

```bash
touch /boot/ssh
```

### Wi-Fi konfigurieren (optional)

```bash
cat > /boot/wpa_supplicant.conf << 'EOF'
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="DEIN_WLAN"
    psk="DEIN_PASSWORT"
}
EOF
```

### System aktualisieren

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv python3-pip
```

### Python 3.11+ sicherstellen

```bash
python3 --version
# Falls < 3.11: aus Source bauen oder Deadsnakes PPA verwenden
```

---

## USB-SSD einrichten

```bash
# SSD identifizieren
lsblk

# Formatieren (falls nötig)
sudo mkfs.ext4 /dev/sda1

# Mountpoint erstellen
sudo mkdir -p /mnt/ssd

# Automount via fstab (noatime für weniger Schreibzugriffe)
echo '/dev/sda1 /mnt/ssd ext4 defaults,noatime 0 2' | sudo tee -a /etc/fstab
sudo mount -a

# Verzeichnis für BaluPi
sudo mkdir -p /mnt/ssd/balupi
sudo chown pi:pi /mnt/ssd/balupi
```

---

## Statische IP

```bash
sudo nano /etc/dhcpcd.conf
```

Eintragen:

```
interface eth0
static ip_address=192.168.178.100/24
static routers=192.168.178.1
static domain_name_servers=192.168.178.1
```

Danach `sudo reboot` oder `sudo systemctl restart dhcpcd`.

---

## Installation

### Automatisch (empfohlen)

Das Install-Script installiert alle Abhängigkeiten, klont das Repo, richtet venv, systemd und nginx ein:

```bash
curl -sSL https://raw.githubusercontent.com/Xveyn/BaluPi/main/deploy/install.sh | bash
```

### Manuell

```bash
# 1. System-Pakete
sudo apt-get install -y git python3-venv python3-pip nginx

# 2. Repo klonen
sudo mkdir -p /opt/balupi
sudo chown $USER:$USER /opt/balupi
git clone https://github.com/Xveyn/BaluPi.git /opt/balupi
cd /opt/balupi

# 3. Python venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e "./backend[dev]"

# 4. Datenverzeichnisse
mkdir -p data/{cache/files,cache/thumbnails,logs}

# Optional: Daten auf SSD auslagern
# ln -s /mnt/ssd/balupi/data /opt/balupi/data

# 5. Konfiguration
cp .env.example .env
nano .env
```

---

## Konfiguration

Alle Einstellungen werden über Umgebungsvariablen mit `BALUPI_`-Prefix gesteuert. Die `.env`-Datei liegt unter `/opt/balupi/.env`.

### Vollständige Variablen-Referenz

```env
# === Allgemein ===
BALUPI_DEBUG=false                  # Debug-Modus (Produktion: false)
BALUPI_LOG_LEVEL=INFO               # Log-Level: DEBUG, INFO, WARNING, ERROR
BALUPI_MODE=prod                    # "dev" = Mock-Daten, "prod" = echte Hardware

# === Netzwerk ===
BALUPI_HOST=127.0.0.1               # Bind-Adresse (127.0.0.1 da nginx davor)
BALUPI_PORT=8000                    # Interner Port (nicht direkt exponiert)

# === Auth ===
BALUPI_SECRET_KEY=<generieren>      # python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# === NAS-Verbindung ===
BALUPI_NAS_URL=http://192.168.178.53  # BaluHost URL
BALUPI_NAS_MAC_ADDRESS=AA:BB:CC:DD:EE:FF  # Für Wake-on-LAN
BALUPI_NAS_USERNAME=admin
BALUPI_NAS_PASSWORD=

# === NAS erweitert (Handshake & rsync) ===
BALUPI_NAS_IP=192.168.178.53       # NAS-IP für DNS-Umschaltung
BALUPI_NAS_INBOX_PATH=/data/inbox  # NAS-seitiger Inbox-Pfad für rsync
BALUPI_NAS_SSH_USER=baluhost       # SSH-User für rsync (Pi → NAS)

# === Handshake (NAS ↔ Pi HMAC-Auth) ===
BALUPI_HANDSHAKE_SECRET=           # Shared HMAC-Secret (32+ Zeichen)

# === Pi-hole DNS-Umschaltung ===
BALUPI_PIHOLE_URL=http://localhost  # Pi-hole Admin-URL
BALUPI_PIHOLE_PASSWORD=             # Pi-hole Admin-Passwort
BALUPI_PI_IP=192.168.178.100        # Eigene Pi-IP (für DNS-Switch)

# === Speicher ===
BALUPI_DATA_DIR=/mnt/ssd/balupi/data
BALUPI_CACHE_DIR=/mnt/ssd/balupi/data/cache/files
BALUPI_THUMBNAIL_DIR=/mnt/ssd/balupi/data/cache/thumbnails
BALUPI_DATABASE_PATH=/mnt/ssd/balupi/data/balupi.db

# === Energy Monitoring ===
BALUPI_ENERGY_SAMPLE_INTERVAL_SECONDS=30    # Messintervall in Sekunden
BALUPI_ENERGY_DEFAULT_PRICE_CENTS=32.0      # Strompreis ct/kWh

# === Tapo Smart Plugs ===
BALUPI_TAPO_USERNAME=deine-email@example.com
BALUPI_TAPO_PASSWORD=dein-tapo-passwort

# === NAS Power Detection ===
BALUPI_NAS_POWER_THRESHOLD_WATTS=30.0  # Schwellwert: NAS an/aus
```

### Wichtige Hinweise

- `BALUPI_MODE=prod` setzen auf dem Pi (sonst werden Mock-Daten verwendet)
- `BALUPI_HOST=127.0.0.1` — Uvicorn bindet nur lokal, nginx macht den Reverse Proxy
- `BALUPI_SECRET_KEY` **muss** generiert werden (nicht den Default verwenden)
- `BALUPI_HANDSHAKE_SECRET` muss auf Pi **und** NAS identisch sein

---

## nginx (Reverse Proxy)

nginx sitzt vor Uvicorn auf Port 80 und übernimmt Gzip-Kompression sowie Asset-Caching.

### Konfiguration installieren

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/balupi
sudo ln -sf /etc/nginx/sites-available/balupi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### Was nginx macht

- **Port 80** — Einziger exponierter Port (kein 8000 nach außen)
- **`/assets/`** — Statische Frontend-Assets direkt aus `/opt/balupi/dist/assets/` mit 1 Jahr Cache (`immutable`)
- **`/` (Rest)** — Proxy zu Uvicorn auf `127.0.0.1:8000` (API + SPA-Fallback)
- **Gzip** — Komprimiert CSS, JS, JSON, SVG
- **Timeouts** — 10s Connect, 60s Read/Send (für langsamen Pi)

### nginx-Konfiguration (`deploy/nginx.conf`)

```nginx
upstream balupi {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name balupi.local _;

    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 256;

    location /assets/ {
        alias /opt/balupi/dist/assets/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    location / {
        proxy_pass http://balupi;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

---

## systemd Service

### Service installieren

```bash
sudo cp deploy/balupi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable balupi
sudo systemctl start balupi
```

### Service-Details (`deploy/balupi.service`)

- **User:** `pi`
- **WorkingDirectory:** `/opt/balupi/backend`
- **ExecStart:** Uvicorn auf `127.0.0.1:8000` mit 1 Worker
- **EnvironmentFile:** `/opt/balupi/.env`
- **Watchdog:** `WatchdogSec=30` — automatischer Neustart bei Nicht-Antwort
- **Restart:** `always` mit 5s Pause, max 5 Versuche pro 60s
- **Security Hardening:** `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`
- **Schreibrechte:** nur `/opt/balupi/data` und `/opt/balupi/backend/data`

---

## Frontend-Sync

Das Pi-Frontend wird auf dem NAS gebaut und als fertige statische Dateien deployed. Kein Node.js auf dem Pi nötig.

### Bevorzugte Methode: Von Git-Branch

```bash
cd /opt/balupi
source .venv/bin/activate
python3 sync_frontend.py --from-branch frontend
```

Holt pre-built Assets aus dem `frontend`-Branch (gepusht von BaluHost GitHub Actions).

### Alternative: Von lokaler BaluHost-Source

```bash
python3 sync_frontend.py --source ../BaluHost/client
```

Benötigt Node.js >= 18.

### Ergebnis

Frontend landet in `/opt/balupi/dist/` und wird von nginx (`/assets/`) und FastAPI (SPA-Fallback) ausgeliefert.

---

## SSH-Key für rsync

Für den Inbox-Flush (Pi → NAS) braucht der Pi passwortlosen SSH-Zugang zum NAS.

```bash
# 1. SSH-Key generieren (als User pi)
ssh-keygen -t ed25519 -C "balupi-rsync" -f ~/.ssh/id_balupi -N ""

# 2. Public Key auf NAS kopieren
ssh-copy-id -i ~/.ssh/id_balupi.pub baluhost@192.168.178.53

# 3. Testen
ssh -i ~/.ssh/id_balupi baluhost@192.168.178.53 "echo OK"

# 4. SSH-Config (optional, vereinfacht rsync-Aufrufe)
cat >> ~/.ssh/config << 'EOF'
Host baluhost-nas
    HostName 192.168.178.53
    User baluhost
    IdentityFile ~/.ssh/id_balupi
EOF
```

Der Handshake-Service nutzt diesen Key für `rsync --remove-source-files` beim Inbox-Flush.

---

## Firewall

```bash
sudo apt install -y ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # nginx (HTTP)
sudo ufw allow 53        # DNS (Pi-hole, TCP + UDP)
sudo ufw enable
```

**Wichtig:** Port 8000 wird **nicht** freigegeben — Uvicorn ist nur lokal erreichbar, nginx macht den Proxy auf Port 80.

---

## Monitoring

### Systemd Watchdog

Der Service hat `WatchdogSec=30`. Bei Nicht-Antwort startet systemd automatisch neu.

### Log-Rotation

```bash
cat > /etc/logrotate.d/balupi << 'EOF'
/opt/balupi/data/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

### Temperatur-Überwachung

```bash
# Manuell
vcgencmd measure_temp

# Via API
curl -s http://localhost/api/system/status | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['cpu_temp_celsius'])"
```

---

## Backup

### SQLite-DB sichern (WAL-safe)

```bash
mkdir -p /mnt/ssd/balupi/backups
sqlite3 /mnt/ssd/balupi/data/balupi.db \
  ".backup /mnt/ssd/balupi/backups/balupi-$(date +%Y%m%d).db"
```

### Cronjob für tägliches Backup

```bash
crontab -e
```

Zeile hinzufügen:

```
0 3 * * * sqlite3 /mnt/ssd/balupi/data/balupi.db ".backup /mnt/ssd/balupi/backups/balupi-$(date +\%Y\%m\%d).db" && find /mnt/ssd/balupi/backups -name "balupi-*.db" -mtime +7 -delete
```

Tägliches Backup um 03:00, alte Backups nach 7 Tagen gelöscht.

---

## Updates

### Automatisch (empfohlen)

```bash
bash /opt/balupi/deploy/update.sh
```

Das Script macht:
1. `git pull --ff-only`
2. `pip install -e "./backend"` (Abhängigkeiten aktualisieren)
3. `sync_frontend.py --from-branch frontend` (Frontend aktualisieren)
4. `systemctl restart balupi`
5. `nginx -t && systemctl reload nginx`

### Manuell

```bash
cd /opt/balupi
git pull
source .venv/bin/activate
pip install -e "./backend"
python3 sync_frontend.py --from-branch frontend
sudo systemctl restart balupi
sudo nginx -t && sudo systemctl reload nginx
```

---

## Troubleshooting

### Service startet nicht

```bash
# Logs prüfen
sudo journalctl -u balupi -n 50 --no-pager

# Manuell starten (zeigt Fehler direkt)
cd /opt/balupi/backend
/opt/balupi/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Datenbank-Probleme

```bash
# WAL-Modus prüfen (Erwartung: "wal")
sqlite3 /mnt/ssd/balupi/data/balupi.db "PRAGMA journal_mode;"

# Integrität prüfen
sqlite3 /mnt/ssd/balupi/data/balupi.db "PRAGMA integrity_check;"
```

### Tapo-Geräte nicht erreichbar

```bash
# Netzwerk prüfen
ping 192.168.178.60  # IP des Tapo-Plugs

# python-kasa Test
/opt/balupi/.venv/bin/kasa discover
```

### Frontend wird nicht angezeigt

```bash
# Prüfen ob dist/ existiert
ls -la /opt/balupi/dist/

# Frontend neu syncen
cd /opt/balupi
source .venv/bin/activate
python3 sync_frontend.py --from-branch frontend

# nginx-Konfig prüfen
sudo nginx -t
sudo systemctl status nginx
```

### Hohe CPU-Last

- Uvicorn Worker ist auf 1 limitiert (Default)
- Energy-Intervall erhöhen: `BALUPI_ENERGY_SAMPLE_INTERVAL_SECONDS=60`
- Thumbnail-Generierung deaktivieren falls nötig

### Manueller Start ohne systemd

```bash
cd /opt/balupi/backend
source /opt/balupi/.venv/bin/activate
export $(cat /opt/balupi/.env | grep -v '^#' | xargs)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Verifizierung

Nach abgeschlossener Einrichtung alle Endpunkte über nginx (Port 80) testen:

```bash
# Health Check
curl http://localhost/api/health

# Ping
curl http://localhost/api/ping

# System-Status (CPU, RAM, Temp)
curl http://localhost/api/system/status

# NAS-Status
curl http://localhost/api/nas/status

# Energy (wenn Tapo konfiguriert)
curl http://localhost/api/energy/current

# Frontend (sollte HTML zurückgeben)
curl -s http://localhost/ | head -5

# Von einem anderen Gerät im Netzwerk
curl http://192.168.178.100/api/health
curl http://balupi.local/api/health
```
