# Net Worth Daily Snapshot Worker + Timeline Page

**Date:** 2026-05-05
**Status:** Approved
**Kanban tasks:** feat - net worth daily snapshot worker, feat - net worth timeline endpoint and page

---

## Summary

Materialize daily net worth snapshots into a dedicated table so the overview page can display an absolute USD net worth timeline chart without expensive on-the-fly recalculation.

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Storage currency | USD | Global open-source app; all current price feeds (yfinance, CoinGecko, gold) return USD natively |
| Storage approach | New `net_worth_snapshots` table | Consistent with existing patterns; instant reads; no TimescaleDB complexity needed for daily data |
| Include cash balances | No | Investments only (stocks, funds, crypto, gold) |
| FX conversion | Not needed now | Thai stocks/funds (only THB assets) are still in Backlog; revisit when added |
| Backfill | Yes, on first run | Users see full history immediately; uses current holdings quantities (same approximation as existing `get_performance()`) |
| Timeline page placement | Section on existing overview page | Net worth is the hero metric of the dashboard; standalone page would be thin |

---

## Architecture

```
Daily at 01:00 UTC
      │
      ▼
ARQ cron: job_snapshot_net_worth
      │
      ▼
NetWorthSnapshotService
  1. Load all holdings for user
  2. For each holding:
     - Get latest price on or before snapshot_date from prices table
     - If no price found → skip that holding (partial snapshots allowed)
  3. Sum → total_value_usd = Σ(quantity × price.close)
           total_cost_usd  = Σ(quantity × avg_cost_price)
  4. INSERT INTO net_worth_snapshots ON CONFLICT DO NOTHING

On first run (0 existing snapshots for user):
  → backfill: repeat for every date from earliest price to yesterday

API: GET /overview/net-worth?range=1M|3M|6M|1Y|ALL
  → SELECT from net_worth_snapshots WHERE user_id = ? AND date >= ?
  → return [{date, value_usd, cost_usd}]

Frontend (Overview page):
  → New NetWorthChart component inserted above allocation section
  → lightweight-charts AreaSeries, absolute USD values
  → Range selector: 1M / 3M / 6M / 1Y / ALL
  → Shows value line + cost basis line
  → Privacy mode: mask Y-axis values with ***
```

---

## Database

### New table: `net_worth_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | gen_random_uuid() |
| `user_id` | UUID FK → users.id | indexed |
| `snapshot_date` | DATE | not null |
| `total_value_usd` | NUMERIC(20,8) | not null |
| `total_cost_usd` | NUMERIC(20,8) | not null |
| `created_at` | TIMESTAMPTZ | server default now() |

**Constraints:**
- `UNIQUE(user_id, snapshot_date)` — idempotency guarantee
- `INDEX(user_id, snapshot_date)` — covers all range queries

### New files
- `backend/app/models/net_worth_snapshot.py`
- `backend/alembic/versions/010_net_worth_snapshot.py`

---

## Backend Service

**File:** `backend/app/services/net_worth_snapshot.py`

### `take_snapshot(db, user_id, snapshot_date) -> NetWorthSnapshot | None`
1. Load all holdings for user
2. For each holding: query latest price on or before `snapshot_date`
3. Skip holdings with no price (don't fail the whole snapshot)
4. Sum `total_value_usd` and `total_cost_usd`
5. `INSERT ... ON CONFLICT (user_id, snapshot_date) DO NOTHING`
6. Return `None` if no holdings had prices (skip empty days)

### `backfill_snapshots(db, user_id) -> int`
1. Find earliest price date across all user's holdings
2. Get set of dates already snapshotted → skip them
3. For each missing date from earliest → yesterday: call `take_snapshot()`
4. Return count of snapshots inserted

---

## Backend Worker Job

**File:** `backend/worker/jobs/net_worth_snapshot.py`

### `job_snapshot_net_worth(ctx) -> dict`
1. Load all users from DB
2. For each user:
   - Check if any snapshot exists; if 0 → run `backfill_snapshots()` first
   - Run `take_snapshot()` for yesterday
3. Log via `create_log` / `finish_log` (pipeline pattern)
4. Return `{"users": N, "snapshots_written": M}`

**Registration in `worker/main.py`:**
- Add to `functions` list
- Add to `cron_jobs`: `cron(job_snapshot_net_worth, hour=1, minute=0)`
- Runs daily at 01:00 UTC (after price fetch jobs)

---

## Backend API

**Modified file:** `backend/app/api/overview.py`

```
GET /overview/net-worth?range=1M
```

**Supported ranges:**

| Range | Lookback |
|---|---|
| `1M` | 30 days (default) |
| `3M` | 90 days |
| `6M` | 180 days |
| `1Y` | 365 days |
| `ALL` | no date filter |

**Response schema** (added to `backend/app/schemas/overview.py`):
```python
class NetWorthPoint(BaseModel):
    date: date
    value_usd: Decimal
    cost_usd: Decimal
```

**New service function** (added to `backend/app/services/overview.py`):
```python
async def get_net_worth_timeline(db, user_id, range_) -> list[dict]
# SELECT snapshot_date, total_value_usd, total_cost_usd
# FROM net_worth_snapshots
# WHERE user_id = ? AND snapshot_date >= range_start
# ORDER BY snapshot_date ASC
```

---

## Frontend

### New component: `frontend/components/net-worth-chart.tsx`

**Structure:**
- Range selector tabs: `1M | 3M | 6M | 1Y | ALL`
- Summary row: Current value (USD) · Total cost (USD) · Unrealized PnL (+ %)
- `lightweight-charts` AreaSeries:
  - Primary line: `total_value_usd`
  - Secondary muted/dashed line: `cost_usd` (cost basis)
- Privacy mode: mask Y-axis values with `***`

**Data fetching:** `GET /overview/net-worth?range=<selected>` on mount and on range change.

### Modified file: `frontend/app/(auth)/page.tsx`

Insert `<NetWorthChart />` between the summary cards and the allocation section:

```
Overview page
├── Summary cards          ← unchanged
├── [NEW] Net Worth Chart  ← hero position
├── Allocation pie         ← unchanged
└── Performance chart      ← unchanged
```

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `backend/app/models/net_worth_snapshot.py` |
| CREATE | `backend/alembic/versions/010_net_worth_snapshot.py` |
| CREATE | `backend/app/services/net_worth_snapshot.py` |
| CREATE | `backend/worker/jobs/net_worth_snapshot.py` |
| MODIFY | `backend/worker/main.py` |
| MODIFY | `backend/app/schemas/overview.py` |
| MODIFY | `backend/app/services/overview.py` |
| MODIFY | `backend/app/api/overview.py` |
| CREATE | `frontend/components/net-worth-chart.tsx` |
| MODIFY | `frontend/app/(auth)/page.tsx` |
