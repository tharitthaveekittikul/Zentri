from unittest.mock import AsyncMock, patch
import pytest
from app.services.document_fetcher import DocumentFetcher


@pytest.mark.asyncio
async def test_resolve_cik_returns_padded_string():
    tickers_json = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
    }
    with patch("app.services.document_fetcher.DocumentFetcher._fetch_json", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = tickers_json
        fetcher = DocumentFetcher()
        cik = await fetcher._resolve_cik("AAPL")
    assert cik == "0000320193"


@pytest.mark.asyncio
async def test_resolve_cik_unknown_ticker_returns_none():
    with patch("app.services.document_fetcher.DocumentFetcher._fetch_json", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {}
        fetcher = DocumentFetcher()
        cik = await fetcher._resolve_cik("ZZZZ")
    assert cik is None


@pytest.mark.asyncio
async def test_fetch_filing_urls_returns_list():
    submissions = {
        "filings": {
            "recent": {
                "form": ["10-Q", "10-K", "8-K"],
                "accessionNumber": ["0000320193-24-000001", "0000320193-23-000001", "0000320193-23-000002"],
                "primaryDocument": ["form10q.htm", "form10k.htm", "form8k.htm"],
            }
        }
    }
    with patch("app.services.document_fetcher.DocumentFetcher._fetch_json", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = submissions
        fetcher = DocumentFetcher()
        urls = fetcher._extract_filing_urls("0000320193", submissions, forms=["10-Q", "10-K"])
    assert len(urls) == 2
    assert any(r["doc_type"] == "10-Q" for r in urls)
    assert any(r["doc_type"] == "10-K" for r in urls)
