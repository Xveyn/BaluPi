# BaluPi Deployment auf Raspberry Pi

## Voraussetzungen

### Hardware
- Raspberry Pi 3B+ (oder neuer)
- microSD-Karte (32 GB+) mit Raspberry Pi OS Lite
- USB-SSD (128–512 GB empfohlen) für Cache-Storage
- Ethernet-Kabel (empfohlen) oder Wi-Fi
- Tapo P110/P115 Smart Plugs (für Energy Monitoring)

### Software
- Raspberry Pi OS Lite (Bookworm, 64-bit empfohlen)
- Python 3.11+
- Git

## Installation

### 1. Pi OS vorbereiten

```bash
# SSH aktivieren (bei headless setup)
touch /boot/ssh

# Wi-Fi konfigurieren (optional)
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

### 2. System aktualisieren

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv python3-pip
```

### 3. Python 3.11+ sicherstellen

```bash
python3 --version
# Falls < 3.11: aus Source bauen oder Deadsnakes PPA verwenden
```

### 4. USB-SSD einrichten

```bash
# SSD identifizieren
lsblk

# Formatieren (falls nötig)
sudo mkfs.ext4 /dev/sda1

# Mountpoint erstellen
sudo mkdir -p /mnt/ssd

# Automount via fstab
echo '/dev/sda1 /mnt/ssd ext4 defaults,noatime 0 2' | sudo tee -a /etc/fstab
sudo mount -a

# Verzeichnis für BaluPi
sudo mkdir -p /mnt/ssd/balupi
sudo chown pi:pi /mnt/ssd/balupi
```

### 5. BaluPi installieren

**Automatisch:**
```bash
curl -sSL https://raw.githubusercontent.com/Xveyn/BaluPi/main/deploy/install.sh | bash
```

**Manuell:**
```bash
git clone https://github.com/Xveyn/BaluPi.git /opt/balupi
cd /opt/balupi
python3 -m venv .venv
source .venv/bin/activate
pip install -e "./backend"

# Datenverzeichnisse
mkdir -p data/{cache/files,cache/thumbnails,logs}

# Oder auf SSD:
ln -s /mnt/ssd/balupi/data /opt/balupi/data
```

### 6. Konfiguration

```bash
cp .env.example .env
nano .env
```

Wichtige Einstellungen:
```env
BALUPI_NAS_URL=http://192.168.178.53
BALUPI_NAS_MAC_ADDRESS=AA:BB:CC:DD:EE:FF
BALUPI_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(32))">
BALUPI_TAPO_USERNAME=deine-email@example.com
BALUPI_TAPO_PASSWORD=dein-tapo-passwort
BALUPI_DATA_DIR=/mnt/ssd/balupi/data
BALUPI_CACHE_DIR=/mnt/ssd/balupi/data/cache/files
BALUPI_DATABASE_PATH=/mnt/ssd/balupi/data/balupi.db
```

### 7. systemd Service einrichten

```bash
sudo cp deploy/balupi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable balupi
sudo systemctl start balupi
```

### 8. Verifizieren

```bash
# Service-Status
sudo systemctl status balupi

# Health Check
curl http://localhost:8000/api/health

# System-Status
curl http://localhost:8000/api/system/status

# Logs
sudo journalctl -u balupi -f
```

## Updates

### Automatisch

```bash
bash /opt/balupi/deploy/update.sh
```

### Manuell

```bash
cd /opt/balupi
git pull
source .venv/bin/activate
pip install -e "./backend"
sudo systemctl restart balupi
```

## Netzwerk

### Feste IP (empfohlen)

```bash
sudo nano /etc/dhcpcd.conf
```

```
interface eth0
static ip_address=192.168.178.100/24
static routers=192.168.178.1
static domain_name_servers=192.168.178.1
```

### Firewall (optional)

```bash
sudo apt install ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # BaluPi API
sudo ufw enable
```

## Monitoring

### Systemd Watchdog

Der Service ist mit `WatchdogSec=30` konfiguriert. Bei Nicht-Antwort startet systemd automatisch neu.

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
curl -s http://localhost:8000/api/system/status | python3 -c "import sys,json; print(json.load(sys.stdin)['cpu_temp_celsius'])"
```

## Troubleshooting

### Service startet nicht

```bash
# Logs prüfen
sudo journalctl -u balupi -n 50 --no-pager

# Manuell starten
cd /opt/balupi/backend
/opt/balupi/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Datenbank-Probleme

```bash
# WAL-Modus prüfen
sqlite3 /mnt/ssd/balupi/data/balupi.db "PRAGMA journal_mode;"
# Sollte "wal" ausgeben

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

### Hohe CPU-Last

- Uvicorn Worker auf 1 limitiert (default)
- Energy-Intervall ggf. auf 60s erhöhen: `BALUPI_ENERGY_SAMPLE_INTERVAL_SECONDS=60`
- Thumbnail-Generierung deaktivieren falls nötig

## Backup

### SQLite-DB sichern

```bash
# Hot-Backup (WAL-safe)
sqlite3 /mnt/ssd/balupi/data/balupi.db ".backup /mnt/ssd/balupi/backups/balupi-$(date +%Y%m%d).db"
```

### Cronjob für tägliches Backup

```bash
crontab -e
# Hinzufügen:
0 3 * * * sqlite3 /mnt/ssd/balupi/data/balupi.db ".backup /mnt/ssd/balupi/backups/balupi-$(date +\%Y\%m\%d).db" && find /mnt/ssd/balupi/backups -name "balupi-*.db" -mtime +7 -delete
```
