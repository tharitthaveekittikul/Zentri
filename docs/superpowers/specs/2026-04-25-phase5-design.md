# Zentri Phase 5 — Market Overview & Asset Detail

**Date:** 2026-04-25
**Status:** Approved
**Phase:** 5 of 8
**Sequence:** A (of A→B→C→D remaining roadmap)

---

## 1. Overview

Phase 5 delivers the first real "dashboard moment" for Zentri — making all the price and portfolio data collected in Phases 1–4 visible and navigable. No AI features yet (Phase 6). No verdict cards.

**Features in scope:**
1. Backend overview endpoints (summary, allocation, performance)
2. Market overview page (`/`)
3. Asset detail page (`/portfolio/[symbol]`)
4. Privacy mode toggle
5. Global ⌘K command palette (search + grayed-out AI slot)

**Out of scope (Phase 6+):** BUY/SELL/HOLD verdict card, AI chat in palette, watchlist data in palette.

---

## 2. Backend Endpoints

### Overview Domain — `/api/v1/overview`

All three endpoints require JWT auth and query existing `holdings`, `assets`, and `prices` tables. No new DB tables or migrations needed.

| Endpoint | Returns |
|---|---|
| `GET /overview/summary` | `total_value`, `total_cost`, `total_pnl`, `total_pnl_pct`, `daily_change`, `daily_change_pct` (vs previous trading day close) |
| `GET /overview/allocation` | Array of `{ asset_type, value, pct }` — one entry per asset type held |
| `GET /overview/performance` | `{ portfolio: [{date, value}], benchmark: [{date, value}] }` — accepts `?range=1W|1M|3M|1Y` |

**Performance endpoint logic:** For each held asset, multiply `quantity` (from `holdings`) by closing price at each date (from `prices` hypertable), sum across all assets to get daily portfolio value. Compare against benchmark prices already stored in the `prices` hypertable (S&P500 `^GSPC`, SET `^SET`). Normalize both series to 100 at range start for apples-to-apples comparison.

### Asset Domain — `/api/v1/assets`

| Endpoint | Returns |
|---|---|
| `GET /assets/{symbol}/history` | Array of `{ time, open, high, low, close, volume }` — accepts `?range=1W|1M|3M|1Y` |

Transactions for the asset detail page are served by `GET /api/v1/portfolio/transactions?symbol={symbol}`. If this query param filter doesn't exist yet, it must be added as part of this phase's backend work.

---

## 3. Market Overview Page (`/`)

**Data:** TanStack Query fetching all three overview endpoints in parallel on mount.

**Layout (3 rows):**

**Row 1 — Summary bar**
- Total portfolio value (large, prominent)
- Total cost basis
- Total P&L (value + %)
- Daily change badge — green if positive, red if negative
- All values wrapped in `<PrivacyValue>` for privacy mode

**Row 2 — Two columns**
- Left (60%): Line chart (shadcn Chart / recharts) — portfolio value vs benchmark normalized to 100. Time range tabs: 1W / 1M / 3M / 1Y.
- Right (40%): Donut chart (shadcn Chart) — allocation by asset type with legend showing type name, value, and %.

**Row 3 — Holdings snapshot table**
- Top holdings sorted by current value descending
- Columns: Symbol, Name, Asset Type, Quantity, Current Value, P&L%
- Row click navigates to `/portfolio/[symbol]`
- Values wrapped in `<PrivacyValue>`

No AI alerts row in Phase 5.

---

## 4. Asset Detail Page (`/portfolio/[symbol]`)

**Data:** TanStack Query fetching `GET /assets/{symbol}/history` and `GET /portfolio/transactions?symbol={symbol}` in parallel.

**Layout (2 sections):**

**Section 1 — Price chart**
- Full-width `lightweight-charts` candlestick chart
- Header: symbol, asset name, latest close price, daily change badge
- Time range tabs: 1W / 1M / 3M / 1Y
- Price values wrapped in `<PrivacyValue>`

**Section 2 — Transactions table**
- TanStack Table, sorted by `executed_at` descending
- Columns: Date, Type (buy/sell/dividend), Quantity, Price, Fee, Platform, Source
- Price/fee values wrapped in `<PrivacyValue>`

No verdict card in Phase 5. The verdict card section is simply absent — it will be added in Phase 6 without any UI rework.

---

## 5. Privacy Mode Toggle

**Storage:** `localStorage` key `zentri_privacy_mode` (boolean).

**State:** Zustand store slice — `privacyMode: boolean`, `togglePrivacyMode()`. Initialized on mount from localStorage. Changes persisted back to localStorage via a store subscription.

**Toggle UI:** Eye / eye-off icon button in the top nav bar (right side, before user menu). Uses shadcn `Button` variant ghost.

**`<PrivacyValue>` component:**
```
<PrivacyValue value="$12,345.67" />
→ renders "••••" when privacyMode is true
→ renders "$12,345.67" when false
```

All monetary values across the app (overview page, asset detail, portfolio list) use this component. Non-monetary values (symbol, asset type, dates) are never masked.

---

## 6. Global ⌘K Command Palette

**Trigger:** `⌘K` (Mac) / `Ctrl+K` (Win/Linux) — `useEffect` keydown listener in root layout. Also triggered by a search icon button in the top nav bar.

**Component:** shadcn `Command` (already in stack) wrapped in shadcn `Dialog`.

**Data source:** Holdings list fetched on mount, cached in Zustand. Watchlist slot is wired but empty in Phase 5 (populated in Phase 7).

**Search behavior:**
- Client-side filter over cached holdings (symbol + name)
- Results grouped: "Holdings" header → matching items
- Selecting a result navigates to `/portfolio/[symbol]` and closes palette

**AI slot (grayed out):**
- When the typed query does not match any holding, show a disabled command item: `Ask AI: "[query]"`
- Styled with muted text color (not interactive)
- shadcn `Tooltip` on hover: "AI analysis available once LLM is configured (Phase 6)"
- Wired to nothing — the action handler is a no-op placeholder

---

## 7. Build Sequence (Option B — Feature-by-Feature)

1. Overview backend endpoints (`/overview/summary`, `/overview/allocation`, `/overview/performance`)
2. Asset history endpoint (`/assets/{symbol}/history`)
3. Market overview page (`/`) — summary bar + charts + holdings table
4. Asset detail page (`/portfolio/[symbol]`) — chart + transactions
5. Privacy mode — Zustand store + `<PrivacyValue>` component + nav toggle + wire all monetary values
6. ⌘K command palette — search + grayed-out AI slot

---

## 8. Backlog Items (deferred from this phase)

- **Share portfolio snapshot as image** — capture summary bar + donut as PNG via `html2canvas` or `dom-to-image`. Add to Kanban backlog.

---

## 9. Phase Roadmap Context

| Phase | Focus |
|---|---|
| 5 (this) | Market Overview + Asset Detail + Privacy Mode + ⌘K palette |
| 6 | AI/LLM Stack — ChromaDB, PDF ingestion, RAG analysis, BUY/SELL/HOLD verdict |
| 7 | Net Worth timeline + Dividend calendar + Watchlist |
| 8 | Settings full UI + Documentation |
