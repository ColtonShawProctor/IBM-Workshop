from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_health_returns_200(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"
