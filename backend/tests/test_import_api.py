import pytest
import uuid

CSV_CONTENT = b"Template,Fund_Code,Trade_Date,Total_Amount,Number_of_Units\nManual,K-VIETNAM,2026-01-01,500,10"


@pytest.mark.asyncio
async def test_analyze_without_platform_id_returns_new(auth_client):
    resp = await auth_client.post(
        "/api/v1/import/analyze",
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["template_status"] == "new"
    assert data["matched_platform_id"] is None


@pytest.mark.asyncio
async def test_analyze_without_platform_id_returns_match_after_template_exists(auth_client):
    p = await auth_client.post("/api/v1/platforms", json={"name": "Finnomena", "asset_types_supported": ["th_fund"]})
    pid = p.json()["id"]

    resp1 = await auth_client.post(
        "/api/v1/import/analyze",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp1.status_code == 200
    assert resp1.json()["template_status"] == "new"

    await auth_client.post(
        "/api/v1/import/generate-template",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )

    resp2 = await auth_client.post(
        "/api/v1/import/analyze",
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["template_status"] == "match"
    assert data["matched_platform_id"] == pid


@pytest.mark.asyncio
async def test_analyze_with_platform_id_still_works(auth_client):
    p = await auth_client.post("/api/v1/platforms", json={"name": "Test", "asset_types_supported": []})
    pid = p.json()["id"]
    resp = await auth_client.post(
        "/api/v1/import/analyze",
        data={"platform_id": pid},
        files={"file": ("transactions.csv", CSV_CONTENT, "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json()["template_status"] == "new"


@pytest.mark.asyncio
async def test_confirm_saves_platform_id_on_transactions(auth_client, db):
    from sqlalchemy import select
    from app.models.transaction import Transaction

    rows = [{"symbol": "AAPL", "type": "buy", "units": "10", "price": "150", "date": "2026-01-01", "asset_type": "us_stock", "currency": "USD"}]
    p = await auth_client.post("/api/v1/platforms", json={"name": "IBKR", "asset_types_supported": ["us_stock"]})
    pid = p.json()["id"]

    resp = await auth_client.post("/api/v1/import/confirm", json={"platform_id": pid, "rows": rows})
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1

    result = await db.execute(select(Transaction))
    txs = result.scalars().all()
    assert len(txs) == 1
    assert str(txs[0].platform_id) == pid


@pytest.mark.asyncio
async def test_confirm_import_uses_canonical_unit_and_trade_date(auth_client):
    rows = [
        {
            "symbol": "AAPL",
            "asset_type": "us_stock",
            "type": "BUY",
            "unit": "10",
            "price": "150.00",
            "currency": "USD",
            "trade_date": "2026-01-15",
            "fee": "0",
        }
    ]
    r = await auth_client.post(
        "/api/v1/import/confirm",
        json={"platform_id": None, "rows": rows},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 1
    assert data["errors"] == []
