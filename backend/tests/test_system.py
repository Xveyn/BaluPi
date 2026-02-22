"""Test system status endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_system_status(client: AsyncClient):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "cpu_percent" in data
    assert "memory_total_mb" in data
    assert "disk_total_gb" in data
    assert "uptime_seconds" in data
    assert data["memory_total_mb"] > 0
    assert data["disk_total_gb"] > 0
