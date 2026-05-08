# Historical Net Worth Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show accurate Net Worth history from the user's first transaction by replaying transactions day-by-day and fetching full yfinance price history for all priced assets.

**Architecture:** A new service function `fetch_historical_prices()` fetches yfinance history back to each asset's earliest transaction and upserts into the existing `prices` table. `backfill_snapshots()` is rewritten to replay `buy`/`sell`/`reward` transactions per-date instead of using today's static holdings. A new `job_backfill_historical_prices` ARQ job wraps the service function and is exposed in the pipeline UI.

**Tech Stack:** Python, SQLAlchemy async, ARQ, yfinance, FastAPI, Next.js/React

---

## Files Modified / Created

| File                                                | Change                                                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `backend/alembic/versions/011_backfill_job_type.py` | **Create** — migration to add `backfill_historical_prices` to `job_type_enum`                         |
| `backend/app/models/pipeline_log.py`                | **Modify** — add `"backfill_historical_prices"` to `JOB_TYPES`                                        |
| `backend/app/schemas/pipeline.py`                   | **Modify** — add `"backfill_historical_prices"` to `JobType` literal                                  |
| `backend/app/api/pipeline.py`                       | **Modify** — add to `job_fn_map`                                                                      |
| `backend/app/services/net_worth_snapshot.py`        | **Modify** — refactor `_build_rate_map`, extract `_replay_transactions`, rewrite `backfill_snapshots` |
| `backend/app/services/price_feed.py`                | **Modify** — add `fetch_historical_prices()`                                                          |
| `backend/worker/jobs/price_fetch.py`                | **Modify** — add `job_backfill_historical_prices`                                                     |
| `backend/worker/main.py`                            | **Modify** — register new job in `functions`                                                          |
| `backend/tests/test_net_worth_snapshot.py`          | **Modify** — fix `compute_snapshot` tests (rate_map param), add `_replay_transactions` tests          |
| `frontend/components/pipeline/TriggerButtons.tsx`   | **Modify** — add button                                                                               |

---

## Task 1: Alembic Migration + Pipeline Type Registration

**Files:**

- Create: `backend/alembic/versions/011_backfill_job_type.py`
- Modify: `backend/app/models/pipeline_log.py`
- Modify: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/api/pipeline.py`

- [ ] **Step 1: Create migration**

Create `backend/alembic/versions/011_backfill_job_type.py`:

```python
"""add backfill_historical_prices job type

Revision ID: 011
Revises: 010
Create Date: 2026-05-08
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_type_enum ADD VALUE IF NOT EXISTS 'backfill_historical_prices'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing ENUM values
```

- [ ] **Step 2: Run migration**

```bash
docker exec zentri-backend-1 alembic upgrade head
```

Expected output: `Running upgrade 010 -> 011, add backfill_historical_prices job type`

- [ ] **Step 3: Add to `JOB_TYPES` in pipeline_log.py**

In `backend/app/models/pipeline_log.py`, change:

```python
JOB_TYPES = (
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth",
    "ingest_document", "run_analysis",
    "watchlist_discovery", "watchlist_scan",
    "dividend_fetch", "ipo_fetch", "dividend_alert",
)
```

to:

```python
JOB_TYPES = (
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth", "backfill_historical_prices",
    "ingest_document", "run_analysis",
    "watchlist_discovery", "watchlist_scan",
    "dividend_fetch", "ipo_fetch", "dividend_alert",
)
```

- [ ] **Step 4: Add to `JobType` literal in schemas/pipeline.py**

In `backend/app/schemas/pipeline.py`, change:

```python
JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth",
    ...
]
```

to:

```python
JobType = Literal[
    "price_fetch_us", "price_fetch_crypto",
    "price_fetch_gold", "price_fetch_benchmark",
    "price_fetch_thai_stock", "price_fetch_th_fund",
    "snapshot_net_worth", "backfill_historical_prices",
    ...
]
```

- [ ] **Step 5: Add to `job_fn_map` in api/pipeline.py**

In `backend/app/api/pipeline.py`, in the `trigger_job` function, add to `job_fn_map`:

```python
job_fn_map = {
    "price_fetch_us": "job_fetch_prices_us",
    "price_fetch_crypto": "job_fetch_prices_crypto",
    "price_fetch_gold": "job_fetch_price_gold",
    "price_fetch_benchmark": "job_fetch_benchmark_prices",
    "price_fetch_thai_stock": "job_fetch_prices_thai_stock",
    "price_fetch_th_fund": "job_fetch_prices_th_fund",
    "snapshot_net_worth": "job_snapshot_net_worth",
    "backfill_historical_prices": "job_backfill_historical_prices",  # add this
}
```

---

## Task 2: Refactor `_build_rate_map` + Fix Existing Tests

`_build_rate_map` currently accepts a list of Holding objects. Refactor to accept a list of `uuid.UUID` directly — cleaner for the transaction-aware backfill which doesn't have Holding objects for all assets.

**Files:**

- Modify: `backend/app/services/net_worth_snapshot.py`
- Modify: `backend/tests/test_net_worth_snapshot.py`

- [ ] **Step 1: Update tests to match current `compute_snapshot` signature (rate_map param was already added)**

Replace all of `backend/tests/test_net_worth_snapshot.py` with:

```python
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.services.net_worth_snapshot import compute_snapshot, _replay_transactions


def _holding(asset_id_hex: str, quantity: str, avg_cost: str):
    h = MagicMock()
    h.asset_id = uuid.UUID(asset_id_hex)
    h.quantity = Decimal(quantity)
    h.avg_cost_price = Decimal(avg_cost)
    return h


def _tx(asset_id: uuid.UUID, type_: str, qty: str, day: int):
    tx = MagicMock()
    tx.asset_id = asset_id
    tx.type = type_
    tx.quantity = Decimal(qty)
    tx.executed_at = datetime(2026, 4, day, 12, 0, 0, tzinfo=timezone.utc)
    return tx


AID1 = "aaaaaaaa-0000-0000-0000-000000000001"
AID2 = "aaaaaaaa-0000-0000-0000-000000000002"
UID1 = uuid.UUID(AID1)
UID2 = uuid.UUID(AID2)


# --- compute_snapshot tests ---

def test_compute_snapshot_sums_value_and_cost():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {UID1: Decimal("120"), UID2: Decimal("60")}
    rate_map = {UID1: Decimal("1"), UID2: Decimal("1")}
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("1320")
    assert result["total_cost_usd"] == Decimal("1100")


def test_compute_snapshot_applies_fx_rate():
    holdings = [_holding(AID1, "10", "100")]
    price_map = {UID1: Decimal("100")}
    rate_map = {UID1: Decimal("0.03")}  # THB→USD rate
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("30")   # 10 * 100 * 0.03
    assert result["total_cost_usd"] == Decimal("30")    # 10 * 100 * 0.03


def test_compute_snapshot_skips_holdings_without_price():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {UID1: Decimal("120")}
    rate_map = {UID1: Decimal("1"), UID2: Decimal("1")}
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("1200")
    assert result["total_cost_usd"] == Decimal("1000")


def test_compute_snapshot_returns_none_when_no_prices():
    holdings = [_holding(AID1, "10", "100")]
    rate_map = {UID1: Decimal("1")}
    result = compute_snapshot(holdings, {}, rate_map)
    assert result is None


def test_compute_snapshot_returns_none_for_empty_holdings():
    result = compute_snapshot([], {}, {})
    assert result is None


# --- _replay_transactions tests ---

def test_replay_buy_only():
    txs = [_tx(UID1, "buy", "10", 1)]
    result = _replay_transactions(txs, date(2026, 4, 5))
    assert result[UID1] == Decimal("10")


def test_replay_buy_then_sell():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "sell", "3", 5)]
    assert _replay_transactions(txs, date(2026, 4, 3))[UID1] == Decimal("10")
    assert _replay_transactions(txs, date(2026, 4, 5))[UID1] == Decimal("7")


def test_replay_reward_adds_quantity():
    txs = [_tx(UID1, "buy", "5", 1), _tx(UID1, "reward", "2", 3)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("7")


def test_replay_future_txs_excluded():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "buy", "5", 20)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("10")


def test_replay_fully_sold_returns_zero():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "sell", "10", 5)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("0")


def test_replay_multiple_assets():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID2, "buy", "5", 2)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("10")
    assert result[UID2] == Decimal("5")
```

- [ ] **Step 2: Run tests — expect failures on `_replay_transactions` (not yet defined)**

```bash
docker exec zentri-backend-1 python -m pytest tests/test_net_worth_snapshot.py -v 2>&1 | tail -20
```

Expected: `ImportError` or `FAILED` on `_replay_transactions` tests.

- [ ] **Step 3: Refactor `_build_rate_map` and add `_replay_transactions` in net_worth_snapshot.py**

In `backend/app/services/net_worth_snapshot.py`, replace `_build_rate_map`:

```python
async def _build_rate_map(db: AsyncSession, asset_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    rate_map: dict[uuid.UUID, Decimal] = {}
    for asset_id in asset_ids:
        asset = (await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )).scalar_one_or_none()
        if asset:
            rate = await fx_service.get_rate(db, asset.currency, "USD")
            rate_map[asset_id] = rate if rate else Decimal("1")
        else:
            rate_map[asset_id] = Decimal("1")
    return rate_map
```

Update callers of `_build_rate_map` in the same file:

In `take_snapshot()`, change:

```python
rate_map = await _build_rate_map(db, holdings)
```

to:

```python
rate_map = await _build_rate_map(db, [h.asset_id for h in holdings])
```

In `backfill_snapshots()`, change:

```python
rate_map = await _build_rate_map(db, holdings)
```

to:

```python
rate_map = await _build_rate_map(db, [h.asset_id for h in holdings])
```

Then add `_replay_transactions` as a pure function (add after `_build_rate_map`):

```python
def _replay_transactions(transactions: list, up_to_date: date) -> dict[uuid.UUID, Decimal]:
    """Compute quantity held per asset as of up_to_date by replaying transactions in order."""
    qty_map: dict[uuid.UUID, Decimal] = {}
    for tx in transactions:
        if tx.executed_at.date() > up_to_date:
            break
        if tx.type in ("buy", "reward"):
            qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) + tx.quantity
        elif tx.type == "sell":
            qty_map[tx.asset_id] = qty_map.get(tx.asset_id, Decimal("0")) - tx.quantity
    return qty_map
```

- [ ] **Step 4: Run tests — all should pass**

```bash
docker exec zentri-backend-1 python -m pytest tests/test_net_worth_snapshot.py -v 2>&1 | tail -20
```

Expected: All tests pass.

---

## Task 3: Rewrite `backfill_snapshots()` with Transaction Replay

**Files:**

- Modify: `backend/app/services/net_worth_snapshot.py`

- [ ] **Step 1: Add `Transaction` import at top of net_worth_snapshot.py**

Add to imports:

```python
from app.models.transaction import Transaction
```

- [ ] **Step 2: Replace `backfill_snapshots()` entirely**

Replace the full `backfill_snapshots` function with:

```python
async def backfill_snapshots(db: AsyncSession, user_id: uuid.UUID) -> int:
    # Load all buy/sell/reward transactions sorted by date — fetched once into memory
    txs_result = await db.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.type.in_(["buy", "sell", "reward"]),
        )
        .order_by(Transaction.executed_at.asc())
    )
    transactions = list(txs_result.scalars().all())

    if not transactions:
        return 0

    asset_ids = list({t.asset_id for t in transactions})

    # FX rates (today's rates — acceptable approximation for trend chart)
    rate_map = await _build_rate_map(db, asset_ids)

    # avg_cost_price from current holdings (approximation for cost line)
    holdings_result = await db.execute(
        select(Holding).where(Holding.user_id == user_id)
    )
    avg_cost_map: dict[uuid.UUID, Decimal] = {
        h.asset_id: h.avg_cost_price
        for h in holdings_result.scalars().all()
    }

    earliest_date = transactions[0].executed_at.date()
    yesterday = date.today() - timedelta(days=1)

    existing_result = await db.execute(
        select(NetWorthSnapshot.snapshot_date).where(NetWorthSnapshot.user_id == user_id)
    )
    existing_dates = {row[0] for row in existing_result.all()}

    # Batch-fetch all historical prices for all transaction assets
    start_dt = datetime(earliest_date.year, earliest_date.month, earliest_date.day, 0, 0, 0, tzinfo=timezone.utc)
    cutoff_dt = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=timezone.utc)

    asset_prices: dict[uuid.UUID, list[tuple[datetime, Decimal]]] = {}
    for asset_id in asset_ids:
        prices_result = await db.execute(
            select(Price.timestamp, Price.close)
            .where(
                Price.asset_id == asset_id,
                Price.timestamp >= start_dt,
                Price.timestamp <= cutoff_dt,
            )
            .order_by(Price.timestamp.asc())
        )
        asset_prices[asset_id] = [(row[0], row[1]) for row in prices_result.all()]

    def get_price_for_date(asset_id: uuid.UUID, target_date: date) -> Decimal | None:
        prices = asset_prices.get(asset_id, [])
        cutoff = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)
        result = None
        for ts, close in prices:
            if ts <= cutoff:
                result = close
            else:
                break
        return result

    count = 0
    current = earliest_date
    while current <= yesterday:
        if current not in existing_dates:
            qty_map = _replay_transactions(transactions, current)

            total_value = Decimal("0")
            total_cost = Decimal("0")
            any_priced = False

            for asset_id, qty in qty_map.items():
                if qty <= 0:
                    continue
                price = get_price_for_date(asset_id, current)
                if price is None:
                    continue
                rate = rate_map.get(asset_id, Decimal("1"))
                avg_cost = avg_cost_map.get(asset_id, Decimal("0"))
                total_value += qty * price * rate
                total_cost += qty * avg_cost * rate
                any_priced = True

            if any_priced:
                snapshot = NetWorthSnapshot(
                    user_id=user_id,
                    snapshot_date=current,
                    total_value_usd=total_value,
                    total_cost_usd=total_cost,
                )
                db.add(snapshot)
                try:
                    await db.commit()
                    await db.refresh(snapshot)
                    count += 1
                except IntegrityError:
                    await db.rollback()

        current += timedelta(days=1)

    logger.info("backfill complete user=%s snapshots=%d", user_id, count)
    return count
```

- [ ] **Step 3: Run all net worth tests to confirm nothing broke**

```bash
docker exec zentri-backend-1 python -m pytest tests/test_net_worth_snapshot.py -v 2>&1 | tail -20
```

Expected: All pass.

---

## Task 4: Add `fetch_historical_prices()` to price_feed.py

**Files:**

- Modify: `backend/app/services/price_feed.py`

- [ ] **Step 1: Add imports at top of price_feed.py**

Add to existing imports (if not already present):

```python
from sqlalchemy import func
from app.models.transaction import Transaction
```

- [ ] **Step 2: Add `fetch_historical_prices()` function**

Add after the existing `fetch_benchmark_prices()` function:

```python
_HISTORICAL_ASSET_TYPES = {"us_stock", "etf", "crypto", "gold"}


async def fetch_historical_prices(db: AsyncSession) -> dict:
    """Fetch full yfinance history for all priced assets, back to their earliest transaction."""
    assets_result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(_HISTORICAL_ASSET_TYPES))
    )
    assets = list(assets_result.scalars().all())

    if not assets:
        logger.info("fetch_historical_prices: no priced assets found")
        return {"inserted": 0, "assets_processed": 0}

    total_inserted = 0
    processed = 0

    for asset in assets:
        earliest_result = await db.execute(
            select(func.min(Transaction.executed_at)).where(Transaction.asset_id == asset.id)
        )
        earliest_dt = earliest_result.scalar_one_or_none()
        if earliest_dt is None:
            logger.debug("fetch_historical_prices: no transactions for %s, skipping", asset.symbol)
            continue

        start_str = str(earliest_dt.date())

        def _fetch(symbol: str, start: str):
            ticker = yf.Ticker(symbol)
            return ticker.history(start=start, interval="1d")

        try:
            hist = await asyncio.get_event_loop().run_in_executor(None, _fetch, asset.symbol, start_str)
        except Exception as e:
            logger.warning("fetch_historical_prices: yfinance failed for %s: %s", asset.symbol, e)
            continue

        if hist.empty:
            logger.warning("fetch_historical_prices: empty history for %s from %s", asset.symbol, start_str)
            continue

        rows = []
        for ts, row in hist.iterrows():
            rows.append({
                "asset_id": asset.id,
                "timestamp": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                "open": _to_decimal(row.get("Open")),
                "high": _to_decimal(row.get("High")),
                "low": _to_decimal(row.get("Low")),
                "close": _to_decimal(row.get("Close")),
                "volume": _to_decimal(row.get("Volume")),
            })

        if rows:
            inserted = await _upsert_prices(db, rows)
            total_inserted += inserted
            logger.info(
                "fetch_historical_prices: %s inserted=%d from=%s",
                asset.symbol, inserted, start_str,
            )

        processed += 1

    return {"inserted": total_inserted, "assets_processed": processed}
```

- [ ] **Step 3: Verify backend imports cleanly (no syntax errors)**

```bash
docker exec zentri-backend-1 python -c "from app.services.price_feed import fetch_historical_prices; print('OK')"
```

Expected: `OK`

---

## Task 5: Add Worker Job + Register in Worker

**Files:**

- Modify: `backend/worker/jobs/price_fetch.py`
- Modify: `backend/worker/main.py`

- [ ] **Step 1: Add `fetch_historical_prices` to imports in price_fetch.py**

In `backend/worker/jobs/price_fetch.py`, add to the import from `price_feed`:

```python
from app.services.price_feed import (
    fetch_benchmark_prices,
    fetch_crypto_prices,
    fetch_gold_price,
    fetch_historical_prices,   # add this
    fetch_th_fund_prices,
    fetch_thai_stock_prices,
    fetch_us_prices,
)
```

- [ ] **Step 2: Add `job_backfill_historical_prices` function at end of price_fetch.py**

```python
async def job_backfill_historical_prices(ctx: dict, manual: bool = False) -> dict:
    """ARQ job: fetch full yfinance price history for all priced assets."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "backfill_historical_prices")
        step = await create_step(db, log.id, "fetch_and_store")
        try:
            result = await fetch_historical_prices(db)
            await finish_step(db, step, success=True, metadata=result)
            await finish_log(db, log, success=True)
            logger.info("job_backfill_historical_prices done: %s", result)
            return result
        except Exception as e:
            logger.exception("job_backfill_historical_prices failed: %s", e)
            await finish_step(db, step, success=False, error_message=str(e))
            await finish_log(db, log, success=False, error_message=str(e))
            raise
```

- [ ] **Step 3: Register in worker/main.py**

In `backend/worker/main.py`, add to the import:

```python
from worker.jobs.price_fetch import (
    job_fetch_benchmark_prices,
    job_fetch_price_gold,
    job_fetch_prices_crypto,
    job_fetch_prices_th_fund,
    job_fetch_prices_thai_stock,
    job_fetch_prices_us,
    job_backfill_historical_prices,   # add this
)
```

Add to `functions` list in `WorkerSettings`:

```python
functions = [
    job_fetch_prices_us,
    job_fetch_prices_crypto,
    job_fetch_price_gold,
    job_fetch_benchmark_prices,
    job_fetch_prices_th_fund,
    job_fetch_prices_thai_stock,
    job_backfill_historical_prices,   # add this
    job_ingest_document,
    ...
]
```

- [ ] **Step 4: Verify worker starts cleanly**

```bash
docker compose restart worker
docker compose logs worker --tail=10
```

Expected: `ARQ worker started — DB pool ready` with no import errors.

---

## Task 6: Add Frontend Pipeline Button

**Files:**

- Modify: `frontend/components/pipeline/TriggerButtons.tsx`

- [ ] **Step 1: Add button to JOBS array**

In `frontend/components/pipeline/TriggerButtons.tsx`, change:

```typescript
const JOBS: { key: JobType; label: string }[] = [
  { key: "price_fetch_us", label: "US Stock" },
  { key: "price_fetch_crypto", label: "Crypto" },
  { key: "price_fetch_gold", label: "Gold" },
  { key: "price_fetch_thai_stock", label: "Thai Stock/DR" },
  { key: "price_fetch_th_fund", label: "Thai Fund" },
  { key: "price_fetch_benchmark", label: "Benchmark" },
  { key: "snapshot_net_worth", label: "Net Worth Snapshot" },
];
```

to:

```typescript
const JOBS: { key: JobType; label: string }[] = [
  { key: "price_fetch_us", label: "US Stock" },
  { key: "price_fetch_crypto", label: "Crypto" },
  { key: "price_fetch_gold", label: "Gold" },
  { key: "price_fetch_thai_stock", label: "Thai Stock/DR" },
  { key: "price_fetch_th_fund", label: "Thai Fund" },
  { key: "price_fetch_benchmark", label: "Benchmark" },
  { key: "snapshot_net_worth", label: "Net Worth Snapshot" },
  { key: "backfill_historical_prices", label: "Backfill Price History" },
];
```

---

## Usage After Implementation

1. Go to Pipeline page
2. Click **▶ Backfill Price History** — fetches full yfinance history for all priced assets back to first transaction
3. Wait for job to complete (check pipeline jobs table)
4. Run in terminal:
   ```bash
   docker exec zentri-postgres-1 psql -U postgres -d zentri -c "DELETE FROM net_worth_snapshots;"
   ```
5. Click **▶ Net Worth Snapshot** — transaction-aware backfill creates accurate full history
6. Net Worth chart now shows complete timeline from first transaction date
