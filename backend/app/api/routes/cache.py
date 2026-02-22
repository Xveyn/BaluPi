"""Cache statistics routes — P3 feature."""

from fastapi import APIRouter

from app.schemas.cache import CacheStats

router = APIRouter()


@router.get("/stats", response_model=CacheStats)
async def cache_stats():
    """Cache usage statistics."""
    # TODO P3: query cached_files table + disk usage
    return CacheStats(
        total_files=0,
        total_size_mb=0.0,
        max_size_gb=200.0,
        usage_percent=0.0,
        dirty_files=0,
    )
