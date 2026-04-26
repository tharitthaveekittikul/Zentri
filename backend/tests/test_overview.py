import pytest


@pytest.fixture
async def asset_with_holding(auth_client):
    asset_res = await auth_client.post("/api/v1/assets", json={
        "symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"
    })
    asset_id = asset_res.json()["id"]
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"
    })
    return asset_id


@pytest.mark.asyncio
async def test_summary_empty_portfolio(auth_client):
    res = await auth_client.get("/api/v1/overview/summary")
    assert res.status_code == 200
    data = res.json()
    assert float(data["total_value"]) == 0.0
    assert float(data["total_cost"]) == 0.0
    assert float(data["total_pnl"]) == 0.0


@pytest.mark.asyncio
async def test_summary_with_holding_no_prices(auth_client, asset_with_holding):
    res = await auth_client.get("/api/v1/overview/summary")
    assert res.status_code == 200
    data = res.json()
    assert float(data["total_cost"]) == 1500.0
    assert float(data["total_value"]) == 0.0


@pytest.mark.asyncio
async def test_allocation_empty(auth_client):
    res = await auth_client.get("/api/v1/overview/allocation")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_allocation_with_holding_no_prices(auth_client, asset_with_holding):
    res = await auth_client.get("/api/v1/overview/allocation")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_performance_returns_structure(auth_client):
    res = await auth_client.get("/api/v1/overview/performance?range=1M")
    assert res.status_code == 200
    data = res.json()
    assert "portfolio" in data
    assert "benchmark" in data
    assert isinstance(data["portfolio"], list)
    assert isinstance(data["benchmark"], list)


@pytest.mark.asyncio
async def test_performance_invalid_range_defaults(auth_client):
    res = await auth_client.get("/api/v1/overview/performance?range=INVALID")
    assert res.status_code == 200
    data = res.json()
    assert "portfolio" in data
