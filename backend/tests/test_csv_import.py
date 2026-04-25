import io
import pytest


SAMPLE_CSV = b"""Date,Symbol,Action,Quantity,Price,Fee
2026-01-15,AAPL,BUY,10,150.00,1.00
2026-02-01,MSFT,BUY,5,300.00,1.00
"""


@pytest.mark.asyncio
async def test_import_preview_returns_columns_and_rows(auth_client):
    response = await auth_client.post(
        "/api/v1/portfolio/import/preview",
        files={"file": ("trades.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "rows" in data
    assert len(data["columns"]) == 6
    assert len(data["rows"]) == 2


@pytest.mark.asyncio
async def test_import_confirm_creates_transactions(auth_client):
    await auth_client.post("/api/v1/assets", json={"symbol": "AAPL", "asset_type": "us_stock", "name": "Apple", "currency": "USD"})
    await auth_client.post("/api/v1/assets", json={"symbol": "MSFT", "asset_type": "us_stock", "name": "Microsoft", "currency": "USD"})

    confirm_payload = {
        "rows": [
            {"date": "2026-01-15", "symbol": "AAPL", "type": "buy", "quantity": "10", "price": "150.00", "fee": "1.00"},
            {"date": "2026-02-01", "symbol": "MSFT", "type": "buy", "quantity": "5", "price": "300.00", "fee": "1.00"},
        ],
        "asset_type": "us_stock",
        "save_profile": False,
        "broker_name": None,
    }
    response = await auth_client.post("/api/v1/portfolio/import/confirm", json=confirm_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0

    txns = await auth_client.get("/api/v1/portfolio/transactions")
    assert len(txns.json()) == 2
