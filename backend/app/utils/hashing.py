"""SHA-256 file hashing utility."""

import hashlib
from pathlib import Path

CHUNK_SIZE = 64 * 1024  # 64 KB


def hash_file(path: Path) -> str:
    """Compute SHA-256 hash of a file, streaming in 64 KB chunks."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()
