"""Cache statistics schemas."""

from pydantic import BaseModel


class CacheStats(BaseModel):
    """Cache usage statistics."""
    total_files: int
    total_size_mb: float
    max_size_gb: float
    usage_percent: float
    dirty_files: int  # Files not yet synced to NAS
    hit_rate_percent: float | None = None
