"""File API routes — cache-aware file access (P3 feature)."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/list")
async def list_files(path: str = "/"):
    """List files — cached metadata + NAS proxy."""
    # TODO P3: query file_metadata_cache, indicate which are locally cached
    return {"path": path, "files": []}


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """Download file — cache hit returns local, miss proxies to NAS."""
    # TODO P3: check cached_files, stream from cache or proxy
    return {"error": "Not yet implemented"}


@router.post("/upload")
async def upload_file():
    """Upload file — stores locally, queues sync to NAS."""
    # TODO P3: save to cache_dir, add to upload_queue
    return {"error": "Not yet implemented"}


@router.get("/sync/status")
async def sync_status():
    """Current sync status."""
    # TODO P3: aggregate from upload_queue + sync state
    return {
        "is_syncing": False,
        "pending_uploads": 0,
        "pending_downloads": 0,
        "conflicts": 0,
        "nas_online": False,
    }
