"""Sync status schemas."""

from datetime import datetime

from pydantic import BaseModel


class SyncStatus(BaseModel):
    """Current sync status."""
    is_syncing: bool = False
    last_sync: datetime | None = None
    pending_uploads: int = 0
    pending_downloads: int = 0
    conflicts: int = 0
    nas_online: bool = False
