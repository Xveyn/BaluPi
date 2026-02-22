"""Disk space management utilities."""

import shutil
from pathlib import Path


def get_disk_usage(path: str | Path) -> dict:
    """Get disk usage for the given path."""
    usage = shutil.disk_usage(str(path))
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "percent": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
    }


def get_directory_size(path: str | Path) -> int:
    """Calculate total size of all files in a directory (recursive)."""
    total = 0
    for f in Path(path).rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total
