# BaluPi — Verbleibende Aufgaben

Alle 4 Phasen (P0–P4) sind code-seitig abgeschlossen. Es steht nur noch Ops/Deployment-Arbeit aus.

---

## 1. SMB-Share auf dem Pi einrichten

- [ ] 1TB HDD formatieren und mounten (`/etc/fstab`, ext4)
- [ ] Mountpoints anlegen: `/smb/share/`, `/smb/inbox/`
- [ ] Samba installieren und konfigurieren (`smb.conf`)
- [ ] Share-Zugriff testen (Windows/macOS/Linux)

## 2. Deployment auf dem Pi

- [ ] `deploy/install.sh` auf dem Pi ausführen
- [ ] `.env` konfigurieren:
  - `BALUPI_MODE=prod`
  - `BALUPI_NAS_URL`, `BALUPI_NAS_IP`, `BALUPI_NAS_MAC_ADDRESS`
  - `BALUPI_TAPO_USERNAME`, `BALUPI_TAPO_PASSWORD`
  - `BALUPI_HANDSHAKE_SECRET` (32+ Zeichen, muss mit BaluHost matchen)
  - `BALUPI_PIHOLE_URL`, `BALUPI_PIHOLE_PASSWORD`
  - `BALUPI_PI_IP`
  - `BALUPI_SECRET_KEY` (wird vom Installer generiert)
- [ ] GitHub Deploy Key für `deploy-pi.yml` Workflow einrichten (`BALUPI_DEPLOY_KEY` Secret)
- [ ] Frontend-Sync testen: `python3 sync_frontend.py --from-branch frontend`
- [ ] Service starten: `sudo systemctl start balupi`
- [ ] Health-Check: `curl http://localhost/api/health`

## 3. BaluHost-Seite aktivieren

- [ ] In BaluHost `.env` setzen:
  - `BALUPI_ENABLED=true`
  - `BALUPI_URL=http://<pi-ip>:8000`
  - `BALUPI_HANDSHAKE_SECRET=<selber Wert wie auf dem Pi>`
- [ ] BaluHost neu starten und Startup-Notification prüfen (Logs)

## 4. End-to-End testen

- [ ] **Shutdown-Handshake**: NAS herunterfahren → Snapshot wird an Pi gesendet → DNS schaltet auf Pi-IP
- [ ] **WoL + Startup-Handshake**: WoL-Button im PiDashboard → NAS bootet → Inbox flush (rsync) → DNS schaltet auf NAS-IP
- [ ] **Heartbeat**: NAS-Service stoppen → nach 3× Failure (~90s) automatischer DNS-Switch auf Pi
- [ ] **Energy Monitoring**: Tapo-Plugs liefern Live-Daten, Aggregation (stündlich/täglich) läuft
- [ ] **PiDashboard**: Alle Widgets zeigen korrekte Daten (NAS Status, Energy, Snapshot, Inbox, Pi Health)
- [ ] **Inbox**: Datei in `/smb/inbox/` legen → nach NAS-Start wird sie per rsync übertragen und lokal gelöscht
