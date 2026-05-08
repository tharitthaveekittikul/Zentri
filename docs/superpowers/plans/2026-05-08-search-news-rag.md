# Search News + RAG Research Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `search_news(query, symbol?)` as a chat tool backed by a RAG store. Fetched articles are saved to DB with embeddings (pgvector) for cache-first retrieval. Users can browse their Research Library filtered by symbol and date.

**Architecture:** `NewsRagStore` table stores articles + vector embeddings. `news_rag.py` service: check cache (< 6h) → fetch from financial news API → embed → save → return top 5. `search_news` is added to `chat_tools.py`. Research Library API exposes a GET endpoint. Frontend shows a browsable article list.

**Dependencies:** Plan 3 (Chat Tool-Calling) must be complete — `search_news` is added to `TOOL_DEFINITIONS` and `execute_tool`.

**Tech Stack:** Python, SQLAlchemy async, pgvector (psycopg2 extension), Alembic, sentence-transformers or OpenAI embeddings, FastAPI, Next.js

**Before starting — install dependencies:**
```bash
cd backend && uv pip install sentence-transformers finnhub-python
```
Also add `FINNHUB_API_KEY=your_key` to `.env`. If no key is configured, `search_news` returns cached results only and warns in logs.

---

## File Map

| File | Change |
|---|---|
| `backend/app/models/news_rag_store.py` | NEW: NewsRagStore model |
| `backend/app/models/__init__.py` | Register model |
| `backend/alembic/versions/<ts>_add_news_rag_store.py` | NEW: migration with vector column |
| `backend/app/services/news_rag.py` | NEW: fetch, embed, cache, search |
| `backend/app/services/chat_tools.py` | Add search_news tool definition + executor |
| `backend/app/api/research.py` | NEW: GET /research/news endpoint |
| `backend/app/main.py` | Register research router |
| `backend/tests/test_news_rag.py` | NEW |
| `frontend/lib/api/research.ts` | NEW: API client |
| `frontend/components/research/ResearchLibrary.tsx` | NEW: article list component |

---

### Task 1: Create NewsRagStore Model

**Files:**
- Create: `backend/app/models/news_rag_store.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_news_rag.py`:

```python
def test_news_rag_store_model_importable():
    from app.models.news_rag_store import NewsRagStore
    assert NewsRagStore.__tablename__ == "news_rag_store"

def test_news_rag_store_has_required_fields():
    from app.models.news_rag_store import NewsRagStore
    cols = {c.key for c in NewsRagStore.__table__.columns}
    assert "headline" in cols
    assert "summary" in cols
    assert "symbol" in cols
    assert "fetched_at" in cols
    assert "source" in cols
    assert "url" in cols
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_news_rag.py::test_news_rag_store_model_importable -v
```

- [ ] **Step 3: Create model**

Create `backend/app/models/news_rag_store.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsRagStore(Base):
    __tablename__ = "news_rag_store"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

> **Note:** Vector embedding column is added separately in the migration using raw SQL (`ALTER TABLE ... ADD COLUMN embedding vector(384)`) after enabling the pgvector extension. SQLAlchemy-pgvector can be added later if the project adopts it.

- [ ] **Step 4: Register in `__init__.py`**

```python
from app.models.news_rag_store import NewsRagStore  # noqa: F401
```

- [ ] **Step 5: Run tests**

```bash
cd backend && uv run pytest tests/test_news_rag.py::test_news_rag_store_model_importable tests/test_news_rag.py::test_news_rag_store_has_required_fields -v
```
Expected: `PASSED`.

---

### Task 2: Create Migration with pgvector

**Files:**
- Create: `backend/alembic/versions/<timestamp>_add_news_rag_store.py`

- [ ] **Step 1: Generate base migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "add_news_rag_store"
```

- [ ] **Step 2: Edit generated migration to add pgvector extension + embedding column**

Open the generated file. Add pgvector setup to `upgrade()`:

```python
def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create table (autogenerated code will be here)
    op.create_table(
        "news_rag_store",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_rag_store_symbol", "news_rag_store", ["symbol"])
    op.create_index("ix_news_rag_store_fetched_at", "news_rag_store", ["fetched_at"])

    # Add vector embedding column (384 dims for all-MiniLM-L6-v2)
    op.execute("ALTER TABLE news_rag_store ADD COLUMN IF NOT EXISTS embedding vector(384)")


def downgrade() -> None:
    op.drop_table("news_rag_store")
```

- [ ] **Step 3: Apply migration**

```bash
cd backend && uv run alembic upgrade head
```
Expected: no errors, table + vector column created.

---

### Task 3: Create news_rag.py service

**Files:**
- Create: `backend/app/services/news_rag.py`
- Test: `backend/tests/test_news_rag.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.news_rag import search_news_for_context, _is_cache_fresh

def test_is_cache_fresh_returns_false_for_old_articles():
    from datetime import datetime, timedelta, timezone
    old_dt = datetime.now(timezone.utc) - timedelta(hours=7)
    assert _is_cache_fresh(old_dt) is False

def test_is_cache_fresh_returns_true_for_recent():
    from datetime import datetime, timedelta, timezone
    recent_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    assert _is_cache_fresh(recent_dt) is True

@pytest.mark.asyncio
async def test_search_news_returns_list_of_dicts(db_session):
    with patch("app.services.news_rag._fetch_from_api") as mock_fetch:
        mock_fetch.return_value = [
            {"headline": "AAPL hits record", "summary": "Apple stock rose 3%.", "source": "Reuters", "url": "https://example.com/1"}
        ]
        with patch("app.services.news_rag._embed_text", return_value=[0.1] * 384):
            results = await search_news_for_context("AAPL earnings", "AAPL", db_session)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "headline" in results[0]
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_news_rag.py -k "cache_fresh or search_news" -v
```

- [ ] **Step 3: Create news_rag.py**

Create `backend/app/services/news_rag.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.news_rag_store import NewsRagStore

logger = get_logger(__name__)

CACHE_TTL_HOURS = 6
MAX_RESULTS = 5


def _is_cache_fresh(fetched_at: datetime) -> bool:
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - fetched_at) < timedelta(hours=CACHE_TTL_HOURS)


def _embed_text(text: str) -> list[float]:
    """Generate embedding using sentence-transformers (all-MiniLM-L6-v2, 384 dims).
    Falls back to zero vector if model unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception:
        logger.warning("Embedding model unavailable, using zero vector")
        return [0.0] * 384


async def _fetch_from_api(query: str, symbol: str | None) -> list[dict]:
    """Fetch news from financial news API. Returns list of {headline, summary, source, url}."""
    # Check for configured news API key
    api_key = getattr(settings, "FINNHUB_API_KEY", None) or getattr(settings, "NEWS_API_KEY", None)
    if not api_key:
        logger.warning("No news API key configured (FINNHUB_API_KEY or NEWS_API_KEY). Returning empty.")
        return []

    # Try Finnhub if key is set as FINNHUB_API_KEY
    if getattr(settings, "FINNHUB_API_KEY", None):
        try:
            from datetime import date, timedelta
            today = date.today().isoformat()
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            url = f"https://finnhub.io/api/v1/company-news?symbol={symbol or ''}&from={week_ago}&to={today}&token={api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                articles = resp.json()[:MAX_RESULTS]
                return [
                    {
                        "headline": a.get("headline", ""),
                        "summary": a.get("summary", ""),
                        "source": a.get("source", ""),
                        "url": a.get("url", ""),
                    }
                    for a in articles
                ]
        except Exception as e:
            logger.error("Finnhub fetch failed: %s", e)
            return []

    return []


async def search_news_for_context(
    query: str, symbol: str | None, db: AsyncSession
) -> list[dict[str, Any]]:
    """Return top articles for query. Checks cache first, fetches API on miss, saves to DB."""

    # Check cache
    stmt = select(NewsRagStore).where(NewsRagStore.query == query)
    if symbol:
        stmt = stmt.where(NewsRagStore.symbol == symbol.upper())
    stmt = stmt.order_by(desc(NewsRagStore.fetched_at)).limit(MAX_RESULTS)
    cached = (await db.execute(stmt)).scalars().all()

    if cached and _is_cache_fresh(cached[0].fetched_at):
        logger.debug("news cache hit: query=%s symbol=%s", query, symbol)
        return [{"headline": a.headline, "summary": a.summary, "source": a.source, "url": a.url} for a in cached]

    # Fetch from API
    articles = await _fetch_from_api(query, symbol)
    if not articles:
        return [{"headline": a.headline, "summary": a.summary, "source": a.source, "url": a.url} for a in cached]

    # Save to DB with embeddings
    now = datetime.now(timezone.utc)
    for article in articles:
        text_to_embed = f"{article['headline']} {article['summary']}"
        embedding = _embed_text(text_to_embed)
        row = NewsRagStore(
            symbol=symbol.upper() if symbol else None,
            query=query,
            headline=article["headline"],
            summary=article["summary"],
            source=article.get("source"),
            url=article.get("url"),
            fetched_at=now,
        )
        db.add(row)
        # Store embedding via raw SQL after flush
        await db.flush()
        await db.execute(
            f"UPDATE news_rag_store SET embedding = :emb WHERE id = :id",
            {"emb": str(embedding), "id": str(row.id)},
        )

    await db.commit()
    return articles[:MAX_RESULTS]
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_news_rag.py -v
```
Expected: `PASSED`.

---

### Task 4: Add search_news to chat_tools.py

**Files:**
- Modify: `backend/app/services/chat_tools.py`
- Test: `backend/tests/test_chat_tools.py`

- [ ] **Step 1: Write failing test**

```python
def test_tool_definitions_contains_search_news():
    from app.services.chat_tools import TOOL_DEFINITIONS
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert "search_news" in names

@pytest.mark.asyncio
async def test_execute_search_news(db_session, user_factory):
    user = await user_factory()
    with patch("app.services.chat_tools.search_news_for_context", new=AsyncMock(return_value=[
        {"headline": "AAPL up 3%", "summary": "Apple rose.", "source": "Reuters", "url": "https://example.com"}
    ])):
        result = await execute_tool("search_news", {"query": "Apple earnings", "symbol": "AAPL"}, user.id, db_session)
    import json
    parsed = json.loads(result)
    assert parsed[0]["headline"] == "AAPL up 3%"
```

- [ ] **Step 2: Run to verify fail**

```bash
cd backend && uv run pytest tests/test_chat_tools.py::test_tool_definitions_contains_search_news -v
```

- [ ] **Step 3: Add search_news to TOOL_DEFINITIONS and execute_tool**

In `backend/app/services/chat_tools.py`, append to `TOOL_DEFINITIONS`:

```python
{
    "name": "search_news",
    "description": "Search for recent financial news articles about a topic or ticker symbol.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query, e.g. 'NVDA earnings Q1 2026'"},
            "symbol": {"type": "string", "description": "Optional ticker symbol to narrow results"},
        },
        "required": ["query"],
    },
},
```

Add to `execute_tool()` before the final `raise ValueError`:

```python
if name == "search_news":
    from app.services.news_rag import search_news_for_context
    query = input_.get("query", "")
    symbol = input_.get("symbol")
    articles = await search_news_for_context(query, symbol, db)
    return json.dumps(articles)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && uv run pytest tests/test_chat_tools.py -v
```
Expected: `PASSED`.

---

### Task 5: Research Library API + Frontend

**Files:**
- Create: `backend/app/api/research.py`
- Modify: `backend/app/main.py`
- Create: `frontend/lib/api/research.ts`
- Create: `frontend/components/research/ResearchLibrary.tsx`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_get_research_news_returns_list(client, auth_headers):
    resp = await client.get("/research/news", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_get_research_news_filter_by_symbol(client, auth_headers, news_in_db):
    resp = await client.get("/research/news?symbol=AAPL", headers=auth_headers)
    assert resp.status_code == 200
    for item in resp.json():
        assert item["symbol"] == "AAPL"
```

- [ ] **Step 2: Create research.py API**

Create `backend/app/api/research.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.news_rag_store import NewsRagStore
from app.models.user import User

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/news")
async def list_news(
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NewsRagStore).order_by(desc(NewsRagStore.fetched_at)).limit(limit)
    if symbol:
        stmt = stmt.where(NewsRagStore.symbol == symbol.upper())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "symbol": r.symbol,
            "headline": r.headline,
            "summary": r.summary,
            "source": r.source,
            "url": r.url,
            "fetched_at": r.fetched_at.isoformat(),
        }
        for r in rows
    ]
```

- [ ] **Step 3: Register router in main.py**

```python
from app.api.research import router as research_router
app.include_router(research_router)
```

- [ ] **Step 4: Run API tests**

```bash
cd backend && uv run pytest tests/ -k "research" -v
```
Expected: `PASSED`.

- [ ] **Step 5: Create frontend API client**

Create `frontend/lib/api/research.ts`:

```typescript
import { apiFetch } from "@/lib/api"

export interface NewsArticle {
  id: string
  symbol: string | null
  headline: string
  summary: string
  source: string | null
  url: string | null
  fetched_at: string
}

export async function getResearchNews(symbol?: string): Promise<NewsArticle[]> {
  const params = symbol ? `?symbol=${encodeURIComponent(symbol)}` : ""
  return apiFetch(`/research/news${params}`)
}
```

- [ ] **Step 6: Create ResearchLibrary component**

Create `frontend/components/research/ResearchLibrary.tsx`:

```tsx
"use client"

import { useEffect, useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { ExternalLink, Newspaper } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { NewsArticle, getResearchNews } from "@/lib/api/research"

export function ResearchLibrary() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [symbolFilter, setSymbolFilter] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getResearchNews(symbolFilter || undefined)
      .then(setArticles)
      .finally(() => setLoading(false))
  }, [symbolFilter])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Newspaper className="h-5 w-5" />
          Research Library
        </CardTitle>
        <Input
          placeholder="Filter by symbol (e.g. AAPL)"
          value={symbolFilter}
          onChange={(e) => setSymbolFilter(e.target.value.toUpperCase())}
          className="max-w-xs"
        />
      </CardHeader>
      <CardContent>
        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!loading && articles.length === 0 && (
          <p className="text-sm text-muted-foreground">No articles yet. Ask the chat assistant about a stock to fetch news.</p>
        )}
        <div className="space-y-3">
          {articles.map((a) => (
            <div key={a.id} className="border rounded-md p-3 space-y-1">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium leading-snug">{a.headline}</p>
                {a.url && (
                  <a href={a.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 text-muted-foreground shrink-0" />
                  </a>
                )}
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2">{a.summary}</p>
              <div className="flex items-center gap-2">
                {a.symbol && <Badge variant="outline" className="text-xs">{a.symbol}</Badge>}
                {a.source && <span className="text-xs text-muted-foreground">{a.source}</span>}
                <span className="text-xs text-muted-foreground ml-auto">
                  {formatDistanceToNow(new Date(a.fetched_at), { addSuffix: true })}
                </span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 7: Add Research Library to appropriate page**

Add `<ResearchLibrary />` to the Watchlist page or Chat page sidebar, wherever makes most sense in the existing layout.

- [ ] **Step 8: Verify in browser**

```bash
cd frontend && npm run dev
```

Test: ask chat "What's the latest news on AAPL?" — article should appear in Research Library after the chat responds.
