# Analysis — Manual Ticker Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live-search ticker input to the Analysis index page so users can navigate to any ticker's analysis page — not just AI-discovered candidates.

**Architecture:** New `GET /assets/market-search` endpoint wraps yfinance search. `POST /analysis/top-down/{symbol}` auto-creates the Asset row if the ticker isn't in the DB yet. A new `TickerSearchInput` frontend component handles debounced search + keyboard navigation and pushes the user to `/analysis/{symbol}` on selection.

**Tech Stack:** Python/FastAPI, yfinance, Next.js App Router, React, Tailwind CSS tokens

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/api/assets.py` | Add `GET /assets/market-search` endpoint |
| Modify | `backend/app/api/top_down_analysis.py` | Auto-create asset when not in DB |
| Create | `frontend/components/analysis/TickerSearchInput.tsx` | Debounced combobox, navigate on select |
| Modify | `frontend/app/(auth)/analysis/page.tsx` | Toggle button + render TickerSearchInput |

---

## Task 1: Backend — Market search endpoint

**Files:**
- Modify: `backend/app/api/assets.py`
- Create: `backend/tests/test_market_search.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_market_search.py`:

```python
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_market_search_aapl_returns_results(auth_client: AsyncClient):
    res = await auth_client.get("/api/v1/assets/market-search?q=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) <= 8
    symbols = [r["symbol"] for r in data]
    assert "AAPL" in symbols
    first = next(r for r in data if r["symbol"] == "AAPL")
    assert "name" in first
    assert "exchange" in first
    assert "type_display" in first


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_market_search.py -v
```

Expected: FAIL — 404 Not Found (route doesn't exist yet)

- [ ] **Step 3: Add the endpoint to assets.py**

Open `backend/app/api/assets.py`. Find the existing `GET /assets/search` route (line ~53). Add the new route **immediately after it** and **before any `/{...}` path parameter routes** to avoid FastAPI route shadowing:

```python
@router.get("/market-search")
async def market_search_tickers(
    q: str = Query(min_length=1),
    _: User = Depends(get_current_user),
):
    import asyncio
    import yfinance as yf

    def _search(query: str) -> list[dict]:
        try:
            results = yf.Search(query, max_results=8).quotes
            out = []
            for r in results:
                symbol = r.get("symbol") or ""
                if not symbol:
                    continue
                out.append({
                    "symbol": symbol,
                    "name": r.get("shortname") or r.get("longname") or symbol,
                    "exchange": r.get("exchange") or "",
                    "type_display": r.get("quoteType") or "",
                })
            return out[:8]
        except Exception:
            return []

    return await asyncio.get_running_loop().run_in_executor(None, _search, q)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_market_search.py -v
```

Expected: PASS (note: `test_market_search_aapl_returns_results` makes a real network call — run it in an environment with internet access)

---

## Task 2: Backend — Auto-create asset in trigger_top_down_analysis

**Files:**
- Modify: `backend/app/api/top_down_analysis.py`
- Create: `backend/tests/test_top_down_manual_trigger.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_top_down_manual_trigger.py`:

```python
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


@pytest.mark.anyio
async def test_trigger_top_down_unknown_symbol_auto_creates_asset(auth_client: AsyncClient):
    fake_quotes = [{"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NMS", "quoteType": "EQUITY"}]
    # patch at the module level — matches `import yfinance as yf; yf.Search(...)` inside the endpoint
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_top_down_manual_trigger.py -v
```

Expected: `test_trigger_top_down_unknown_symbol_auto_creates_asset` FAIL — 404 "Asset AAPL not found"

- [ ] **Step 3: Replace trigger_top_down_analysis in top_down_analysis.py**

Replace the existing `trigger_top_down_analysis` function (lines 89–112) with:

```python
@router.post("/{symbol}", status_code=202)
async def trigger_top_down_analysis(
    symbol: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import asyncio
    import yfinance as yf

    sym = symbol.upper()
    result = await db.execute(select(Asset).where(Asset.symbol == sym))
    asset = result.scalar_one_or_none()

    if not asset:
        def _fetch_quote(s: str):
            try:
                quotes = yf.Search(s, max_results=10).quotes
                return next((q for q in quotes if (q.get("symbol") or "").upper() == s), None)
            except Exception:
                return None

        match = await asyncio.get_running_loop().run_in_executor(None, _fetch_quote, sym)
        if not match:
            raise HTTPException(status_code=404, detail=f"Ticker {sym} not found in market data")

        quote_type = (match.get("quoteType") or "").upper()
        if sym.endswith(".BK"):
            asset_type, currency = "thai_stock", "THB"
        elif quote_type == "ETF":
            asset_type, currency = "etf", "USD"
        else:
            asset_type, currency = "us_stock", "USD"

        name = match.get("shortname") or match.get("longname") or sym
        from app.services.asset import create_asset
        asset = await create_asset(db, current_user.id, sym, asset_type, name, currency)
        logger.info("auto-created asset for analysis symbol=%s user=%s", sym, current_user.id)

    job_id = None
    try:
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_run_top_down_analysis", sym)
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        pass

    logger.info("top_down_analysis triggered symbol=%s job_id=%s", sym, job_id)
    return {"symbol": sym, "job_id": job_id}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_top_down_manual_trigger.py -v
```

Expected: PASS

- [ ] **Step 5: Verify existing analysis tests still pass**

```bash
cd backend && pytest tests/test_analysis.py -v
```

Expected: PASS (no regressions)

---

## Task 3: Frontend — TickerSearchInput component

**Files:**
- Create: `frontend/components/analysis/TickerSearchInput.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/analysis/TickerSearchInput.tsx`:

```tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

type TickerResult = {
  symbol: string
  name: string
  exchange: string
  type_display: string
}

export function TickerSearchInput({ onClose }: { onClose: () => void }) {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await api.get(`/api/v1/assets/market-search?q=${encodeURIComponent(query)}`)
        if (res.ok) setResults(await res.json())
      } finally {
        setLoading(false)
        setActiveIndex(-1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  function navigate(symbol: string) {
    onClose()
    router.push(`/analysis/${symbol}`)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      setActiveIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      navigate(results[activeIndex].symbol)
    }
  }

  return (
    <div ref={containerRef} className="relative w-72">
      <input
        ref={inputRef}
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search ticker…"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-brand)]"
      />
      {(results.length > 0 || loading) && (
        <ul className="absolute left-0 top-full z-50 mt-1 w-full overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-md">
          {loading && (
            <li className="px-3 py-2 text-xs text-[var(--color-text-muted)]">Searching…</li>
          )}
          {results.map((r, i) => (
            <li
              key={r.symbol}
              className={`cursor-pointer px-3 py-2 text-sm transition-colors ${
                i === activeIndex
                  ? 'bg-[var(--color-brand)]/10 text-[var(--color-text-primary)]'
                  : 'hover:bg-[var(--color-brand)]/5 text-[var(--color-text-primary)]'
              }`}
              onMouseDown={() => navigate(r.symbol)}
            >
              <span className="font-semibold">{r.symbol}</span>
              <span className="ml-2 text-[var(--color-text-muted)]">
                {r.name} · {r.exchange}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Check TypeScript compiles cleanly**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep TickerSearchInput
```

Expected: no output (no errors)

---

## Task 4: Frontend — Wire into Analysis index page

**Files:**
- Modify: `frontend/app/(auth)/analysis/page.tsx`

- [ ] **Step 1: Add import and state**

At the top of `page.tsx`, add the import alongside existing imports:

```tsx
import { TickerSearchInput } from '@/components/analysis/TickerSearchInput'
```

Inside `AnalysisIndexPage`, add state alongside `discovering`:

```tsx
const [showTickerSearch, setShowTickerSearch] = useState(false)
```

- [ ] **Step 2: Add button and conditional render**

Replace the header `<div className="flex items-center justify-between">` block:

```tsx
<div className="flex items-center justify-between">
  <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">
    Top-Down Analysis
  </h1>
  <div className="flex items-center gap-2">
    <Button
      onClick={() => setShowTickerSearch(v => !v)}
      variant="outline"
      className="px-4 py-2 text-sm font-medium"
    >
      Analyze Ticker
    </Button>
    <Button
      onClick={discover}
      disabled={discovering}
      className="px-4 py-2 text-sm font-medium"
    >
      {discovering ? 'Scanning…' : '⟳ Discover Candidates'}
    </Button>
  </div>
</div>

{showTickerSearch && (
  <TickerSearchInput onClose={() => setShowTickerSearch(false)} />
)}
```

- [ ] **Step 3: Check TypeScript compiles cleanly**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "analysis/page|TickerSearch"
```

Expected: no output

- [ ] **Step 4: Start dev server and verify manually**

```bash
cd frontend && npm run dev
```

Test the following:
1. Click "Analyze Ticker" → input appears below header
2. Click again → input closes
3. Type "AAPL" → dropdown shows Apple results after ~300ms
4. Press ArrowDown → highlights first result
5. Press Enter → navigates to `/analysis/AAPL`
6. Type "TSLA" → click result → navigates to `/analysis/TSLA`
7. Press Escape → input closes
8. Click outside the input → input closes
9. "Discover Candidates" button still works as before
