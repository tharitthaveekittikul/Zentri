# Watchlist Scan + Discovery + Page — Design Spec
Date: 2026-05-06

## Summary

Two Kanban items delivered together:
- **feat - watchlist scan ARQ job for AI discovery**: On-demand AI analysis of existing watchlist items + AI-generated ticker discovery
- **feat - watchlist page and promote to portfolio flow**: Frontend page to manage the watchlist and act on AI results

"Promote to portfolio" was clarified during brainstorming: it means using the AI-suggested buy price as a price alert target — not creating a holding.

---

## Feature Keys

Two new LLM feature keys registered in `FEATURE_KEYS`:
- `watchlist_scan` — analyzes existing watchlist items (verdict + suggested buy price)
- `watchlist_discovery` — suggests new tickers to add to the watchlist based on portfolio context

Both appear in Settings > AI as configurable LLM assignments. All LLM calls are audited to `llm_call_logs`.

---

## Data Model

### New: `watchlist_suggestions` table

```
id             UUID PK
user_id        UUID FK users
symbol         VARCHAR(20)       — raw ticker string
asset_id       UUID FK assets    — nullable (may not exist in DB yet)
reasoning      TEXT
suggested_price NUMERIC(20,8)    — nullable
verdict        VARCHAR(10)       — BUY / SELL / HOLD
status         VARCHAR(20)       — pending | accepted | dismissed
created_at     TIMESTAMPTZ
```

One Alembic migration: `017_watchlist_suggestion.py`.

### Modified: `WatchlistItem` (no schema change)

The existing `target_price` + `alert_enabled` fields serve as the "apply AI price as alert" target. No new columns needed.

### Modified: `AIAnalysis` (no schema change)

Existing table reused to store per-item scan verdicts. `asset_id` is sufficient — no holding required. The `job_id` references the pipeline log entry.

### Modified: `FEATURE_KEYS` tuple

Add `"watchlist_scan"` and `"watchlist_discovery"` to `app/models/feature_llm_config.py`.

---

## Backend

### New: `get_feature_llm_provider(db, feature_key, user_id)`

Added to `app/services/llm_service.py`. Logic:
1. Look up `FeatureLLMConfig` for `(user_id, feature_key)`
2. If found → resolve `ProviderConfig` → return appropriate LLMProvider with that model
3. Fallback → `get_llm_provider(db)` (active LLMSettings)

### New ARQ Jobs

**`worker/jobs/watchlist_scan.py`**
- `job_scan_watchlist_item(ctx, symbol, user_id)` — scans one watchlist item:
  1. Fetch asset + recent prices (90 days) + RAG context
  2. Call LLM with watchlist-specific prompt (no holdings context — framed as "should I buy?")
  3. Parse JSON response: `{verdict, suggested_price, reasoning}`
  4. Save to `ai_analyses`
  5. Write `LLMCallLog` with `feature_key="watchlist_scan"`, `user_id`
  6. Update pipeline log

- `job_scan_watchlist_batch(ctx)` — iterates all `WatchlistItem` rows, queues `job_scan_watchlist_item` per symbol

**`worker/jobs/watchlist_discover.py`**
- `job_discover_watchlist(ctx)` — generates new ticker suggestions:
  1. Fetch user's holdings (symbols + allocation)
  2. Fetch user's existing watchlist (to exclude)
  3. Call LLM with discovery prompt: "Given this portfolio, suggest 3-5 tickers worth watching"
  4. Parse JSON array: `[{symbol, reasoning, suggested_price, verdict}, ...]`
  5. For each suggestion: look up asset in DB (set `asset_id` if found, null otherwise)
  6. Save to `watchlist_suggestions` (status=pending), skip if symbol already in watchlist or already has a pending suggestion
  7. Write `LLMCallLog` with `feature_key="watchlist_discovery"`, `user_id`

### New API Endpoints (in `app/api/watchlist.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/watchlist/{item_id}/scan` | Trigger single-item scan job |
| `POST` | `/watchlist/scan-all` | Trigger batch scan job |
| `POST` | `/watchlist/discover` | Trigger discovery job |
| `GET`  | `/watchlist/suggestions` | List pending suggestions |
| `POST` | `/watchlist/suggestions/{id}/accept` | Accept → create WatchlistItem + mark accepted |
| `POST` | `/watchlist/suggestions/{id}/dismiss` | Mark dismissed |

**Accept flow detail:**
1. If `asset_id` is set → directly create `WatchlistItem`
2. If `asset_id` is null → call `asset_service.search_assets(db, user_id, symbol)` to find/create asset, then create `WatchlistItem`
3. Set `target_price` from `suggested_price` if present
4. Mark suggestion status = "accepted"

### Modified: `WatchlistItemOut` schema

Add fields:
- `last_verdict: str | None` — from latest `AIAnalysis` for this asset
- `ai_suggested_price: Decimal | None` — `target_price` from latest `AIAnalysis`
- `last_scanned_at: datetime | None` — `created_at` of latest `AIAnalysis`

These are resolved in `_item_to_out()` and the list endpoint via a subquery on `ai_analyses`.

### Modified: `worker/main.py`

Add to `functions`:
- `job_scan_watchlist_item`
- `job_scan_watchlist_batch`
- `job_discover_watchlist`

No new cron jobs (on-demand only).

---

## Frontend

### New: `lib/services/watchlist.ts`

API client functions:
- `listWatchlist()` → `GET /api/v1/watchlist`
- `addToWatchlist(body)` → `POST /api/v1/watchlist`
- `updateWatchlistItem(id, patch)` → `PATCH /api/v1/watchlist/{id}`
- `deleteWatchlistItem(id)` → `DELETE /api/v1/watchlist/{id}`
- `rearmWatchlistItem(id)` → `POST /api/v1/watchlist/{id}/rearm`
- `scanItem(id)` → `POST /api/v1/watchlist/{id}/scan`
- `scanAll()` → `POST /api/v1/watchlist/scan-all`
- `discover()` → `POST /api/v1/watchlist/discover`
- `listSuggestions()` → `GET /api/v1/watchlist/suggestions`
- `acceptSuggestion(id)` → `POST /api/v1/watchlist/suggestions/{id}/accept`
- `dismissSuggestion(id)` → `POST /api/v1/watchlist/suggestions/{id}/dismiss`

### New: `app/(auth)/watchlist/page.tsx`

Two sections:

**My Watchlist** — table with columns:
- Ticker (symbol + name)
- Current Price
- Target Price (editable inline or via edit dialog)
- % to Target
- AI Verdict badge (BUY/SELL/HOLD or —)
- AI Suggested Price
- Last Scanned (relative time)
- Actions: [Scan] [Apply Price] [🔔/🔕] [🗑]

**AI Suggestions** — card list (shown only when suggestions exist):
- Symbol + reasoning + suggested price + verdict badge
- [Add to Watchlist] [Dismiss] buttons

**Header actions:**
- [+ Add] — opens dialog: asset search (calls `GET /api/v1/assets/search?q=...`), optional target price
- [Scan All] — triggers batch scan, shows spinner
- [Discover New] — triggers discovery, refreshes suggestions after delay

**Interaction details:**
- [Scan] per row: sets row into loading state, triggers `scanItem(id)`, re-fetches row on completion
- [Apply Price]: calls `updateWatchlistItem(id, {target_price: ai_suggested_price, alert_enabled: true})` — only visible when `ai_suggested_price` is set
- [🔔/🔕]: calls `updateWatchlistItem(id, {alert_enabled: !current})` — shows bell filled/outline
- Alert already triggered (alerted_at set): shows [Rearm] button instead

### Modified: `lib/services/feature-llm-config.ts`

Add to `FEATURE_LABELS`:
```ts
watchlist_scan: "Watchlist Scanner",
watchlist_discovery: "Watchlist Discovery",
```

### Modified: `components/layout/TopNav.tsx`

Add Watchlist nav link pointing to `/watchlist`.

---

## LLM Prompts

### Watchlist Scan (per item)
System: "You are a financial analyst. Given an asset's price history and research context, assess whether it is a good buy opportunity. Respond ONLY with valid JSON: {\"verdict\": \"BUY\"|\"SELL\"|\"HOLD\", \"suggested_price\": <number or null>, \"reasoning\": \"<2-3 sentences>\"}"

User prompt includes: symbol, recent 10-day price history, RAG context. No holdings (framed as "I don't own this yet — should I buy?").

### Watchlist Discovery
System: "You are a portfolio advisor. Given a user's current holdings, suggest assets they should consider watching. Respond ONLY with valid JSON array: [{\"symbol\": \"...\", \"verdict\": \"BUY\", \"suggested_price\": <number or null>, \"reasoning\": \"...\"}]. Suggest 3-5 assets not already in the portfolio."

User prompt includes: list of held symbols + allocation %, existing watchlist symbols (to exclude), brief user profile (age, planning horizon if available).

---

## Error Handling

- Scan job failure per item: logs error, marks pipeline log as failed, continues to next item (batch doesn't abort)
- Discovery job: if LLM returns malformed JSON → retry once with format reminder (same pattern as `run_analysis`)
- Asset not found during accept: call asset search, if still not found return 404 to frontend
- Duplicate suggestion: skip silently if symbol already in watchlist or has a pending suggestion

---

## Out of Scope

- Cron scheduling for scan/discovery (on-demand only per user decision)
- Removing item from watchlist on "promote" (user keeps watching after applying price)
- Creating holdings from watchlist (separate future feature)
