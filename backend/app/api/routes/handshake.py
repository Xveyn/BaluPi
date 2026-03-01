"""NAS <-> Pi handshake endpoints with HMAC-SHA256 authentication."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.services import (
    get_dns_service,
    get_heartbeat_service,
    get_state_machine,
)
from app.services.nas_state_machine import NasState

logger = logging.getLogger(__name__)
router = APIRouter()

SNAPSHOT_DIR = Path(settings.data_dir) / "snapshot"
SNAPSHOT_FILE = SNAPSHOT_DIR / "snapshot.json"
INBOX_DIR = Path(settings.data_dir) / "inbox"

MAX_TIMESTAMP_AGE = 60  # seconds — reject older requests (replay protection)


async def verify_hmac_signature(request: Request) -> None:
    """Verify HMAC-SHA256 signature from NAS.

    Headers:
        X-Balupi-Timestamp: Unix timestamp (int)
        X-Balupi-Signature: HMAC hex digest

    Signature = HMAC-SHA256(secret, "{method}:{path}:{timestamp}:{sha256(body)}")
    """
    if not settings.handshake_secret:
        raise HTTPException(500, "Handshake secret not configured")

    timestamp_str = request.headers.get("X-Balupi-Timestamp", "")
    signature = request.headers.get("X-Balupi-Signature", "")

    if not timestamp_str or not signature:
        raise HTTPException(401, "Missing HMAC headers")

    # Replay protection
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(401, "Invalid timestamp")

    age = abs(time.time() - timestamp)
    if age > MAX_TIMESTAMP_AGE:
        raise HTTPException(401, f"Timestamp too old ({int(age)}s)")

    # Read body and compute expected signature
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    method = request.method
    path = request.url.path
    message = f"{method}:{path}:{timestamp_str}:{body_hash}"

    expected = hmac.new(
        settings.handshake_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid HMAC signature")


@router.post("/nas-going-offline", dependencies=[Depends(verify_hmac_signature)])
async def nas_going_offline(request: Request):
    """NAS is shutting down — store snapshot, switch DNS to Pi."""
    sm = get_state_machine()
    dns = get_dns_service()

    # Store snapshot
    body = await request.body()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_bytes(body)
    logger.info("Stored NAS shutdown snapshot (%d bytes)", len(body))

    # Transition state
    sm.transition(NasState.SHUTTING_DOWN)

    # Switch DNS to Pi
    dns_switched = await dns.switch_baluhost_dns(settings.pi_ip)

    # After a short delay, mark as offline (NAS will be gone)
    sm.transition(NasState.OFFLINE)

    return {
        "acknowledged": True,
        "dns_switched": dns_switched,
    }


@router.post("/nas-coming-online", dependencies=[Depends(verify_hmac_signature)])
async def nas_coming_online(request: Request):
    """NAS has booted up — flush inbox, switch DNS to NAS."""
    sm = get_state_machine()
    dns = get_dns_service()

    # Transition state
    sm.transition(NasState.ONLINE)

    # Flush inbox
    files_transferred = await _flush_inbox()

    # Switch DNS to NAS
    nas_ip = settings.nas_ip or settings.nas_url.split("//")[-1]
    dns_switched = await dns.switch_baluhost_dns(nas_ip)

    # Disable fast heartbeat polling
    try:
        heartbeat = get_heartbeat_service()
        heartbeat.set_normal_poll()
    except RuntimeError:
        pass

    return {
        "acknowledged": True,
        "inbox_flushed": files_transferred > 0,
        "files_transferred": files_transferred,
        "dns_switched": dns_switched,
    }


@router.get("/status")
async def handshake_status(current_user=Depends(get_current_user)):
    """Current NAS state and handshake info."""
    sm = get_state_machine()

    # Check snapshot
    last_snapshot = None
    if SNAPSHOT_FILE.exists():
        last_snapshot = SNAPSHOT_FILE.stat().st_mtime
        from datetime import datetime, timezone

        last_snapshot = datetime.fromtimestamp(last_snapshot, tz=timezone.utc).isoformat()

    # Inbox size
    inbox_size_mb = 0.0
    if INBOX_DIR.exists():
        total = sum(f.stat().st_size for f in INBOX_DIR.rglob("*") if f.is_file())
        inbox_size_mb = round(total / (1024 * 1024), 1)

    return {
        "nas_state": sm.state.value,
        "since": sm.since.isoformat(),
        "last_snapshot": last_snapshot,
        "inbox_size_mb": inbox_size_mb,
    }


async def _flush_inbox() -> int:
    """rsync inbox to NAS, removing successfully transferred files.

    Returns number of files transferred.
    """
    if settings.is_dev_mode:
        logger.info("[DEV] Inbox flush (not executed)")
        return 0

    if not INBOX_DIR.exists() or not any(INBOX_DIR.iterdir()):
        logger.info("Inbox is empty, nothing to flush")
        return 0

    nas_ip = settings.nas_ip or settings.nas_url.split("//")[-1]

    try:
        result = await asyncio.create_subprocess_exec(
            "rsync", "-avz", "--remove-source-files",
            str(INBOX_DIR) + "/",
            f"{settings.nas_ssh_user}@{nas_ip}:{settings.nas_inbox_path}/",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            logger.error("Inbox flush failed: %s", stderr.decode())
            return 0

        # Count transferred files from rsync output
        lines = stdout.decode().splitlines()
        transferred = sum(
            1 for line in lines
            if line.strip()
            and not line.startswith(("sending", "sent", "total", "building", "created"))
            and not line.endswith("/")
        )

        logger.info("Inbox flush: %d files transferred", transferred)
        return transferred
    except FileNotFoundError:
        logger.error("rsync not found — cannot flush inbox")
        return 0
    except Exception as e:
        logger.error("Inbox flush error: %s", e)
        return 0
