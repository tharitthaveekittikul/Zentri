# Events Calendar — Design Spec

**Date:** 2026-05-06
**Status:** Approved

## Overview

Evolve the `/dividends` page into a unified `/events` Market Calendar that shows multiple event types (dividends + IPOs) with color-coded calendar dots, watchlist integration, and on-demand LLM analysis for IPO events.

---

## 1. Backend & Data Model

### New: `IpoEvent` model (`backend/app/models/ipo_event.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `symbol` | str | Ticker symbol |
| `company_name` | str | |
| `ipo_date` | date | The listing date |
| `price_low` | Decimal nullable | Expected price range low |
| `price_high` | Decimal nullable | Expected price range high |
| `sector` | str nullable | From yfinance |
| `status` | enum | `upcoming`, `priced`, `listed` |
| `source` | str | `yfinance` (swappable later) |
| `created_at` / `updated_at` | datetime | |

**Seeding strategy:** Pull from watchlist tickers that have `ipoDate` in `yf.Ticker(symbol).info`. yfinance has limited IPO calendar coverage — this is intentional for v1, source is swappable later without schema change.

### LLM Assignment

Add `"ipo_analysis"` to `FEATURE_KEYS` in `backend/app/models/feature_llm_config.py`. Users assign their preferred provider/model in Settings → AI & LLM tab — same UI pattern as existing features (`watchlist_scan`, `portfolio_analysis`, etc.).

### Unified Calendar API

`GET /api/v1/events/calendar?months=3`

Response shape:
```json
{
  "months": [
    {
      "year": 2026,
      "month": 5,
      "events": [
        { "event_type": "dividend", "id": "...", "symbol": "AAPL", "ex_date": "2026-05-10", ... },
        { "event_type": "ipo", "id": "...", "symbol": "XYZ", "ipo_date": "2026-05-15", ... }
      ]
    }
  ]
}
```

Fetches dividends + IPOs in parallel from DB, merges by month.

### AI Analysis API

`POST /api/v1/ipos/{event_id}/analyze`

- Check `ai_analyses` table for cached result (same `asset_id`, created today) — return if found
- Load user's `ipo_analysis` `FeatureLLMConfig` via `llm_gateway`
- If not configured: return 400 `{ "detail": "Please assign an LLM to IPO Analysis in Settings → AI & LLM" }`
- Build prompt with: symbol, company, sector, IPO date, price range, yfinance info (description, market cap, P/E)
- Call `llm_gateway` with user's assigned provider/model
- Store result in `ai_analyses` — add nullable `ipo_event_id` FK column and make `asset_id` nullable via migration, so IPO analyses don't require a portfolio holding
- Return result

**Default system prompt** (customizable in Settings):
> "You are a financial analyst. Given IPO data, assess whether to Buy, Watch, or Skip. Provide a suggested entry price and 2-3 sentence reasoning. Be concise and data-driven."

### Route Changes

- Old `/api/v1/dividends/calendar` — unchanged, kept for dividend-only use
- New `/api/v1/events/calendar` — unified endpoint
- New `/api/v1/ipos/{event_id}/analyze` — AI analysis

---

## 2. Frontend Structure

### Route & Navigation

- Move `frontend/app/(auth)/dividends/` → `frontend/app/(auth)/events/`
- Sidebar nav: "Dividends" → "Events"
- Add redirect: `/dividends` → `/events`

### Page Layout

```
[Events]                                    [Refresh]

[All] [Dividends] [IPOs] [Watchlist only]   ← filter chips

┌─────────────────────────────────────────┐
│              May 2026                   │
│  Su  Mo  Tu  We  Th  Fr  Sa            │
│  ...  5●  ...  12●🔵  ...  18●🟠  ...  │  ← color-coded dots
└─────────────────────────────────────────┘

Upcoming Events
┌────────────────────────────────────────────────────┐
│ Symbol │ Type     │ Date    │ Details   │ Status   │
│ AAPL   │ Dividend │ May 10  │ $0.25/sh  │ upcoming │
│ XYZ    │ IPO      │ May 18  │ $10–$14   │ upcoming │
└────────────────────────────────────────────────────┘
```

### Calendar Dot Colors

| Event Type | Color | Notes |
|---|---|---|
| Dividend | Blue | Existing |
| IPO | Orange | New |
| Watchlist match | Star/highlight on dot | Overlay indicator |

### Filter Chips

- `All` — show everything (default)
- `Dividends` — dividends only
- `IPOs` — IPOs only
- `Watchlist only` — any event type but only for watchlist symbols

### Click Behavior

**Dividend event** → existing confirm dialog (unchanged)

**IPO event** → new side panel:
- Company name, symbol, sector
- IPO date, price range (N/A if yfinance doesn't have it)
- Status badge (upcoming / priced / listed)
- Watchlist badge if symbol is in user's watchlist
- "Analyze with AI" button
  - Shows spinner while waiting
  - If LLM not configured: "Set up AI in Settings →" link
  - Result: verdict chip (Buy / Watch / Skip) + suggested price + reasoning
  - Re-analyze button to bypass cache

### Settings Page

Settings → AI & LLM tab: add `ipo_analysis` row — same component pattern as existing feature rows. No new UI component needed.

---

## 3. AI Analysis Flow

```
User clicks "Analyze with AI"
  → POST /api/v1/ipos/{event_id}/analyze
    → Check ai_analyses cache (today's date)
      → Hit: return cached result
      → Miss: load ipo_analysis FeatureLLMConfig
        → Not configured: return 400 + guidance message
        → Configured: build prompt + call llm_gateway
          → Parse verdict / target_price / reasoning
          → Store in ai_analyses
          → Return to frontend
```

Frontend renders result inline in the IPO detail panel. Re-analyze button bypasses cache and triggers a fresh call.

---

## Out of Scope (v1)

- Earnings events, stock splits — future event types, architecture supports them
- Push notifications for IPO events — future
- Auto-analysis of all IPOs in background — future
- Non-yfinance IPO data sources — future (source field is already swappable)
