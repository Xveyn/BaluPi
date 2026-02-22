"""Test health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "balupi"
    assert "version" in data


@pytest.mark.asyncio
async def test_ping(client: AsyncClient):
    resp = await client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
