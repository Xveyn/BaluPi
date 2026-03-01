"""Serve the last NAS snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.config import settings

router = APIRouter()

SNAPSHOT_FILE = Path(settings.data_dir) / "snapshot" / "snapshot.json"


@router.get("/snapshot")
async def get_snapshot(current_user=Depends(get_current_user)):
    """Serve the last NAS snapshot as JSON."""
    if not SNAPSHOT_FILE.exists():
        raise HTTPException(404, "No snapshot available")
    return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
