import uuid

import pytest


@pytest.mark.asyncio
async def test_update_holding_quantity(auth_client):
    # Add a holding first
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "AAPL", "asset_type": "us_stock",
        "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]

    # Update quantity
    patch = await auth_client.patch(f"/api/v1/portfolio/holdings/{holding_id}", json={
        "quantity": "20",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert float(data["outstanding_shares"]) == 20
    assert float(data["cost_per_share"]) == 150  # unchanged


@pytest.mark.asyncio
async def test_update_holding_currency_and_platform(auth_client):
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "VOO", "asset_type": "etf",
        "quantity": "5", "avg_cost_price": "400", "currency": "USD",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]

    patch = await auth_client.patch(f"/api/v1/portfolio/holdings/{holding_id}", json={
        "currency": "THB",
        "platform": "Interactive Brokers",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert data["currency"] == "THB"
    assert data["platform"] == "Interactive Brokers"


@pytest.mark.asyncio
async def test_update_holding_not_found(auth_client):
    patch = await auth_client.patch(
        f"/api/v1/portfolio/holdings/{uuid.uuid4()}", json={"quantity": "5"}
    )
    assert patch.status_code == 404


@pytest.mark.asyncio
async def test_update_holding_returns_platform_in_list(auth_client):
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "MSFT", "asset_type": "us_stock",
        "quantity": "3", "avg_cost_price": "300", "currency": "USD",
        "platform": "Schwab",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]
    assert resp.json()["platform"] == "Schwab"

    # Confirm it appears in list
    list_resp = await auth_client.get("/api/v1/portfolio/holdings")
    assert list_resp.status_code == 200
    match = next((h for h in list_resp.json() if h["id"] == holding_id), None)
    assert match is not None
    assert match["platform"] == "Schwab"
