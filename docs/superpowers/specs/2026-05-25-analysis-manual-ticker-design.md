# Analysis Page — Manual Ticker Input

**Date:** 2026-05-25
**Status:** Approved

## Goal

Allow users to analyze any ticker they're interested in, not just candidates discovered by the AI discovery job. Users type a ticker, select from a live search dropdown, and land on the analysis detail page to trigger whichever analyses they want.

## Backend

### New: `GET /api/v1/assets/search?q=<query>`

Location: `backend/app/api/assets.py`

- Calls `yf.Search(q).quotes` from yfinance
- Returns up to 8 results: `[{symbol, name, exchange, type_display}]` where `type_display` is yfinance's `quoteType` (e.g. `Equity`, `ETF`, `INDEX`)
- Requires auth (existing `get_current_user` dep)
- Min query: 1 character

### Modified: `POST /api/v1/analysis/top-down/{symbol}`

Location: `backend/app/api/top_down_analysis.py`

Current behavior: returns 404 if asset not in DB.

New behavior:
- If asset not found → call `yf.Ticker(symbol).fast_info` to get name/exchange/asset type
- Create the Asset row with that data
- Proceed to queue `job_run_top_down_analysis` as before
- If yfinance can't resolve the ticker → return 404 with message `"Ticker {symbol} not found in market data"`

## Frontend

### New component: `TickerSearchInput`

Location: `frontend/components/analysis/TickerSearchInput.tsx`

- Text input with a dropdown list
- Debounces 300ms, min 1 char → `GET /api/v1/assets/search?q=...`
- Dropdown item format: `AAPL — Apple Inc. (NASDAQ)`
- Selecting an item → `router.push('/analysis/{symbol}')`
- Escape key or click-outside closes the dropdown
- Keyboard navigation (arrow keys + Enter) on dropdown items

### Modified: `frontend/app/(auth)/analysis/page.tsx`

- Add "Analyze Ticker" button in the header row, to the right of "Discover Candidates"
- Clicking toggles `TickerSearchInput` visibility below the header row (inline, not modal)
- A second click while open closes it

## Flow

```
User clicks "Analyze Ticker"
  → TickerSearchInput appears
  → User types "AAPL"
  → Dropdown shows: AAPL — Apple Inc. (NASDAQ), ...
  → User selects AAPL
  → router.push('/analysis/AAPL')
  → [symbol]/page.tsx loads with empty cards + trigger buttons
  → User triggers whichever analyses they want
```

## What does NOT change

- `[symbol]/page.tsx` — no changes; already handles new symbols with null data
- Discovery flow — unchanged
- Other analysis endpoints — unchanged

## Constraints

- Asset auto-creation only happens when `POST /api/v1/analysis/top-down/{symbol}` is called, not on search
- Use design tokens from `globals.css` — no hardcoded colors
- No emoji in UI
