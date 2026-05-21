# Top-Down Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a structured Top-Down Analysis feature: auto-fetch SEC filings + news per ticker, deduplicate by source URL, run LLM with structured SWOT output, serve results via API, and display in a new frontend page.

**Architecture:** New ARQ job `job_run_top_down_analysis` orchestrates 5 steps — load asset, pre-fetch documents (SEC EDGAR 10-Q/10-K + news, deduplicated by `source_url`), RAG retrieval, LLM call returning structured JSON, save to new `TopDownAnalysis` model. Existing `job_run_analysis` and `AIAnalysis` are untouched.

**Tech Stack:** Python/FastAPI backend, SQLAlchemy async, Alembic, ARQ/Redis, ChromaDB, httpx (EDGAR fetch), Next.js/TypeScript frontend, Tailwind + CSS variables.

---

## File Map

### Backend — New
| File | Responsibility |
|---|---|
| `backend/app/models/top_down_analysis.py` | SQLAlchemy model for `top_down_analyses` table |
| `backend/app/services/document_fetcher.py` | Resolve 10-Q/10-K URLs from SEC EDGAR + news from DB |
| `backend/app/services/document_manager.py` | Check source_url dedup → download → save → enqueue ingest |
| `backend/app/api/top_down_analysis.py` | POST trigger + GET latest/history endpoints |
| `backend/worker/jobs/run_top_down_analysis.py` | 5-step ARQ job |
| `backend/alembic/versions/037_top_down_analysis.py` | Migration: source_url on documents + top_down_analyses table |

### Backend — Modified
| File | Change |
|---|---|
| `backend/app/models/document.py` | Add `source_url: str | None` column |
| `backend/app/api/documents.py` | Add `GET /documents/{doc_id}/file` endpoint |
| `backend/app/main.py` | Import and register `top_down_analysis.router` |
| `backend/worker/main.py` | Import and register `job_run_top_down_analysis` |

### Frontend — New
| File | Responsibility |
|---|---|
| `frontend/components/analysis/SwotGrid.tsx` | 2×2 SWOT grid component |
| `frontend/components/analysis/DocumentsList.tsx` | Document list with open-in-tab + path display |
| `frontend/components/analysis/TopDownAnalysisCard.tsx` | Full analysis card assembling all sections |
| `frontend/app/(auth)/analysis/[symbol]/page.tsx` | Page: fetch + display TopDownAnalysis for a symbol |

---

## Task 1: DB Migration

**Files:**
- Create: `backend/alembic/versions/037_top_down_analysis.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/037_top_down_analysis.py
"""add top_down_analyses and source_url to documents

Revision ID: 037
Revises: 036
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("doc_type", sa.String(50), nullable=True))

    op.create_table(
        "top_down_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", sa.String(), nullable=True),
        sa.Column("mega_trend", sa.Text(), nullable=False),
        sa.Column("financial_health", sa.Text(), nullable=False),
        sa.Column("swot_strengths", postgresql.JSON(), nullable=False),
        sa.Column("swot_weaknesses", postgresql.JSON(), nullable=False),
        sa.Column("swot_opportunities", postgresql.JSON(), nullable=False),
        sa.Column("swot_threats", postgresql.JSON(), nullable=False),
        sa.Column("verdict", sa.String(10), nullable=False),
        sa.Column("target_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("top_down_analyses")
    op.drop_column("documents", "source_url")
    op.drop_column("documents", "doc_type")
```

- [ ] **Step 2: Run the migration**

```bash
cd backend && docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 036 -> 037, add top_down_analyses and source_url to documents`

---

## Task 2: TopDownAnalysis Model

**Files:**
- Create: `backend/app/models/top_down_analysis.py`

- [ ] **Step 1: Write the model**

```python
# backend/app/models/top_down_analysis.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TopDownAnalysis(Base):
    __tablename__ = "top_down_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    mega_trend: Mapped[str] = mapped_column(Text, nullable=False)
    financial_health: Mapped[str] = mapped_column(Text, nullable=False)
    swot_strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_opportunities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot_threats: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    verdict: Mapped[str] = mapped_column(String(10), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)

    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && docker compose exec backend python -c "from app.models.top_down_analysis import TopDownAnalysis; print('ok')"
```

Expected: `ok`

---

## Task 3: Document Model — source_url + File Serve Endpoint

**Files:**
- Modify: `backend/app/models/document.py`
- Modify: `backend/app/api/documents.py`

- [ ] **Step 1: Add source_url to Document model**

In `backend/app/models/document.py`, add after the `error_msg` field:

```python
source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Full updated model:

```python
# backend/app/models/document.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chroma_collection_id: Mapped[str | None] = mapped_column(nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Add file serve endpoint to documents.py**

Add this at the end of `backend/app/api/documents.py`:

```python
from fastapi.responses import FileResponse


@router.get("/{doc_id}/file")
async def serve_document_file(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    p = Path(doc.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    media_type = "application/pdf" if p.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(path=str(p), media_type=media_type, filename=doc.filename)
```

- [ ] **Step 3: Verify the endpoint is reachable**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/documents/00000000-0000-0000-0000-000000000000/file
```

Expected: `404` (not found, but route exists)

---

## Task 4: DocumentFetcher Service

**Files:**
- Create: `backend/app/services/document_fetcher.py`
- Create: `backend/tests/test_document_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_document_fetcher.py
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && docker compose exec backend pytest tests/test_document_fetcher.py -v 2>&1 | tail -15
```

Expected: `ImportError` or `ModuleNotFoundError` for `document_fetcher`

- [ ] **Step 3: Implement DocumentFetcher**

```python
# backend/app/services/document_fetcher.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && docker compose exec backend pytest tests/test_document_fetcher.py -v 2>&1 | tail -15
```

Expected: `3 passed`

---

## Task 5: DocumentManager Service

**Files:**
- Create: `backend/app/services/document_manager.py`
- Create: `backend/tests/test_document_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_document_manager.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.services.document_manager import DocumentManager


@pytest.mark.asyncio
async def test_pre_fetch_skips_existing_url():
    doc_items = [{"url": "https://sec.gov/doc.htm", "doc_type": "10-Q", "filename": "doc.htm"}]

    mock_db = AsyncMock()
    existing_doc = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_doc
    mock_db.execute = AsyncMock(return_value=mock_result)

    manager = DocumentManager()
    result = await manager.pre_fetch(
        ticker="AAPL",
        asset_id=uuid.uuid4(),
        doc_items=doc_items,
        db=mock_db,
    )

    assert result["skipped"] == 1
    assert result["fetched"] == 0


@pytest.mark.asyncio
async def test_pre_fetch_downloads_new_url():
    doc_items = [{"url": "https://sec.gov/doc.htm", "doc_type": "10-Q", "filename": "doc.htm"}]

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    fake_content = b"%PDF-1.4 fake pdf content"

    manager = DocumentManager()
    with patch.object(manager, "_download", new_callable=AsyncMock, return_value=fake_content), \
         patch.object(manager, "_save_file", return_value="/uploads/AAPL/10-Q/doc.htm"), \
         patch.object(manager, "_enqueue_ingest", new_callable=AsyncMock):
        result = await manager.pre_fetch(
            ticker="AAPL",
            asset_id=uuid.uuid4(),
            doc_items=doc_items,
            db=mock_db,
        )

    assert result["fetched"] == 1
    assert result["skipped"] == 0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && docker compose exec backend pytest tests/test_document_manager.py -v 2>&1 | tail -15
```

Expected: `ImportError` for `document_manager`

- [ ] **Step 3: Implement DocumentManager**

```python
# backend/app/services/document_manager.py
from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger(__name__)

EDGAR_HEADERS = {"User-Agent": "Zentri contact@zentri.app"}


def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


class DocumentManager:
    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers=EDGAR_HEADERS)
            resp.raise_for_status()
            return resp.content

    def _save_file(self, content: bytes, ticker: str, doc_type: str, doc_id: uuid.UUID, filename: str) -> str:
        dest_dir = _upload_dir() / ticker.upper() / doc_type.replace("/", "_")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{doc_id}_{filename}"
        dest.write_bytes(content)
        return str(dest)

    async def _enqueue_ingest(self, doc_id: uuid.UUID) -> None:
        try:
            from arq.connections import ArqRedis, RedisSettings, create_pool
            from app.core.config import settings
            redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job("job_ingest_document", str(doc_id))
            await redis.aclose()
        except Exception as e:
            logger.warning("document_manager: failed to enqueue ingest doc_id=%s: %s", doc_id, e)

    async def check_exists(self, source_url: str, db: AsyncSession) -> Document | None:
        result = await db.execute(
            select(Document).where(Document.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def pre_fetch(
        self,
        ticker: str,
        asset_id: uuid.UUID | None,
        doc_items: list[dict],
        db: AsyncSession,
    ) -> dict:
        fetched = 0
        skipped = 0
        failed = 0

        for item in doc_items:
            url = item["url"]
            doc_type = item["doc_type"]
            filename = item["filename"]

            existing = await self.check_exists(url, db)
            if existing:
                logger.info("document_manager: skip existing source_url=%s", url)
                skipped += 1
                continue

            try:
                content = await self._download(url)
                doc_id = uuid.uuid4()
                file_path = self._save_file(content, ticker, doc_type, doc_id, filename)

                doc = Document(
                    id=doc_id,
                    filename=filename,
                    file_path=file_path,
                    asset_id=asset_id,
                    source_url=url,
                    doc_type=doc_type,
                    status="pending",
                )
                db.add(doc)
                await db.flush()
                await self._enqueue_ingest(doc_id)
                fetched += 1
                logger.info("document_manager: fetched doc_id=%s url=%s", doc_id, url)
            except Exception as e:
                failed += 1
                logger.warning("document_manager: failed url=%s: %s", url, e)

        if fetched > 0:
            await db.commit()

        return {"fetched": fetched, "skipped": skipped, "failed": failed}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && docker compose exec backend pytest tests/test_document_manager.py -v 2>&1 | tail -15
```

Expected: `2 passed`

---

## Task 6: ARQ Job — run_top_down_analysis

**Files:**
- Create: `backend/worker/jobs/run_top_down_analysis.py`
- Create: `backend/tests/test_run_top_down_analysis.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_run_top_down_analysis.py
from unittest.mock import MagicMock
import pytest
from worker.jobs.run_top_down_analysis import _parse_top_down


def test_parse_top_down_valid():
    content = """{
        "mega_trend": "AI boom pulling back 25% from ATH",
        "financial_health": "Revenue +18% YoY, strong margins",
        "swot": {
            "strengths": ["Market leader", "Strong brand"],
            "weaknesses": ["High valuation"],
            "opportunities": ["AI services expansion"],
            "threats": ["Regulatory risk"]
        },
        "verdict": "BUY",
        "target_price": 210.0
    }"""
    result = _parse_top_down(content)
    assert result is not None
    assert result["verdict"] == "BUY"
    assert result["swot"]["strengths"] == ["Market leader", "Strong brand"]
    assert result["target_price"] == 210.0


def test_parse_top_down_invalid_verdict():
    content = '{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}, "verdict": "MAYBE", "target_price": null}'
    assert _parse_top_down(content) is None


def test_parse_top_down_missing_swot_key():
    content = '{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": []}, "verdict": "HOLD", "target_price": null}'
    assert _parse_top_down(content) is None


def test_parse_top_down_markdown_wrapped():
    content = '```json\n{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}, "verdict": "SELL", "target_price": null}\n```'
    result = _parse_top_down(content)
    assert result is not None
    assert result["verdict"] == "SELL"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend && docker compose exec backend pytest tests/test_run_top_down_analysis.py -v 2>&1 | tail -15
```

Expected: `ImportError` for `run_top_down_analysis`

- [ ] **Step 3: Implement the job**

```python
# backend/worker/jobs/run_top_down_analysis.py
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.top_down_analysis import TopDownAnalysis
from app.models.llm_conversation import LLMConversation
from app.services.llm_service import get_llm_provider
from app.services.pipeline import create_log, finish_log, create_step, finish_step
from app.services.exchange_rate import get_current_usd_thb
from app.services.rag_service import get_or_create_collection, search
from app.services.document_fetcher import DocumentFetcher
from app.services.document_manager import DocumentManager

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a professional financial analyst performing a top-down analysis.
Analyse the provided data and respond ONLY with valid JSON in this exact format:
{
  "mega_trend": "<industry trend and ATH pullback context, 2-3 sentences>",
  "financial_health": "<revenue and profit trend summary, 2-3 sentences>",
  "swot": {
    "strengths": ["<item>", "..."],
    "weaknesses": ["<item>", "..."],
    "opportunities": ["<item>", "..."],
    "threats": ["<item>", "..."]
  },
  "verdict": "BUY" | "SELL" | "HOLD",
  "target_price": <number or null>
}
Do not include any text outside the JSON object."""

FORMAT_REMINDER = 'Respond ONLY with the JSON object as specified. All four SWOT keys required. verdict must be BUY, SELL, or HOLD.'


def _parse_top_down(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        data = json.loads(text)
        if data.get("verdict") not in ("BUY", "SELL", "HOLD"):
            return None
        swot = data.get("swot", {})
        required_keys = {"strengths", "weaknesses", "opportunities", "threats"}
        if not required_keys.issubset(swot.keys()):
            return None
        return data
    except (json.JSONDecodeError, AttributeError):
        return None


async def job_run_top_down_analysis(ctx: dict, symbol: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "run_top_down_analysis")
        current_step = None
        try:
            from app.models.asset import Asset
            from app.models.price import Price

            # Step 1: load_asset
            current_step = await create_step(db, log.id, "load_asset")
            a_result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
            asset = a_result.scalar_one_or_none()
            if not asset:
                raise ValueError(f"Asset {symbol} not found")

            since = datetime.now(timezone.utc) - timedelta(days=90)
            p_result = await db.execute(
                select(Price)
                .where(Price.asset_id == asset.id, Price.timestamp >= since)
                .order_by(desc(Price.timestamp))
                .limit(10)
            )
            prices = p_result.scalars().all()
            await finish_step(db, current_step, success=True, metadata={"symbol": symbol.upper()})

            # Step 2: fetch_documents
            current_step = await create_step(db, log.id, "fetch_documents")
            fetcher = DocumentFetcher()
            manager = DocumentManager()
            doc_items = await fetcher.fetch_for_ticker(symbol)
            fetch_result = await manager.pre_fetch(
                ticker=symbol,
                asset_id=asset.id,
                doc_items=doc_items,
                db=db,
            )
            await finish_step(db, current_step, success=True, metadata=fetch_result)

            # Step 3: rag_retrieval
            current_step = await create_step(db, log.id, "rag_retrieval")
            collection = get_or_create_collection(symbol)
            rag_chunks = search(collection, query=f"{symbol} financial analysis earnings revenue SWOT")
            rag_context = "\n\n---\n\n".join(rag_chunks) if rag_chunks else "No documents available."

            from app.services.news_rag import list_recent_articles
            news_articles = await list_recent_articles(db, symbol=symbol, limit=10)
            news_context = "\n".join(
                f"- [{a.title}] {a.summary or ''}" for a in news_articles
            ) if news_articles else ""
            await finish_step(db, current_step, success=True, metadata={
                "rag_chunks": len(rag_chunks),
                "news_articles": len(news_articles),
            })

            # Build prompt
            prices_txt = "\n".join(
                f"{p.timestamp.date()}: close={p.close}" for p in prices[:10]
            ) if prices else "No price history."

            user_prompt = f"""Asset: {symbol}

Recent price history (last 10 days):
{prices_txt}

Research documents context:
{rag_context}

Recent news:
{news_context}

Provide your top-down analysis as JSON."""

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            # Step 4: llm_call
            current_step = await create_step(db, log.id, "llm_call")
            llm = await get_llm_provider(db)
            resp = await llm.complete(messages)
            parsed = _parse_top_down(resp.content)

            if parsed is None:
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": FORMAT_REMINDER})
                resp2 = await llm.complete(messages)
                parsed = _parse_top_down(resp2.content)
                if parsed is None:
                    raise ValueError(f"LLM returned malformed JSON after retry: {resp2.content[:200]}")
                resp = resp2

            await finish_step(db, current_step, success=True, metadata={
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "cost_usd": float(resp.cost_usd),
                "verdict": parsed["verdict"],
            })

            # Step 5: save_analysis
            current_step = await create_step(db, log.id, "save_analysis")
            swot = parsed["swot"]
            analysis = TopDownAnalysis(
                asset_id=asset.id,
                job_id=str(log.id),
                mega_trend=parsed["mega_trend"],
                financial_health=parsed["financial_health"],
                swot_strengths=swot["strengths"],
                swot_weaknesses=swot["weaknesses"],
                swot_opportunities=swot["opportunities"],
                swot_threats=swot["threats"],
                verdict=parsed["verdict"],
                target_price=parsed.get("target_price"),
                provider=type(llm).__name__.replace("Provider", "").lower(),
                model=getattr(llm, "model", "unknown"),
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                cost_usd=resp.cost_usd,
            )
            db.add(analysis)
            await db.flush()

            for i, msg in enumerate(messages + [{"role": "assistant", "content": resp.content}]):
                db.add(LLMConversation(
                    analysis_id=analysis.id,
                    role=msg["role"],
                    content=msg["content"],
                    message_order=i,
                ))

            await db.commit()
            await finish_step(db, current_step, success=True, metadata={
                "verdict": parsed["verdict"],
                "analysis_id": str(analysis.id),
            })
            await finish_log(db, log, success=True)
            logger.info("run_top_down_analysis done symbol=%s verdict=%s", symbol, parsed["verdict"])
            return {"verdict": parsed["verdict"], "analysis_id": str(analysis.id)}

        except Exception as e:
            logger.exception("run_top_down_analysis failed symbol=%s: %s", symbol, e)
            if current_step is not None:
                await finish_step(db, current_step, success=False, error=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && docker compose exec backend pytest tests/test_run_top_down_analysis.py -v 2>&1 | tail -15
```

Expected: `4 passed`

---

## Task 7: API Router — top_down_analysis

**Files:**
- Create: `backend/app/api/top_down_analysis.py`

- [ ] **Step 1: Write the router**

```python
# backend/app/api/top_down_analysis.py
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.document import Document
from app.models.top_down_analysis import TopDownAnalysis
from app.models.user import User

router = APIRouter(prefix="/analysis/top-down", tags=["top-down-analysis"])
logger = get_logger(__name__)


def _serialize(a: TopDownAnalysis) -> dict:
    return {
        "id": str(a.id),
        "asset_id": str(a.asset_id) if a.asset_id else None,
        "mega_trend": a.mega_trend,
        "financial_health": a.financial_health,
        "swot": {
            "strengths": a.swot_strengths,
            "weaknesses": a.swot_weaknesses,
            "opportunities": a.swot_opportunities,
            "threats": a.swot_threats,
        },
        "verdict": a.verdict,
        "target_price": float(a.target_price) if a.target_price else None,
        "provider": a.provider,
        "model": a.model,
        "tokens_in": a.tokens_in,
        "tokens_out": a.tokens_out,
        "cost_usd": float(a.cost_usd),
        "created_at": a.created_at.isoformat(),
    }


@router.post("/{symbol}", status_code=202)
async def trigger_top_down_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_top_down_analysis", symbol.upper())
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("top_down_analysis triggered symbol=%s job_id=%s", symbol, job_id)
    return {"symbol": symbol.upper(), "job_id": job_id}


@router.get("/{symbol}/latest")
async def get_latest_top_down(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(TopDownAnalysis)
        .where(TopDownAnalysis.asset_id == asset.id)
        .order_by(desc(TopDownAnalysis.created_at))
        .limit(1)
    )
    analysis = a_result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No top-down analysis found for this asset")

    # Load documents used (all docs for this ticker)
    d_result = await db.execute(
        select(Document)
        .where(Document.asset_id == asset.id)
        .order_by(desc(Document.created_at))
    )
    docs = d_result.scalars().all()

    serialized = _serialize(analysis)
    serialized["documents"] = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_path": d.file_path,
            "doc_type": d.doc_type or "general",
            "source_url": d.source_url,
            "status": d.status,
        }
        for d in docs
        if d.status == "ready"
    ]
    return serialized


@router.get("/{symbol}/history")
async def get_top_down_history(
    symbol: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Asset).where(Asset.symbol == symbol.upper()))
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")

    a_result = await db.execute(
        select(TopDownAnalysis)
        .where(TopDownAnalysis.asset_id == asset.id)
        .order_by(desc(TopDownAnalysis.created_at))
        .limit(limit)
    )
    return [_serialize(a) for a in a_result.scalars().all()]
```

---

## Task 8: Wire Up — main.py + worker/main.py

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Register router in main.py**

In `backend/app/main.py`, add to the import block:

```python
from app.api import (
    analysis, assets, auth, cash_balance, chat, dividends, documents,
    events, feature_llm_config, health, import_pipeline, ipos, llm_pricing, llm_usage,
    overview, pipeline, platforms, portfolio, provider_config, research, settings, system, watchlist,
    top_down_analysis,
)
```

Then add after the last `app.include_router(...)` line:

```python
app.include_router(top_down_analysis.router, prefix="/api/v1")
```

- [ ] **Step 2: Register job in worker/main.py**

In `backend/worker/main.py`, add to imports:

```python
from worker.jobs.run_top_down_analysis import job_run_top_down_analysis
```

Then add to `WorkerSettings.functions` list:

```python
job_run_top_down_analysis,
```

- [ ] **Step 3: Restart and verify endpoint exists**

```bash
docker compose restart backend worker
curl -s http://localhost:8000/api/v1/analysis/top-down/AAPL/latest \
  -H "Authorization: Bearer <your_token>" | python3 -m json.tool | head -5
```

Expected: `{"detail": "Asset AAPL not found"}` or `{"detail": "No top-down analysis found"}` — either confirms the route is live.

---

## Task 9: Frontend — SwotGrid Component

**Files:**
- Create: `frontend/components/analysis/SwotGrid.tsx`

- [ ] **Step 1: Write the component**

```tsx
// frontend/components/analysis/SwotGrid.tsx
type SwotData = {
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  threats: string[]
}

type SwotGridProps = {
  swot: SwotData
}

const quadrants = [
  { key: 'strengths' as const, label: 'Strengths', colorVar: '--color-success' },
  { key: 'weaknesses' as const, label: 'Weaknesses', colorVar: '--color-destructive' },
  { key: 'opportunities' as const, label: 'Opportunities', colorVar: '--color-info' },
  { key: 'threats' as const, label: 'Threats', colorVar: '--color-warning' },
]

export function SwotGrid({ swot }: SwotGridProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {quadrants.map(({ key, label, colorVar }) => (
        <div
          key={key}
          className="rounded-lg border p-3"
          style={{ borderColor: `var(${colorVar})` }}
        >
          <p
            className="mb-2 text-xs font-semibold uppercase tracking-wide"
            style={{ color: `var(${colorVar})` }}
          >
            {label}
          </p>
          <ul className="space-y-1">
            {swot[key].map((item, i) => (
              <li key={i} className="text-sm text-[var(--color-text-secondary)]">
                • {item}
              </li>
            ))}
            {swot[key].length === 0 && (
              <li className="text-sm text-[var(--color-text-muted)] italic">None identified</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep SwotGrid
```

Expected: no output (no errors)

---

## Task 10: Frontend — DocumentsList Component

**Files:**
- Create: `frontend/components/analysis/DocumentsList.tsx`

- [ ] **Step 1: Write the component**

```tsx
// frontend/components/analysis/DocumentsList.tsx
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

type DocItem = {
  id: string
  filename: string
  file_path: string
  source_url: string | null
  status: string
}

type DocumentsListProps = {
  documents: DocItem[]
  ticker: string
}

function getDisplayPath(filePath: string, ticker: string): string {
  const idx = filePath.indexOf(`/${ticker.toUpperCase()}/`)
  return idx >= 0 ? filePath.slice(idx) : filePath
}

export function DocumentsList({ documents, ticker }: DocumentsListProps) {
  if (documents.length === 0) {
    return <p className="text-sm text-[var(--color-text-muted)] italic">No documents stored yet.</p>
  }

  return (
    <ul className="space-y-2">
      {documents.map((doc) => {
        const isExternal = doc.source_url && !doc.file_path
        const openUrl = isExternal
          ? doc.source_url!
          : `${API_BASE}/documents/${doc.id}/file`

        return (
          <li key={doc.id} className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--color-text-primary)]">
                {doc.filename}
              </p>
              <p className="truncate text-xs text-[var(--color-text-muted)]">
                {isExternal ? doc.source_url : getDisplayPath(doc.file_path, ticker)}
              </p>
            </div>
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-xs text-[var(--color-brand)] underline hover:no-underline"
            >
              ↗ Open
            </a>
          </li>
        )
      })}
    </ul>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep DocumentsList
```

Expected: no output (no errors)

---

## Task 11: Frontend — TopDownAnalysisCard + Page

**Files:**
- Create: `frontend/components/analysis/TopDownAnalysisCard.tsx`
- Create: `frontend/app/(auth)/analysis/[symbol]/page.tsx`

- [ ] **Step 1: Write TopDownAnalysisCard**

```tsx
// frontend/components/analysis/TopDownAnalysisCard.tsx
'use client'

import { SwotGrid } from './SwotGrid'
import { DocumentsList } from './DocumentsList'

type TopDownAnalysisData = {
  id: string
  mega_trend: string
  financial_health: string
  swot: {
    strengths: string[]
    weaknesses: string[]
    opportunities: string[]
    threats: string[]
  }
  verdict: 'BUY' | 'SELL' | 'HOLD'
  target_price: number | null
  created_at: string
  documents: {
    id: string
    filename: string
    file_path: string
    source_url: string | null
    status: string
  }[]
}

const verdictStyle: Record<string, string> = {
  BUY: 'var(--color-success)',
  SELL: 'var(--color-destructive)',
  HOLD: 'var(--color-warning)',
}

type Props = {
  data: TopDownAnalysisData
  ticker: string
  onRefresh: () => void
  loading: boolean
}

export function TopDownAnalysisCard({ data, ticker, onRefresh, loading }: Props) {
  return (
    <div className="space-y-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">
            {ticker} Top-Down Analysis
          </h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            {new Date(data.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data.target_price && (
            <span className="text-sm text-[var(--color-text-secondary)]">
              Target: {data.target_price.toFixed(2)}
            </span>
          )}
          <span
            className="rounded-full px-3 py-1 text-sm font-bold text-white"
            style={{ backgroundColor: verdictStyle[data.verdict] ?? 'var(--color-text-muted)' }}
          >
            {data.verdict}
          </span>
        </div>
      </div>

      {/* Mega Trend */}
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Mega Trend
        </p>
        <p className="text-sm text-[var(--color-text-primary)]">{data.mega_trend}</p>
      </div>

      {/* Financial Health */}
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          Financial Health
        </p>
        <p className="text-sm text-[var(--color-text-primary)]">{data.financial_health}</p>
      </div>

      {/* SWOT */}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
          SWOT Analysis
        </p>
        <SwotGrid swot={data.swot} />
      </div>

      {/* Documents */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
            Documents used ({data.documents.length})
          </p>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="rounded-md bg-[var(--color-brand)] px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Fetch & Analyze'}
          </button>
        </div>
        <DocumentsList documents={data.documents} ticker={ticker} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write the page**

```tsx
// frontend/app/(auth)/analysis/[symbol]/page.tsx
'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { TopDownAnalysisCard } from '@/components/analysis/TopDownAnalysisCard'
import { apiFetch } from '@/lib/api'

export default function TopDownAnalysisPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    try {
      const res = await apiFetch(`/analysis/top-down/${symbol}/latest`)
      setData(res)
      setError(null)
    } catch {
      setError('No analysis found. Click Fetch & Analyze to run one.')
    }
  }

  async function trigger() {
    setLoading(true)
    try {
      await apiFetch(`/analysis/top-down/${symbol}`, { method: 'POST' })
      // Poll until result appears (max 120s)
      for (let i = 0; i < 24; i++) {
        await new Promise((r) => setTimeout(r, 5000))
        try {
          const res = await apiFetch(`/analysis/top-down/${symbol}/latest`)
          setData(res)
          setError(null)
          break
        } catch {}
      }
    } catch (e: any) {
      setError(e.message ?? 'Failed to trigger analysis')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [symbol])

  return (
    <div className="mx-auto max-w-2xl py-8 px-4">
      <h1 className="mb-6 text-2xl font-bold text-[var(--color-text-primary)]">
        {symbol?.toUpperCase()} — Top-Down Analysis
      </h1>
      {error && !data && (
        <div className="rounded-lg border border-[var(--border)] p-4 text-sm text-[var(--color-text-secondary)]">
          {error}
          <button
            onClick={trigger}
            disabled={loading}
            className="ml-3 rounded-md bg-[var(--color-brand)] px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {loading ? 'Running…' : 'Fetch & Analyze'}
          </button>
        </div>
      )}
      {data && (
        <TopDownAnalysisCard
          data={data}
          ticker={symbol?.toUpperCase() ?? ''}
          onRefresh={trigger}
          loading={loading}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles with no errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output

- [ ] **Step 4: Open the page in the browser**

Navigate to `http://localhost:3000/analysis/AAPL`. Expected: page loads, shows error state with "Fetch & Analyze" button. Click it, wait ~30s, page should show the analysis result.

---

## Self-Review Notes

- All spec requirements covered:
  - Document dedup by source_url ✓ (Task 5)
  - SEC EDGAR 10-Q + 10-K fetch ✓ (Task 4)
  - News from existing DB ✓ (Task 6 job step 3)
  - User-supplied URLs already in store ✓ (DocumentManager.check_exists)
  - Structured SWOT output ✓ (Task 6 parser + model)
  - File serve endpoint ✓ (Task 3)
  - Open in new tab ✓ (Task 10)
  - Storage path display ✓ (Task 10)
  - Phase B foundation: DocumentManager methods are isolated and callable as tools ✓
- Type consistency: `TopDownAnalysisData` in frontend matches `_serialize()` shape in Task 7
- `apiFetch` utility assumed to exist at `@/lib/api` — check the existing codebase for the correct import path; adjust if different
