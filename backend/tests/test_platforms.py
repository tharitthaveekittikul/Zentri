import pytest


@pytest.mark.asyncio
async def test_create_platform(auth_client):
    response = await auth_client.post("/api/v1/platforms", json={
        "name": "Robinhood",
        "asset_types_supported": ["us_stock", "crypto"],
        "notes": "US broker",
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Robinhood"


@pytest.mark.asyncio
async def test_list_platforms(auth_client):
    await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    response = await auth_client.get("/api/v1/platforms")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_update_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.put(f"/api/v1/platforms/{pid}", json={"name": "Robinhood Pro", "asset_types_supported": ["us_stock", "crypto"]})
    assert response.status_code == 200
    assert response.json()["name"] == "Robinhood Pro"


@pytest.mark.asyncio
async def test_delete_platform(auth_client):
    create = await auth_client.post("/api/v1/platforms", json={"name": "Robinhood", "asset_types_supported": ["us_stock"]})
    pid = create.json()["id"]
    response = await auth_client.delete(f"/api/v1/platforms/{pid}")
    assert response.status_code == 204
    list_response = await auth_client.get("/api/v1/platforms")
    assert len(list_response.json()) == 0
