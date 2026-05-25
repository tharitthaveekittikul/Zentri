import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.anyio
async def test_trigger_top_down_unknown_symbol_auto_creates_asset(auth_client: AsyncClient):
    fake_quotes = [{"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NMS", "quoteType": "EQUITY"}]
    with patch("yfinance.Search") as mock_search:
        mock_search.return_value.quotes = fake_quotes
        res = await auth_client.post("/api/v1/analysis/top-down/AAPL")
    assert res.status_code == 202
    data = res.json()
    assert data["symbol"] == "AAPL"


@pytest.mark.anyio
async def test_trigger_top_down_unknown_symbol_not_in_yfinance_returns_404(auth_client: AsyncClient):
    with patch("yfinance.Search") as mock_search:
        mock_search.return_value.quotes = []
        res = await auth_client.post("/api/v1/analysis/top-down/NOTREAL99999")
    assert res.status_code == 404


@pytest.mark.anyio
async def test_trigger_top_down_thai_stock_strips_bk_suffix(auth_client: AsyncClient):
    fake_quotes = [{"symbol": "PTT.BK", "shortname": "PTT PCL", "exchange": "SET", "quoteType": "EQUITY"}]
    with patch("yfinance.Search") as mock_search:
        mock_search.return_value.quotes = fake_quotes
        res = await auth_client.post("/api/v1/analysis/top-down/PTT.BK")
    assert res.status_code == 202
    data = res.json()
    assert data["symbol"] == "PTT"
