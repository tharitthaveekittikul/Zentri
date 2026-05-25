import pytest
from httpx import AsyncClient
from unittest.mock import patch


@pytest.mark.anyio
async def test_market_search_aapl_returns_results(auth_client: AsyncClient):
    fake_quotes = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NMS", "quoteType": "EQUITY"},
        {"symbol": "AAPL.BA", "shortname": "Apple Inc. (BA)", "exchange": "BUE", "quoteType": "EQUITY"},
    ]
    with patch("yfinance.Search") as mock_search:
        mock_search.return_value.quotes = fake_quotes
        res = await auth_client.get("/api/v1/assets/market-search?q=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    first = data[0]
    assert first["symbol"] == "AAPL"
    assert first["name"] == "Apple Inc."
    assert first["exchange"] == "NMS"
    assert first["type_display"] == "EQUITY"


@pytest.mark.anyio
async def test_market_search_gibberish_returns_empty_list(auth_client: AsyncClient):
    res = await auth_client.get("/api/v1/assets/market-search?q=XYZZZNOTREAL99999")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


@pytest.mark.anyio
async def test_market_search_requires_auth(client: AsyncClient):
    res = await client.get("/api/v1/assets/market-search?q=AAPL")
    assert res.status_code == 401
