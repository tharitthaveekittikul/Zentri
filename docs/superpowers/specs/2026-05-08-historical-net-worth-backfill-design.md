# Historical Net Worth Backfill Design

**Date:** 2026-05-08
**Status:** Approved

## Problem

The Net Worth chart only shows data from the date the price-fetch worker first ran (Apr 29). Two root causes:

1. The `prices` table only contains prices from when the worker started — no historical data
2. `backfill_snapshots()` uses today's holding quantities for all historical dates — inaccurate if positions were bought/sold over time

## Goal

Show accurate Net Worth history going back to the user's very first transaction by:
1. Fetching full historical prices from yfinance for all priced assets
2. Replaying transactions day-by-day to compute accurate holdings at each historical date

## Architecture

Two independent parts, both triggerable via the pipeline page.

### Part A: Historical Price Backfill Job

**New job:** `job_backfill_historical_prices` in `worker/jobs/price_fetch.py`

**Logic:**
1. Find all unique assets across all users' holdings where `asset_type IN ('us_stock', 'etf', 'crypto', 'gold')`
2. For each asset, find the earliest `executed_at` across all transactions referencing that asset
3. Call `yfinance ticker.history(start=earliest_date, end=today, interval="1d")`
4. Upsert results into existing `prices` table using the existing `_upsert_prices()` function
5. Skip assets where yfinance returns empty history (log warning, continue)

**Asset types excluded:** `thai_fund`, `thai_stock` — no yfinance coverage. When a Thai fund price API is added in future, those prices will flow into the same `prices` table and automatically appear in Net Worth without further changes.

**Idempotent:** safe to run multiple times — upsert handles duplicates.

**Pipeline integration:**
- Function registered in `WorkerSettings.functions` in `worker/main.py`
- `"backfill_historical_prices"` added to `JobType` literal in `app/schemas/pipeline.py`
- Added to `job_fn_map` in `app/api/pipeline.py`
- `{ key: "backfill_historical_prices", label: "Backfill Historical Prices" }` added to `JOBS` in `frontend/components/pipeline/TriggerButtons.tsx`

### Part B: Transaction-Aware `backfill_snapshots()`

**Rewrite of** `backfill_snapshots()` in `app/services/net_worth_snapshot.py`

**Logic:**
1. Load all transactions for the user with `type IN ('buy', 'sell', 'reward')`, sorted by `executed_at` ascending — fetched once into memory
2. If no transactions → return 0
3. Build `rate_map` once (asset_id → USD FX rate) using existing `_build_rate_map()`
4. Determine date range: `start = earliest_tx.executed_at.date()`, `end = yesterday`
5. Batch-fetch all prices per asset between start and end (existing pattern from current backfill)
6. Walk `start` → `end` one day at a time:
   - **Replay transactions up to date D**: filter txs where `executed_at.date() <= D`
     - `buy` / `reward` → `qty_map[asset_id] += transaction.quantity`
     - `sell` → `qty_map[asset_id] -= transaction.quantity`
   - Skip assets where `qty <= 0` (not yet purchased or fully sold out)
   - Look up price for each asset with `qty > 0` using pre-fetched price data
   - Apply FX conversion via `rate_map`
   - `total_value = sum(qty * price * rate)` for assets that have a price on date D
   - `total_cost = sum(qty * holding.avg_cost_price * rate)` — uses today's avg cost as a reasonable approximation for a trend chart
   - If at least one asset is priced → write `NetWorthSnapshot` for date D
   - Skip dates already in `existing_dates` (safe to re-run)

**Cost approximation rationale:** Using today's `avg_cost_price` for historical cost is an accepted simplification. The Net Worth chart's primary purpose is showing value growth over time; the cost line is a reference band. Exact historical cost basis (FIFO/LIFO) is not required for this feature.

## Usage Flow

After deploying:
1. User opens Pipeline page
2. Clicks **▶ Backfill Historical Prices** — fetches full yfinance history for all priced assets
3. Deletes existing net worth snapshots: `DELETE FROM net_worth_snapshots;`
4. Clicks **▶ Net Worth Snapshot** — transaction-aware backfill runs, creates full history
5. Net Worth chart now shows complete timeline from first transaction

> Step 3 (delete) is needed because existing snapshots used today's quantities. Going forward, the daily cron (`job_snapshot_net_worth` at 1 AM UTC) creates each day's snapshot automatically, so no manual re-runs are needed.

## Files to Create / Modify

| File | Change |
|---|---|
| `backend/worker/jobs/price_fetch.py` | Add `job_backfill_historical_prices` function |
| `backend/app/services/net_worth_snapshot.py` | Rewrite `backfill_snapshots()` |
| `backend/app/schemas/pipeline.py` | Add `"backfill_historical_prices"` to `JobType` |
| `backend/app/api/pipeline.py` | Add to `job_fn_map` |
| `backend/worker/main.py` | Register new job in `functions` list |
| `frontend/components/pipeline/TriggerButtons.tsx` | Add button |

## Out of Scope

- FIFO/LIFO realized P&L tracking
- Thai fund / Thai stock historical prices (depends on future API key)
- Cash balance historical tracking in Net Worth snapshots
- Automatic re-backfill trigger when new historical prices are added
