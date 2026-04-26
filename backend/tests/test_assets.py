import pytest


@pytest.mark.asyncio
async def test_create_asset(auth_client):
    response = await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL",
        "asset_type": "us_stock",
        "name": "Apple Inc.",
        "currency": "USD",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["asset_type"] == "us_stock"


@pytest.mark.asyncio
async def test_search_assets(auth_client):
    await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple Inc.", "currency": "USD"})
    response = await auth_client.get("/api/v1/assets/search?q=AAPL")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_asset_detail(auth_client):
    create = await auth_client.post("/api/v1/assets", json={"symbol": "MSFT", "asset_type": "us_stock", "name": "Microsoft", "currency": "USD"})
    asset_id = create.json()["id"]
    response = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert response.status_code == 200
    assert response.json()["symbol"] == "MSFT"


@pytest.mark.asyncio
async def test_asset_history_by_symbol(auth_client):
    # Create asset first
    await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"
    })
    res = await auth_client.get("/api/v1/assets/symbol/AAPL/history?range=1M")
    assert res.status_code == 200
    data = res.json()
    assert "asset_id" in data
    assert "bars" in data
    assert isinstance(data["bars"], list)


@pytest.mark.asyncio
async def test_asset_history_symbol_not_found(auth_client):
    res = await auth_client.get("/api/v1/assets/symbol/UNKNOWN/history?range=1M")
    assert res.status_code == 404
