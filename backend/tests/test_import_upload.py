import pytest
from app.services.import_pipeline import is_canonical, apply_mapping, parse_all_rows


# Override the autouse async setup_db fixture with a sync no-op so these
# pure-unit tests don't require a database connection.
@pytest.fixture(autouse=True)
def setup_db():  # type: ignore[override]
    yield

def test_is_canonical_exact_match():
    headers = ["trade_date", "type", "symbol", "unit", "price", "currency"]
    assert is_canonical(headers) is True

def test_is_canonical_unknown_header():
    headers = ["Date", "Ticker", "Qty", "Amount"]
    assert is_canonical(headers) is False

def test_is_canonical_empty():
    assert is_canonical([]) is True

def test_apply_mapping_basic():
    mapping = {
        "field_map": {"Date": "trade_date", "Ticker": "symbol", "Qty": "unit", "Action": "type"},
        "type_map": {"Buy": "BUY", "Sell": "SELL"},
        "currency_default": "USD",
        "asset_type_default": "us_stock",
    }
    row = {"Date": "2024-01-15", "Ticker": "AAPL", "Qty": "10", "Action": "Buy"}
    result = apply_mapping(row, mapping)
    assert result["trade_date"] == "2024-01-15"
    assert result["symbol"] == "AAPL"
    assert result["unit"] == "10"
    assert result["type"] == "BUY"
    assert result["currency"] == "USD"

def test_apply_mapping_type_passthrough():
    mapping = {"field_map": {"type": "type"}, "type_map": {}, "currency_default": "THB", "asset_type_default": "thai_stock"}
    row = {"type": "BUY"}
    result = apply_mapping(row, mapping)
    assert result["type"] == "BUY"
