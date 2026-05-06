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


@pytest.mark.asyncio
async def test_patch_asset(auth_client):
    create = await auth_client.post("/api/v1/assets", json={
        "symbol": "SCB_THB", "asset_type": "cash", "name": "SCB_THB", "currency": "THB",
        "metadata_": {"account_number": "111-1-11111-1"},
    })
    asset_id = create.json()["id"]

    response = await auth_client.patch(f"/api/v1/assets/{asset_id}", json={
        "symbol": "SCB_THB2",
        "name": "SCB_THB2",
        "currency": "THB",
        "metadata_": {"account_number": "222-2-22222-2"},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "SCB_THB2"
    assert data["metadata_"]["account_number"] == "222-2-22222-2"


@pytest.mark.asyncio
async def test_patch_asset_not_found(auth_client):
    import uuid
    response = await auth_client.patch(f"/api/v1/assets/{uuid.uuid4()}", json={"symbol": "X"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_asset(auth_client):
    create = await auth_client.post("/api/v1/assets", json={
        "symbol": "KTB_THB", "asset_type": "cash", "name": "KTB_THB", "currency": "THB",
    })
    asset_id = create.json()["id"]

    # Add a cash balance to verify cascade
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": asset_id, "balance": 5000.0, "snapshot_date": "2026-05-06",
    })

    response = await auth_client.delete(f"/api/v1/assets/{asset_id}")
    assert response.status_code == 204

    get = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert get.status_code == 404

    balance = await auth_client.get(f"/api/v1/cash-balances/{asset_id}/latest")
    assert balance.status_code != 200


@pytest.mark.asyncio
async def test_delete_asset_not_found(auth_client):
    import uuid
    response = await auth_client.delete(f"/api/v1/assets/{uuid.uuid4()}")
    assert response.status_code == 404
