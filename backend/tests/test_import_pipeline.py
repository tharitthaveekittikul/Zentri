import pytest
import hashlib
import json
import uuid
from app.services.import_pipeline import (
    detect_file_format,
    extract_structure,
    compute_signature,
    apply_template,
    get_template_by_signature,
    save_template,
)


def test_detect_csv_format():
    assert detect_file_format("transactions.csv", b"Fund_Code,Date\nK-VIETNAM,2026-01-01") == "csv"


def test_detect_json_format():
    assert detect_file_format("data.json", b'[{"symbol": "AAPL"}]') == "json"


def test_extract_csv_structure():
    content = b"Fund_Code,Trade_Date,Total_Amount\nK-VIETNAM,2026-01-01,500"
    structure = extract_structure("csv", content, json_path=None)
    assert structure["headers"] == ["Fund_Code", "Trade_Date", "Total_Amount"]
    assert len(structure["sample_rows"]) == 1


def test_extract_json_structure():
    data = [{"transactions": [{"symbol": "AAPL", "unit": 1}]}, {"transactions": [{"symbol": "MSFT", "unit": 2}]}]
    content = json.dumps(data).encode()
    structure = extract_structure("json", content, json_path="[].transactions[]")
    assert "symbol" in structure["headers"]


def test_compute_signature_stable():
    headers = ["Fund_Code", "Trade_Date", "Total_Amount"]
    sig1 = compute_signature(headers)
    sig2 = compute_signature(headers)
    assert sig1 == sig2
    assert len(sig1) == 64  # sha256 hex


def test_apply_template_maps_fields():
    rows = [{"share_name": "PTT", "unit": 100, "net_amount": 3455, "trade_date": "2026-01-01", "type": "BUY"}]
    template = {
        "field_map": {"share_name": "symbol", "unit": "units", "net_amount": "total_thb", "trade_date": "date"},
        "asset_type_rules": [],
        "asset_type_fallback": "thai_stock",
        "currency_default": "THB",
    }
    result = apply_template(rows, template)
    assert result[0]["symbol"] == "PTT"
    assert result[0]["units"] == 100
    assert result[0]["asset_type"] == "thai_stock"
    assert result[0]["currency"] == "THB"


def test_apply_template_asset_type_rules():
    rows = [{"symbol": "AAPL", "exchange": "XNAS", "unit": 1, "total_thb": 5000, "date": "2026-01-01", "type": "BUY"}]
    template = {
        "field_map": {},
        "asset_type_rules": [
            {"field": "exchange", "values": ["XNAS", "XNYS"], "asset_type": "us_stock"},
        ],
        "asset_type_fallback": "etf",
        "currency_default": "USD",
    }
    result = apply_template(rows, template)
    assert result[0]["asset_type"] == "us_stock"


@pytest.mark.asyncio
async def test_get_template_by_signature_not_found(db):
    result = await get_template_by_signature(db, uuid.uuid4(), "nonexistent_sig")
    assert result is None


@pytest.mark.asyncio
async def test_get_template_by_signature_found(db, auth_client):
    # Create a platform first
    p = await auth_client.post("/api/v1/platforms", json={"name": "Test", "asset_types_supported": []})
    pid = uuid.UUID(p.json()["id"])
    me = await auth_client.get("/api/v1/auth/me")
    user_id = uuid.UUID(me.json()["id"])

    await save_template(
        db, user_id, pid,
        {"field_map": {}, "asset_type_rules": [], "asset_type_fallback": "us_stock", "currency_default": "THB"},
        "csv", None, "abc123"
    )
    result = await get_template_by_signature(db, user_id, "abc123")
    assert result is not None
    assert result.platform_id == pid
