from __future__ import annotations

import httpx
from app.core.logging import get_logger

logger = get_logger(__name__)

EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
EDGAR_HEADERS = {"User-Agent": "Zentri contact@zentri.app"}


class DocumentFetcher:
    async def _fetch_json(self, url: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=EDGAR_HEADERS)
            resp.raise_for_status()
            return resp.json()

    async def _resolve_cik(self, ticker: str) -> str | None:
        data = await self._fetch_json(EDGAR_TICKERS_URL)
        ticker_upper = ticker.upper()
        for entry in data.values():
            if isinstance(entry, dict) and entry.get("ticker", "").upper() == ticker_upper:
                return str(entry["cik_str"]).zfill(10)
        return None

    def _extract_filing_urls(self, cik: str, submissions: dict, forms: list[str]) -> list[dict]:
        recent = submissions.get("filings", {}).get("recent", {})
        form_list = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        results: list[dict] = []
        seen_forms: set[str] = set()

        for form, accession, doc in zip(form_list, accessions, primary_docs):
            if form not in forms or form in seen_forms:
                continue
            accession_path = accession.replace("-", "")
            url = EDGAR_DOC_URL.format(cik=int(cik), accession=accession_path, document=doc)
            results.append({
                "url": url,
                "doc_type": form,
                "filename": f"{form.replace('/', '_')}_{accession}.htm",
            })
            seen_forms.add(form)

        return results

    async def fetch_for_ticker(self, ticker: str) -> list[dict]:
        cik = await self._resolve_cik(ticker)
        if not cik:
            logger.warning("document_fetcher: CIK not found for ticker=%s", ticker)
            return []

        try:
            submissions = await self._fetch_json(EDGAR_SUBMISSIONS_URL.format(cik=cik))
        except Exception as e:
            logger.warning("document_fetcher: EDGAR fetch failed ticker=%s: %s", ticker, e)
            return []

        urls = self._extract_filing_urls(cik, submissions, forms=["10-Q", "10-K"])
        logger.info("document_fetcher: found %d filing URLs for ticker=%s", len(urls), ticker)
        return urls
