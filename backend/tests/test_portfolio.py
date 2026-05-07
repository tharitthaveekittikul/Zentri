import pytest


@pytest.fixture
async def asset_id(auth_client):
    res = await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"})
    return res.json()["id"]


@pytest.mark.asyncio
async def test_add_holding(auth_client, asset_id):
    response = await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id,
        "quantity": "10.5",
        "avg_cost_price": "150.00",
        "currency": "USD",
    })
    assert response.status_code == 201
    data = response.json()
    assert float(data["quantity"]) == 10.5
    assert float(data["avg_cost_price"]) == 150.00


@pytest.mark.asyncio
async def test_list_holdings(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={"asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"})
    response = await auth_client.get("/api/v1/portfolio/holdings")
    assert response.status_code == 200
    # New — returns paginated response
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_add_transaction(auth_client, asset_id):
    response = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    assert response.status_code == 201
    assert response.json()["type"] == "buy"


@pytest.mark.asyncio
async def test_list_transactions_for_asset(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z"
    })
    response = await auth_client.get(f"/api/v1/portfolio/transactions?asset_id={asset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_portfolio_summary(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={"asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD"})
    response = await auth_client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert "holdings_count" in data
    assert data["holdings_count"] == 1


@pytest.mark.asyncio
async def test_patch_transaction(auth_client, asset_id):
    create_res = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    tx_id = create_res.json()["id"]

    patch_res = await auth_client.patch(
        f"/api/v1/portfolio/transactions/{tx_id}",
        json={"price": "160.00", "fee": "0.50"},
    )
    assert patch_res.status_code == 200
    assert float(patch_res.json()["price"]) == 160.00
    assert float(patch_res.json()["fee"]) == 0.50


@pytest.mark.asyncio
async def test_delete_transaction(auth_client, asset_id):
    create_res = await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id,
        "type": "buy",
        "quantity": "5",
        "price": "155.00",
        "fee": "1.00",
        "executed_at": "2026-01-15T10:00:00Z",
    })
    tx_id = create_res.json()["id"]

    delete_res = await auth_client.delete(f"/api/v1/portfolio/transactions/{tx_id}")
    assert delete_res.status_code == 204

    list_res = await auth_client.get("/api/v1/portfolio/transactions")
    assert all(t["id"] != tx_id for t in list_res.json()["items"])


@pytest.mark.asyncio
async def test_delete_transaction_not_found(auth_client):
    import uuid
    fake_id = str(uuid.uuid4())
    res = await auth_client.delete(f"/api/v1/portfolio/transactions/{fake_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_transactions_includes_symbol(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z"
    })
    res = await auth_client.get("/api/v1/portfolio/transactions")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_add_holding_persists_metadata(auth_client):
    response = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "BTC",
        "asset_type": "crypto",
        "quantity": "0.5",
        "avg_cost_price": "50000",
        "currency": "USD",
        "metadata_": {"coingecko_id": "bitcoin"},
    })
    assert response.status_code == 201
    data = response.json()
    assert data["symbol"] == "BTC"

    # Verify asset was stored with coingecko_id
    asset_id = data["asset_id"]
    asset_res = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert asset_res.status_code == 200
    assert asset_res.json()["metadata_"]["coingecko_id"] == "bitcoin"


@pytest.mark.asyncio
async def test_list_holdings_paginated_search(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    res = await auth_client.get("/api/v1/portfolio/holdings?search=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "AAPL"

@pytest.mark.asyncio
async def test_list_holdings_paginated_no_match(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    res = await auth_client.get("/api/v1/portfolio/holdings?search=NOTEXIST")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []

@pytest.mark.asyncio
async def test_list_transactions_paginated_search(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z",
    })
    res = await auth_client.get("/api/v1/portfolio/transactions?search=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "AAPL"

@pytest.mark.asyncio
async def test_list_transactions_paginated_type_filter(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z",
    })
    res = await auth_client.get("/api/v1/portfolio/transactions?type=sell")
    assert res.status_code == 200
    assert res.json()["total"] == 0
