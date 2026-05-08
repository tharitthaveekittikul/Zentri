import pytest


@pytest.mark.asyncio
async def test_list_platforms_empty(auth_client):
    res = await auth_client.get("/api/v1/platforms")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_upsert_and_list_platform(auth_client):
    res = await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}

    res = await auth_client.get("/api/v1/platforms")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bitkub"
    assert data[0]["color"] == "#FF6B00"


@pytest.mark.asyncio
async def test_upsert_updates_existing(auth_client):
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#123456"})

    res = await auth_client.get("/api/v1/platforms")
    data = res.json()
    assert len(data) == 1
    assert data[0]["color"] == "#123456"


@pytest.mark.asyncio
async def test_delete_platform(auth_client):
    await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "#FF6B00"})
    res = await auth_client.delete("/api/v1/platforms/Bitkub")
    assert res.status_code == 204

    res = await auth_client.get("/api/v1/platforms")
    assert res.json() == []


@pytest.mark.asyncio
async def test_delete_platform_not_found(auth_client):
    res = await auth_client.delete("/api/v1/platforms/NoSuchPlatform")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_upsert_invalid_color(auth_client):
    res = await auth_client.put("/api/v1/platforms/Bitkub", json={"color": "red"})
    assert res.status_code == 422
