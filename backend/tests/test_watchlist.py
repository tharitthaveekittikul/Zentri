import pytest


@pytest.mark.asyncio
async def test_list_watchlist_paginated(auth_client):
    res = await auth_client.get("/api/v1/watchlist")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["items"] == []
    assert data["total"] == 0
