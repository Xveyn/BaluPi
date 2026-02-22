"""File schemas — compatible with BaluHost subset."""

from datetime import datetime

from pydantic import BaseModel


class FileItem(BaseModel):
    """File metadata for listing."""
    id: str
    filename: str
    relative_path: str
    mime_type: str | None = None
    size_bytes: int
    is_directory: bool = False
    modified_at: datetime | None = None
    is_cached: bool = False  # Pi-specific: is file locally available?
