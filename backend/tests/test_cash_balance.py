import pytest
from datetime import date


async def test_create_cash_asset_and_balance(auth_client):
    # Create cash asset
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "KBANK_SAVINGS",
        "asset_type": "cash",
        "name": "KBANK Savings",
        "currency": "THB",
    })
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    # Add balance snapshot
    resp = await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": asset_id,
        "balance": 50000.0,
        "snapshot_date": str(date.today()),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["balance"] == 50000.0


async def test_latest_balance(auth_client):
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "GSB_SAVINGS", "asset_type": "cash", "name": "GSB", "currency": "THB"
    })
    aid = asset.json()["id"]
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": aid, "balance": 10000.0, "snapshot_date": "2026-01-01"
    })
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": aid, "balance": 15000.0, "snapshot_date": "2026-02-01"
    })
    resp = await auth_client.get(f"/api/v1/cash-balances/{aid}/latest")
    assert resp.status_code == 200
    assert resp.json()["balance"] == 15000.0


async def test_balance_history(auth_client):
    asset = await auth_client.post("/api/v1/assets", json={
        "symbol": "DIME_USD", "asset_type": "cash", "name": "DIME USD", "currency": "USD"
    })
    aid = asset.json()["id"]
    for amount in [100.0, 200.0, 150.0]:
        await auth_client.post("/api/v1/cash-balances", json={
            "asset_id": aid, "balance": amount, "snapshot_date": f"2026-0{int(amount/100)}-01"
        })
    resp = await auth_client.get(f"/api/v1/cash-balances/{aid}/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 3
