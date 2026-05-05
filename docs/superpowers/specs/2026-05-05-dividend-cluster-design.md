# Dividend Cluster Design

**Date:** 2026-05-05
**Status:** Approved
**Scope:** Dividend fetch worker + dividend calendar page + transactions management page

---

## Overview

Three features shipped as one cluster:
1. **Dividend fetch worker** — ARQ job that fetches dividend events from yfinance (weekly + on-demand)
2. **Dividend calendar endpoint + page** — calendar grid + upcoming list with projected income and "mark as received" flow
3. **Transactions management page** — table with edit and delete for all transaction types

---

## Architecture

```
yfinance (.dividends + .calendar)
         ↓
worker/jobs/dividend_fetch.py     ← new ARQ job (weekly cron + on-demand)
         ↓
app/services/dividend_feed.py     ← new service (fetch + upsert events)
         ↓
dividend_events table             ← new table (migration 013)
         ↓
app/api/dividends.py              ← new router (calendar, list, refresh, mark-received)
app/api/portfolio.py              ← +PATCH/DELETE /transactions/{id}
         ↓
frontend/app/(auth)/dividends/page.tsx     ← calendar grid + event list + confirm flow
frontend/app/(auth)/transactions/page.tsx  ← full transaction table with edit + delete
```

**Fetch strategy:**
- `us_stock` and `etf` assets: fetch via yfinance
- `thai_stock` and `th_fund`: skip for now, reserved for future Thai API (`source="thai_api"`)
- `crypto`: skip entirely (no dividends)
- `gold`, `cash`: skip

---

## Data Model

### New table: `dividend_events` (migration 013)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | gen_random_uuid() |
| `asset_id` | UUID FK → assets | |
| `ex_date` | Date | Must own shares before this date |
| `pay_date` | Date nullable | Actual payment date |
| `record_date` | Date nullable | |
| `amount_per_share` | Numeric(20,8) | In asset's native currency |
| `currency` | String(10) | e.g. USD |
| `frequency` | String(20) nullable | quarterly, annual, monthly, special |
| `status` | Enum | upcoming / payable / paid |
| `source` | String(20) | yfinance, thai_api, manual |
| `confirmed_transaction_id` | UUID FK → transactions nullable | Set on mark-as-received |
| `created_at` | DateTime(tz) | |
| `updated_at` | DateTime(tz) | |

- Unique constraint: `(asset_id, ex_date)`
- Index: `(asset_id, ex_date)`
- Status enum name: `dividend_event_status_enum`
- **Single-user note:** `dividend_events` is intentionally asset-scoped (no `user_id`) — shared market data. `confirmed_transaction_id` effectively ties confirmation to the one user. When multi-user is implemented, this table will need a `user_id` column or a separate `user_dividend_confirmations` join table.

**Status transitions:**
```
upcoming  → payable  (worker updates when ex_date passes)
payable   → paid     (user clicks "mark as received")
```

### Existing `transactions` table

No schema changes. `type=dividend` already exists in `transaction_type_enum`. The `confirmed_transaction_id` FK on `dividend_events` points to `transactions.id`.

---

## Worker

### `worker/jobs/dividend_fetch.py`

```python
async def job_fetch_dividends(ctx: dict) -> dict:
    """ARQ job: fetch dividend events for all user holdings via yfinance."""
    # create_log → dividend_feed.fetch_all_dividends(db) → finish_log
```

### `app/services/dividend_feed.py`

- Queries all unique `us_stock` / `etf` assets across all users
- For each asset: calls `yfinance.Ticker(symbol).dividends` (history) and `.calendar` (upcoming)
- Upserts into `dividend_events` using `(asset_id, ex_date)` as conflict key
- Updates `status` field: `ex_date > today → upcoming`, `ex_date <= today AND confirmed_transaction_id IS NULL → payable`
- Logs count of inserted/updated rows

### Cron schedule

```python
cron(job_fetch_dividends, weekday=0, hour=2, minute=0)  # Every Monday 02:00
```

Registered in `worker/main.py` functions list and cron_jobs.

---

## API Endpoints

### New router: `app/api/dividends.py` (prefix `/dividends`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/dividends/calendar?months=3` | Events grouped by month (default: next 3 months); `months` param 1–12 |
| `GET` | `/dividends/upcoming` | Flat list of payable + upcoming events sorted by ex_date |
| `POST` | `/dividends/refresh` | Enqueue `job_fetch_dividends` on-demand via ARQ |
| `POST` | `/dividends/{event_id}/confirm` | Mark as received → create transaction + set confirmed_transaction_id + status=paid |

**Confirm request body:**
```json
{ "quantity": 10.0, "executed_at": "2026-05-15" }
```
`quantity` defaults to current holding quantity but can be overridden (for users who sold between ex-date and pay-date). `executed_at` defaults to `pay_date`.

**Calendar response shape:**
```json
{
  "months": [
    {
      "year": 2026,
      "month": 5,
      "total_projected_usd": 12.50,
      "events": [
        {
          "id": "uuid",
          "symbol": "AAPL",
          "asset_id": "uuid",
          "ex_date": "2026-05-09",
          "pay_date": "2026-05-15",
          "amount_per_share": 0.25,
          "currency": "USD",
          "frequency": "quarterly",
          "status": "payable",
          "quantity_held": 10.0,
          "projected_total_usd": 2.50,
          "projected_total_secondary": 87.50
        }
      ]
    }
  ]
}
```

Projected income = `quantity_held × amount_per_share`, converted to secondary currency using exchange rate cache (same pattern as portfolio summary).

### Additions to `app/api/portfolio.py`

| Method | Path | Description |
|---|---|---|
| `PATCH` | `/portfolio/transactions/{id}` | Edit type, quantity, price, fee, executed_at, platform |
| `DELETE` | `/portfolio/transactions/{id}` | Delete a transaction (404 if not found or not owned by user) |

Pattern mirrors existing `PATCH /holdings/{id}` and `DELETE /holdings/{id}`.

---

## Frontend

### `frontend/app/(auth)/dividends/page.tsx`

Layout (top to bottom):
1. **Header row** — title "Dividend Calendar" + "Refresh" button → calls `POST /dividends/refresh`, shows spinner
2. **Month grid** — calendar grid for current month. Days with events show colored dot + ticker. Clicking a day opens a popover with: ex_date, pay_date, amount/share, projected total (dual-currency), status badge, "Mark as Received" button (payable only)
3. **Upcoming list** — DataTable grouped by month with columns: Ticker | Ex-Date | Pay-Date | Per Share | Projected Total (dual-currency) | Status badge | Action
4. **Mark as Received dialog** — confirms transaction details before creation. Shows: asset symbol, quantity held, amount/share, total in dual-currency. On confirm → `POST /dividends/{event_id}/confirm`

### `frontend/app/(auth)/transactions/page.tsx`

Layout:
1. **Header** — title "Transactions" + filters: asset search, type select, date range picker
2. **DataTable** — columns: Date | Asset | Type badge | Quantity | Price | Fee | Platform | Actions (edit + delete)
3. **Edit sheet/dialog** — slides in on edit click. Editable: type, quantity, price, fee, executed_at, platform. Calls `PATCH /portfolio/transactions/{id}`
4. **Delete confirmation dialog** — "Delete this transaction?" with cancel/confirm. Calls `DELETE /portfolio/transactions/{id}`

### `components/layout/Sidebar.tsx`

Add two new nav links:
- "Dividends" → `/dividends`
- "Transactions" → `/transactions`

---

## New Files Summary

| File | Type |
|---|---|
| `backend/alembic/versions/013_dividend_events.py` | Migration |
| `backend/app/models/dividend_event.py` | SQLAlchemy model |
| `backend/app/schemas/dividend.py` | Pydantic schemas |
| `backend/app/services/dividend_feed.py` | Service |
| `backend/app/api/dividends.py` | FastAPI router |
| `backend/worker/jobs/dividend_fetch.py` | ARQ job |
| `frontend/app/(auth)/dividends/page.tsx` | Page |
| `frontend/app/(auth)/transactions/page.tsx` | Page |

### Modified Files

| File | Change |
|---|---|
| `backend/app/models/__init__.py` | Import DividendEvent |
| `backend/app/api/portfolio.py` | Add PATCH + DELETE /transactions/{id} |
| `backend/app/main.py` | Register dividends router |
| `backend/worker/main.py` | Register job + cron |
| `frontend/components/layout/Sidebar.tsx` | Add nav links |
