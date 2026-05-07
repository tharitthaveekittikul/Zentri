# Server-Side Search & Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add server-side search, filtering, and pagination to Portfolio holdings, Transactions, and Watchlist tables with URL-synced filter state.

**Architecture:** A shared `PaginatedResponse[T]` Pydantic generic is returned by all three list endpoints. The frontend uses a shared `useTableParams` hook (Next.js `useSearchParams` + `useRouter`) to sync filter state to the URL. The portfolio page uses two React Query calls — one unfiltered for `PlatformBreakdownCards`, one filtered+paginated for `HoldingsTable`. The transactions and watchlist pages use `useSearchParams` + `useEffect` consistent with their current patterns.

**Tech Stack:** FastAPI, SQLAlchemy (async), Pydantic v2, Next.js App Router (`useSearchParams`, `useRouter`), React Query (`@tanstack/react-query`), TypeScript

---

## File Map

### Create

- `backend/app/schemas/common.py` — `PaginatedResponse[T]` generic
- `frontend/lib/types.ts` — shared `PaginatedResponse<T>` TS interface
- `frontend/hooks/useTableParams.ts` — URL param read/write hook

### Modify

- `backend/app/services/portfolio.py` — add `list_holdings_paginated`, `list_transactions_paginated`
- `backend/app/api/portfolio.py` — update `list_holdings`, `list_transactions` endpoints
- `backend/app/api/watchlist.py` — update `list_watchlist` endpoint inline
- `backend/tests/test_portfolio.py` — update existing tests + add filter tests
- `frontend/lib/services/portfolio.ts` — update `fetchHoldings`, add `fetchTransactions`
- `frontend/lib/services/watchlist.ts` — update `listWatchlist`
- `frontend/components/portfolio/HoldingsTable.tsx` — server-driven filter/pagination
- `frontend/app/(auth)/portfolio/page.tsx` — two-query pattern
- `frontend/app/(auth)/transactions/page.tsx` — add filter bar + URL params
- `frontend/app/(auth)/watchlist/page.tsx` — add filter bar + URL params

---

## Task 1: Backend — PaginatedResponse schema

**Files:**

- Create: `backend/app/schemas/common.py`

- [ ] **Step 1: Create the schema file**

```python
# backend/app/schemas/common.py
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd /path/to/project && docker compose exec backend python -c "from app.schemas.common import PaginatedResponse; print('ok')"
```

Expected: `ok`

---

## Task 2: Backend — list_holdings_paginated service function

**Files:**

- Modify: `backend/app/services/portfolio.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_portfolio.py`:

```python
@pytest.mark.asyncio
async def test_list_holdings_paginated_search(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    res = await auth_client.get("/api/v1/portfolio/holdings?search=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "AAPL"

@pytest.mark.asyncio
async def test_list_holdings_paginated_no_match(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/holdings", json={
        "asset_id": asset_id, "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    res = await auth_client.get("/api/v1/portfolio/holdings?search=NOTEXIST")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest backend/tests/test_portfolio.py::test_list_holdings_paginated_search -v
```

Expected: FAIL (endpoint still returns a list, not paginated response)

- [ ] **Step 3: Add `list_holdings_paginated` to portfolio service**

Add this function to `backend/app/services/portfolio.py`. Also add `or_` to the existing SQLAlchemy import at the top:

```python
from sqlalchemy import func, or_, select
```

Then add after the existing `list_holdings_with_assets` function:

```python
async def list_holdings_paginated(
    db: AsyncSession,
    user_id: uuid.UUID,
    search: str | None = None,
    platform: str | None = None,
    asset_type: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    def _apply_filters(q):
        if search:
            q = q.where(or_(
                Asset.symbol.ilike(f"%{search}%"),
                Asset.name.ilike(f"%{search}%"),
            ))
        if platform:
            q = q.where(Holding.platform == platform)
        if asset_type:
            q = q.where(Asset.asset_type == asset_type)
        return q

    count_q = _apply_filters(
        select(func.count(Holding.id))
        .select_from(Holding)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    total: int = (await db.execute(count_q)).scalar_one()

    if total == 0:
        return [], 0

    max_page = (total + page_size - 1) // page_size
    page = max(1, min(page, max_page))
    offset = (page - 1) * page_size

    data_q = _apply_filters(
        select(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
        .offset(offset)
        .limit(page_size)
    )
    holdings_result = await db.execute(data_q)
    holdings_raw = list(holdings_result.all())

    asset_ids = [asset.id for _, asset in holdings_raw]
    ranked_sq = (
        select(
            Price.asset_id,
            Price.close,
            func.row_number().over(
                partition_by=Price.asset_id,
                order_by=Price.timestamp.desc(),
            ).label("rn"),
        )
        .where(Price.asset_id.in_(asset_ids))
        .subquery()
    )
    price_result = await db.execute(
        select(ranked_sq.c.asset_id, ranked_sq.c.close, ranked_sq.c.rn)
        .where(ranked_sq.c.rn <= 2)
    )
    price_map: dict[uuid.UUID, dict[int, Decimal]] = {}
    for row in price_result:
        price_map.setdefault(row.asset_id, {})[row.rn] = row.close

    rows = []
    for holding, asset in holdings_raw:
        prices = price_map.get(asset.id, {})
        latest_close = prices.get(1)
        prev_close = prices.get(2)
        total_cost = holding.quantity * holding.avg_cost_price
        holding_value = holding.quantity * latest_close if latest_close else None
        unrealized_pnl = (holding_value - total_cost) if holding_value is not None else None
        price_1d_change = (
            (latest_close - prev_close) / prev_close * 100
            if latest_close and prev_close and prev_close != 0
            else None
        )
        rows.append({
            "id": holding.id,
            "asset_id": holding.asset_id,
            "symbol": asset.symbol,
            "asset_type": asset.asset_type,
            "currency": holding.currency,
            "platform": holding.platform,
            "purchased_at": holding.purchased_at,
            "outstanding_shares": holding.quantity,
            "cost_per_share": holding.avg_cost_price,
            "total_cost": total_cost,
            "current_price": latest_close,
            "holding_value": holding_value,
            "unrealized_pnl": unrealized_pnl,
            "price_1d_change": price_1d_change,
        })
    return rows, total
```

---

## Task 3: Backend — list_transactions_paginated service function

**Files:**

- Modify: `backend/app/services/portfolio.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_portfolio.py`:

```python
@pytest.mark.asyncio
async def test_list_transactions_paginated_search(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z",
    })
    res = await auth_client.get("/api/v1/portfolio/transactions?search=AAPL")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["symbol"] == "AAPL"

@pytest.mark.asyncio
async def test_list_transactions_paginated_type_filter(auth_client, asset_id):
    await auth_client.post("/api/v1/portfolio/transactions", json={
        "asset_id": asset_id, "type": "buy", "quantity": "5",
        "price": "155", "fee": "1", "executed_at": "2026-01-15T10:00:00Z",
    })
    res = await auth_client.get("/api/v1/portfolio/transactions?type=sell")
    assert res.status_code == 200
    assert res.json()["total"] == 0
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest backend/tests/test_portfolio.py::test_list_transactions_paginated_search -v
```

Expected: FAIL

- [ ] **Step 3: Add `list_transactions_paginated` to portfolio service**

Add after `list_transactions_with_assets` in `backend/app/services/portfolio.py`. The `date` and `time` types are already imported (`from datetime import date, datetime, timezone`). Add `time` to that import:

```python
from datetime import date, datetime, time, timezone
```

Then add the function:

```python
async def list_transactions_paginated(
    db: AsyncSession,
    user_id: uuid.UUID,
    search: str | None = None,
    asset_id: uuid.UUID | None = None,
    type_: str | None = None,
    platform: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict], int]:
    def _apply_filters(q):
        if search:
            q = q.where(or_(
                Asset.symbol.ilike(f"%{search}%"),
                Asset.name.ilike(f"%{search}%"),
            ))
        if asset_id:
            q = q.where(Transaction.asset_id == asset_id)
        if type_:
            q = q.where(Transaction.type == type_)
        if platform:
            q = q.where(Transaction.platform == platform)
        if date_from:
            q = q.where(
                Transaction.executed_at >= datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
            )
        if date_to:
            q = q.where(
                Transaction.executed_at <= datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
            )
        return q

    count_q = _apply_filters(
        select(func.count(Transaction.id))
        .select_from(Transaction)
        .join(Asset, Asset.id == Transaction.asset_id)
        .where(Transaction.user_id == user_id)
    )
    total: int = (await db.execute(count_q)).scalar_one()

    if total == 0:
        return [], 0

    max_page = (total + page_size - 1) // page_size
    page = max(1, min(page, max_page))
    offset = (page - 1) * page_size

    data_q = _apply_filters(
        select(Transaction, Asset)
        .join(Asset, Asset.id == Transaction.asset_id)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.executed_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_q)

    rows = []
    for tx, asset in result.all():
        rows.append({
            "id": tx.id,
            "asset_id": tx.asset_id,
            "symbol": asset.symbol,
            "asset_type": asset.asset_type,
            "platform": tx.platform,
            "type": tx.type,
            "quantity": tx.quantity,
            "price": tx.price,
            "fee": tx.fee,
            "source": tx.source,
            "executed_at": tx.executed_at,
            "created_at": tx.created_at,
        })
    return rows, total
```

---

## Task 4: Backend — Update holdings endpoint

**Files:**

- Modify: `backend/app/api/portfolio.py`

- [ ] **Step 1: Update imports in `backend/app/api/portfolio.py`**

Add `PaginatedResponse` to the import block at the top of the file:

```python
from app.schemas.common import PaginatedResponse
```

Also add `list_holdings_paginated` to the portfolio service imports (the file already imports `from app.services import portfolio as portfolio_service`, so no import change needed there).

- [ ] **Step 2: Replace `list_holdings` endpoint**

Find the existing `list_holdings` function and replace it:

```python
@router.get("/holdings", response_model=PaginatedResponse[HoldingRow])
async def list_holdings(
    search: str | None = None,
    platform: str | None = None,
    asset_type: str | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await portfolio_service.list_holdings_paginated(
        db, current_user.id,
        search=search, platform=platform, asset_type=asset_type,
        page=page, page_size=page_size,
    )
    return PaginatedResponse(
        items=[HoldingRow(**r) for r in rows],
        total=total, page=page, page_size=page_size,
    )
```

- [ ] **Step 3: Run new tests**

```bash
pytest backend/tests/test_portfolio.py::test_list_holdings_paginated_search backend/tests/test_portfolio.py::test_list_holdings_paginated_no_match -v
```

Expected: PASS

- [ ] **Step 4: Update broken existing tests**

In `backend/tests/test_portfolio.py`, find and update the tests that still expect a raw list:

`test_list_holdings` — change:

```python
# Old:
assert len(response.json()) == 1
# New:
data = response.json()
assert data["total"] == 1
assert len(data["items"]) == 1
```

- [ ] **Step 5: Run full portfolio test suite**

```bash
pytest backend/tests/test_portfolio.py -v
```

Expected: All PASS

---

## Task 5: Backend — Update transactions endpoint

**Files:**

- Modify: `backend/app/api/portfolio.py`

- [ ] **Step 1: Replace `list_transactions` endpoint**

Find the existing `list_transactions` function and replace it (keep `asset_id` param for backward compat with portfolio detail page):

```python
@router.get("/transactions", response_model=PaginatedResponse[TransactionRow])
async def list_transactions(
    search: str | None = None,
    asset_id: uuid.UUID | None = None,
    type: str | None = None,
    platform: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await portfolio_service.list_transactions_paginated(
        db, current_user.id,
        search=search, asset_id=asset_id, type_=type,
        platform=platform, date_from=date_from, date_to=date_to,
        page=page, page_size=page_size,
    )
    return PaginatedResponse(items=rows, total=total, page=page, page_size=page_size)
```

Also add `date` to the import at the top of `backend/app/api/portfolio.py`:

```python
from datetime import date
```

- [ ] **Step 2: Run new transaction tests**

```bash
pytest backend/tests/test_portfolio.py::test_list_transactions_paginated_search backend/tests/test_portfolio.py::test_list_transactions_paginated_type_filter -v
```

Expected: PASS

- [ ] **Step 3: Update broken existing transaction tests**

In `backend/tests/test_portfolio.py`, update tests that expect raw list:

`test_list_transactions_for_asset`:

```python
# Old:
assert len(response.json()) == 1
# New:
data = response.json()
assert data["total"] == 1
```

`test_list_transactions_includes_symbol`:

```python
# Old:
assert res.json()[0]["symbol"] == "AAPL"
# New:
data = res.json()
assert data["total"] == 1
assert data["items"][0]["symbol"] == "AAPL"
```

- [ ] **Step 4: Run full test suite**

```bash
pytest backend/tests/test_portfolio.py -v
```

Expected: All PASS

---

## Task 6: Backend — Update watchlist endpoint

**Files:**

- Modify: `backend/app/api/watchlist.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_watchlist.py` if it doesn't exist, or add to it:

```python
import pytest

@pytest.mark.asyncio
async def test_list_watchlist_paginated(auth_client):
    res = await auth_client.get("/api/v1/watchlist")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert data["items"] == []
    assert data["total"] == 0

@pytest.mark.asyncio
async def test_list_watchlist_alert_status_filter(auth_client):
    res = await auth_client.get("/api/v1/watchlist?alert_status=enabled")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest backend/tests/test_watchlist.py -v 2>/dev/null || pytest backend/tests/ -k "watchlist" -v
```

Expected: FAIL (returns list, not paginated response)

- [ ] **Step 3: Update imports in `backend/app/api/watchlist.py`**

Add at the top of the imports section:

```python
from sqlalchemy import and_, func, or_, select
from app.schemas.common import PaginatedResponse
```

(Note: `and_` and `select` are likely already imported; add `func`, `or_`, and `PaginatedResponse` if not present.)

- [ ] **Step 4: Replace `list_watchlist` function**

Find the `list_watchlist` function in `backend/app/api/watchlist.py` and replace it:

```python
@router.get("", response_model=PaginatedResponse[WatchlistItemOut])
async def list_watchlist(
    search: str | None = None,
    asset_type: str | None = None,
    alert_status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    def _apply_filters(q):
        if search:
            q = q.where(or_(
                Asset.symbol.ilike(f"%{search}%"),
                Asset.name.ilike(f"%{search}%"),
            ))
        if asset_type:
            q = q.where(Asset.asset_type == asset_type)
        if alert_status == "enabled":
            from app.models.watchlist_item import WatchlistItem as WatchlistItemModel
            q = q.where(
                WatchlistItemModel.alert_enabled.is_(True),
                WatchlistItemModel.alerted_at.is_(None),
            )
        elif alert_status == "triggered":
            from app.models.watchlist_item import WatchlistItem as WatchlistItemModel
            q = q.where(WatchlistItemModel.alerted_at.isnot(None))
        elif alert_status == "disabled":
            from app.models.watchlist_item import WatchlistItem as WatchlistItemModel
            q = q.where(WatchlistItemModel.alert_enabled.is_(False))
        return q

    # Use the WatchlistItem model that's already imported in this file
    # (whatever it's named — check existing imports at top of watchlist.py)
    WatchlistItemModel = WatchlistItem  # use the model class already imported

    count_q = _apply_filters(
        select(func.count(WatchlistItemModel.id))
        .select_from(WatchlistItemModel)
        .join(Asset, Asset.id == WatchlistItemModel.asset_id)
        .where(WatchlistItemModel.user_id == current_user.id)
    )
    total: int = (await db.execute(count_q)).scalar_one()

    if total == 0:
        return PaginatedResponse(items=[], total=0, page=1, page_size=page_size)

    max_page = (total + page_size - 1) // page_size
    page = max(1, min(page, max_page))
    offset = (page - 1) * page_size

    data_q = _apply_filters(
        select(WatchlistItemModel)
        .join(Asset, Asset.id == WatchlistItemModel.asset_id)
        .where(WatchlistItemModel.user_id == current_user.id)
        .order_by(WatchlistItemModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_q)
    items = list(result.scalars().all())

    out_items = [await _item_to_out(db, item) for item in items]
    return PaginatedResponse(items=out_items, total=total, page=page, page_size=page_size)
```

> **Note on `WatchlistItem` model name:** Check the existing imports at the top of `watchlist.py`. The model class is imported there — use whatever name it's imported as (likely `WatchlistItem`). The `_apply_filters` inner function closure issue with the model class can be resolved by using the outer scope `WatchlistItemModel` variable instead of re-importing inside the closure. Refactor `_apply_filters` to reference `WatchlistItemModel` from the outer scope.

Cleaner version of `_apply_filters` without inner imports:

```python
@router.get("", response_model=PaginatedResponse[WatchlistItemOut])
async def list_watchlist(
    search: str | None = None,
    asset_type: str | None = None,
    alert_status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # WatchlistItem here is the SQLAlchemy model (already imported at top of file)
    base_q_holdings = (
        select(func.count(WatchlistItem.id))
        .select_from(WatchlistItem)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == current_user.id)
    )
    base_q_data = (
        select(WatchlistItem)
        .join(Asset, Asset.id == WatchlistItem.asset_id)
        .where(WatchlistItem.user_id == current_user.id)
    )

    if search:
        flt = or_(Asset.symbol.ilike(f"%{search}%"), Asset.name.ilike(f"%{search}%"))
        base_q_holdings = base_q_holdings.where(flt)
        base_q_data = base_q_data.where(flt)
    if asset_type:
        base_q_holdings = base_q_holdings.where(Asset.asset_type == asset_type)
        base_q_data = base_q_data.where(Asset.asset_type == asset_type)
    if alert_status == "enabled":
        flt = and_(WatchlistItem.alert_enabled.is_(True), WatchlistItem.alerted_at.is_(None))
        base_q_holdings = base_q_holdings.where(flt)
        base_q_data = base_q_data.where(flt)
    elif alert_status == "triggered":
        flt = WatchlistItem.alerted_at.isnot(None)
        base_q_holdings = base_q_holdings.where(flt)
        base_q_data = base_q_data.where(flt)
    elif alert_status == "disabled":
        flt = WatchlistItem.alert_enabled.is_(False)
        base_q_holdings = base_q_holdings.where(flt)
        base_q_data = base_q_data.where(flt)

    total: int = (await db.execute(base_q_holdings)).scalar_one()

    if total == 0:
        return PaginatedResponse(items=[], total=0, page=1, page_size=page_size)

    max_page = (total + page_size - 1) // page_size
    page = max(1, min(page, max_page))
    offset = (page - 1) * page_size

    result = await db.execute(
        base_q_data.order_by(WatchlistItem.created_at.desc()).offset(offset).limit(page_size)
    )
    db_items = list(result.scalars().all())
    out_items = [await _item_to_out(db, item) for item in db_items]
    return PaginatedResponse(items=out_items, total=total, page=page, page_size=page_size)
```

> **Important:** `WatchlistItem` in this context refers to the SQLAlchemy **model** class. Verify the import at the top of `watchlist.py` — if there is a naming conflict with the Pydantic schema, rename one of them (e.g., `from app.models.watchlist_item import WatchlistItem as WatchlistItemModel`).

- [ ] **Step 5: Run watchlist tests**

```bash
pytest backend/tests/ -k "watchlist" -v
```

Expected: All PASS

---

## Task 7: Frontend — Shared types + useTableParams hook

**Files:**

- Create: `frontend/lib/types.ts`
- Create: `frontend/hooks/useTableParams.ts`

- [ ] **Step 1: Create shared types file**

```typescript
// frontend/lib/types.ts
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
```

- [ ] **Step 2: Create useTableParams hook**

```typescript
// frontend/hooks/useTableParams.ts
"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export function useTableParams() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const get = useCallback(
    (key: string, fallback = "") => searchParams.get(key) ?? fallback,
    [searchParams],
  );

  const getInt = useCallback(
    (key: string, fallback: number) =>
      Number(searchParams.get(key) ?? fallback),
    [searchParams],
  );

  const setParam = useCallback(
    (updates: Record<string, string | number | null>, resetPage = true) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === "") {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      if (resetPage && !("page" in updates)) {
        params.set("page", "1");
      }
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return { get, getInt, setParam };
}
```

---

## Task 8: Frontend — Update portfolio service

**Files:**

- Modify: `frontend/lib/services/portfolio.ts`

- [ ] **Step 1: Add PaginatedResponse import and update fetchHoldings**

At the top of `frontend/lib/services/portfolio.ts`, add:

```typescript
import { PaginatedResponse } from "@/lib/types";
```

Add `HoldingsParams` interface and update `fetchHoldings`:

```typescript
export interface HoldingsParams {
  search?: string;
  platform?: string;
  asset_type?: string;
  page?: number;
  page_size?: number;
}

export async function fetchHoldings(
  params: HoldingsParams = {},
): Promise<PaginatedResponse<HoldingRow>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.platform) qs.set("platform", params.platform);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const res = await api.get(
    `/api/v1/portfolio/holdings${query ? `?${query}` : ""}`,
  );
  if (!res.ok) throw new Error("Failed to fetch holdings");
  return res.json();
}
```

- [ ] **Step 2: Add TransactionRow type and fetchTransactions**

The `TransactionRow` type is currently defined locally in the transactions page. Move it to the service file and add `fetchTransactions`:

```typescript
export interface TransactionRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency?: string;
  platform: string | null;
  type: string;
  quantity: string;
  price: string;
  fee: string;
  source: string;
  executed_at: string;
  created_at: string;
}

export interface TransactionParams {
  search?: string;
  asset_id?: string;
  type?: string;
  platform?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export async function fetchTransactions(
  params: TransactionParams = {},
): Promise<PaginatedResponse<TransactionRow>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.asset_id) qs.set("asset_id", params.asset_id);
  if (params.type) qs.set("type", params.type);
  if (params.platform) qs.set("platform", params.platform);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const res = await api.get(
    `/api/v1/portfolio/transactions${query ? `?${query}` : ""}`,
  );
  if (!res.ok) throw new Error("Failed to fetch transactions");
  return res.json();
}
```

---

## Task 9: Frontend — Update watchlist service

**Files:**

- Modify: `frontend/lib/services/watchlist.ts`

- [ ] **Step 1: Add PaginatedResponse import and update listWatchlist**

At the top of `frontend/lib/services/watchlist.ts`, add:

```typescript
import { PaginatedResponse } from "@/lib/types";
```

Add `WatchlistParams` interface and update `listWatchlist`:

```typescript
export interface WatchlistParams {
  search?: string;
  asset_type?: string;
  alert_status?: string;
  page?: number;
  page_size?: number;
}

export async function listWatchlist(
  params: WatchlistParams = {},
): Promise<PaginatedResponse<WatchlistItem>> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.asset_type) qs.set("asset_type", params.asset_type);
  if (params.alert_status) qs.set("alert_status", params.alert_status);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  const query = qs.toString();
  const r = await api.get(`/api/v1/watchlist${query ? `?${query}` : ""}`);
  if (!r.ok) throw new Error("Failed to fetch watchlist");
  return r.json();
}
```

---

## Task 10: Frontend — Update HoldingsTable component

**Files:**

- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

- [ ] **Step 1: Update imports and Props interface**

Replace the existing imports and Props:

```typescript
import { PaginatedResponse } from "@/lib/types";
import { HoldingRow } from "@/lib/services/portfolio";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
// Keep existing imports: ColumnDef, flexRender, getCoreRowModel, getSortedRowModel,
// SortingState, useReactTable, Table components, Button, Select, Trash2, Pencil,
// ArrowUpDown, ArrowUp, ArrowDown, ArrowUpRight, ArrowDownRight,
// useDualCurrency, DualCurrencyAmount, EditHoldingDialog, AlertDialog components
```

Change Props:

```typescript
interface TableParams {
  search: string;
  platform: string;
  asset_type: string;
  page: number;
  page_size: number;
}

interface Props {
  data: PaginatedResponse<HoldingRow>;
  params: TableParams;
  onParamChange: (updates: Record<string, string | number | null>) => void;
  onDelete: (id: string) => void;
  onUpdated: () => void;
  isFetching?: boolean;
}
```

- [ ] **Step 2: Rewrite HoldingsTable body**

Replace the entire function body. Remove `platformFilter`, `filteredHoldings`, `platforms` state/memos. Remove `getPaginationRowModel` from React Table. Add filter bar with search, platform, asset type controls.

```typescript
export function HoldingsTable({
  data,
  params,
  onParamChange,
  onDelete,
  onUpdated,
  isFetching = false,
}: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [searchInput, setSearchInput] = useState(params.search);
  const [editHolding, setEditHolding] = useState<HoldingRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<HoldingRow | null>(null);

  const { formatNative } = useDualCurrency();

  // Sync local search input to URL with debounce
  useEffect(() => {
    setSearchInput(params.search);
  }, [params.search]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (searchInput !== params.search) {
        onParamChange({ search: searchInput || null });
      }
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  function SortIcon({ isSorted }: { isSorted: false | "asc" | "desc" }) {
    if (!isSorted) return <ArrowUpDown className="ml-1 h-3 w-3 inline opacity-40" />;
    if (isSorted === "asc") return <ArrowUp className="ml-1 h-3 w-3 inline" />;
    return <ArrowDown className="ml-1 h-3 w-3 inline" />;
  }

  // columns definition — same as before, unchanged
  const columns: ColumnDef<HoldingRow>[] = [
    // ... keep existing column definitions verbatim
  ];

  const table = useReactTable({
    data: data.items,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    // No getPaginationRowModel — pagination is server-driven
  });

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8 h-9"
            placeholder="Search symbol or name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <Select
          value={params.platform || "all"}
          onValueChange={(v) => onParamChange({ platform: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Platform" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Platforms</SelectItem>
            {/* Platforms are now fetched from server — show common options or derive from data */}
            {Array.from(new Set(data.items.map((h) => h.platform).filter(Boolean))).map((p) => (
              <SelectItem key={p!} value={p!}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={params.asset_type || "all"}
          onValueChange={(v) => onParamChange({ asset_type: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[160px]">
            <SelectValue placeholder="Asset Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {["us_stock", "thai_stock", "crypto", "etf", "bond", "fund"].map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Rows:</span>
          <Select
            value={String(params.page_size)}
            onValueChange={(v) => onParamChange({ page_size: Number(v), page: 1 }, false)}
          >
            <SelectTrigger className="h-8 w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[25, 50, 100].map((n) => (
                <SelectItem key={n} value={String(n)}>{n}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className={`bg-card card-surface rounded-2xl border border-border overflow-x-auto transition-opacity ${isFetching ? "opacity-60" : ""}`}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => (
                  <TableHead key={h.id}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="hover:bg-muted/40 transition-colors duration-150">
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-12">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <span className="text-2xl">📋</span>
                    <span className="text-sm font-medium">No holdings found</span>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {data.total > 0
            ? `${(params.page - 1) * params.page_size + 1}–${Math.min(params.page * params.page_size, data.total)} of ${data.total}`
            : "0 results"}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline" size="sm"
            onClick={() => onParamChange({ page: params.page - 1 }, false)}
            disabled={params.page <= 1}
          >
            ← Prev
          </Button>
          <span className="flex items-center px-2">
            Page {params.page} of {totalPages}
          </span>
          <Button
            variant="outline" size="sm"
            onClick={() => onParamChange({ page: params.page + 1 }, false)}
            disabled={params.page >= totalPages}
          >
            Next →
          </Button>
        </div>
      </div>

      {/* EditHoldingDialog and AlertDialog — unchanged from original */}
      <EditHoldingDialog
        holding={editHolding}
        open={editOpen}
        onOpenChange={setEditOpen}
        onUpdated={onUpdated}
      />
      {/* ... keep existing AlertDialog verbatim ... */}
    </div>
  );
}
```

> **Note on `useEffect` import:** Add `useEffect` to the React import at the top of the file since it's now used for debounce.

---

## Task 11: Frontend — Update portfolio page

**Files:**

- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Add imports**

Add to the import block:

```typescript
import { useTableParams } from "@/hooks/useTableParams";
import { HoldingsParams } from "@/lib/services/portfolio";
```

- [ ] **Step 2: Add useTableParams and update queries**

Inside `PortfolioPage`, add after the existing `useEffect`:

```typescript
const { get, getInt, setParam } = useTableParams();

const tableParams: HoldingsParams = {
  search: get("search") || undefined,
  platform: get("platform") || undefined,
  asset_type: get("asset_type") || undefined,
  page: getInt("page", 1),
  page_size: getInt("page_size", 25),
};

// Unfiltered fetch — for PlatformBreakdownCards (always fetches all)
const { data: allHoldings } = useQuery({
  queryKey: ["holdings-all"],
  queryFn: () => fetchHoldings({ page: 1, page_size: 1000 }),
});

// Filtered+paginated fetch — for HoldingsTable
const { data: holdingsPage, isFetching: holdingsFetching } = useQuery({
  queryKey: ["holdings", tableParams],
  queryFn: () => fetchHoldings(tableParams),
  placeholderData: (prev) => prev,
});
```

Remove the old single holdings query:

```typescript
// Remove this:
const { data: holdings = [], isLoading } = useQuery({
  queryKey: ["holdings"],
  queryFn: fetchHoldings,
});
```

- [ ] **Step 3: Update JSX — PlatformBreakdownCards and HoldingsTable**

Update `PlatformBreakdownCards` to use unfiltered data:

```typescript
<PlatformBreakdownCards holdings={allHoldings?.items ?? []} />
```

Update `HoldingsTable`:

```typescript
{holdingsPage ? (
  <HoldingsTable
    data={holdingsPage}
    params={{
      search: tableParams.search ?? "",
      platform: tableParams.platform ?? "",
      asset_type: tableParams.asset_type ?? "",
      page: tableParams.page ?? 1,
      page_size: tableParams.page_size ?? 25,
    }}
    onParamChange={setParam}
    onDelete={(id) => deleteMutation.mutate(id)}
    onUpdated={refresh}
    isFetching={holdingsFetching}
  />
) : (
  <Skeleton className="h-48 w-full" />
)}
```

Update `refresh` to also invalidate the new query keys:

```typescript
const refresh = () => {
  qc.invalidateQueries({ queryKey: ["holdings"] });
  qc.invalidateQueries({ queryKey: ["holdings-all"] });
  qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
};
```

---

## Task 12: Frontend — Update transactions page

**Files:**

- Modify: `frontend/app/(auth)/transactions/page.tsx`

- [ ] **Step 1: Replace imports**

Replace the top of the file:

```typescript
"use client";

import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pencil, Search, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { useTableParams } from "@/hooks/useTableParams";
import { api } from "@/lib/api";
import {
  fetchTransactions,
  TransactionRow,
  type TransactionParams,
} from "@/lib/services/portfolio";
import type { PaginatedResponse } from "@/lib/types";
```

- [ ] **Step 2: Rewrite TransactionsPage**

Replace `TransactionsPage` function. Remove the local `TransactionRow` type definition (now imported). Replace the `fetchTransactions` / `useEffect` / `useState` data-fetching logic with URL-param-driven fetching:

```typescript
export default function TransactionsPage() {
  const { formatNative } = useDualCurrency();
  const { get, getInt, setParam } = useTableParams();

  const [data, setData] = useState<PaginatedResponse<TransactionRow>>({
    items: [], total: 0, page: 1, page_size: 25,
  });
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [editTarget, setEditTarget] = useState<TransactionRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TransactionRow | null>(null);
  const [editForm, setEditForm] = useState<Partial<TransactionRow>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [searchInput, setSearchInput] = useState(get("search"));

  const params: TransactionParams = {
    search: get("search") || undefined,
    type: get("type") || undefined,
    platform: get("platform") || undefined,
    date_from: get("date_from") || undefined,
    date_to: get("date_to") || undefined,
    page: getInt("page", 1),
    page_size: getInt("page_size", 25),
  };

  useEffect(() => {
    setFetching(true);
    fetchTransactions(params)
      .then(setData)
      .finally(() => { setLoading(false); setFetching(false); });
  // params is reconstructed from searchParams which changes reference each render — stringify to stabilize
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    get("search"), get("type"), get("platform"),
    get("date_from"), get("date_to"),
    getInt("page", 1), getInt("page_size", 25),
  ]);

  // Debounce search input → URL
  useEffect(() => {
    setSearchInput(get("search"));
  }, [get("search")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const t = setTimeout(() => {
      const current = get("search");
      if (searchInput !== current) setParam({ search: searchInput || null });
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = () => {
    setFetching(true);
    fetchTransactions(params).then(setData).finally(() => setFetching(false));
  };

  const openEdit = (tx: TransactionRow) => {
    setEditTarget(tx);
    setEditForm({
      type: tx.type, quantity: tx.quantity, price: tx.price,
      fee: tx.fee, executed_at: tx.executed_at.slice(0, 16),
      platform: tx.platform ?? "",
    });
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    const res = await api.patch(`/api/v1/portfolio/transactions/${editTarget.id}`, {
      type: editForm.type,
      quantity: editForm.quantity ? parseFloat(editForm.quantity) : undefined,
      price: editForm.price ? parseFloat(editForm.price) : undefined,
      fee: editForm.fee ? parseFloat(editForm.fee) : undefined,
      executed_at: editForm.executed_at
        ? new Date(editForm.executed_at).toISOString() : undefined,
      platform: editForm.platform || null,
    });
    setSaving(false);
    if (res.ok) { setEditTarget(null); reload(); }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    await api.delete(`/api/v1/portfolio/transactions/${deleteTarget.id}`);
    setDeleting(false);
    setDeleteTarget(null);
    reload();
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-4">
      <PageHeader title="Transactions" />

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8 h-9"
            placeholder="Search symbol or name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
        <Select
          value={get("type") || "all"}
          onValueChange={(v) => setParam({ type: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {["buy", "sell", "dividend", "reward", "fee", "transfer"].map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={get("platform") || "all"}
          onValueChange={(v) => setParam({ platform: v === "all" ? null : v })}
        >
          <SelectTrigger className="h-9 w-[140px]">
            <SelectValue placeholder="Platform" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Platforms</SelectItem>
            {Array.from(new Set(data.items.map((t) => t.platform).filter(Boolean))).map((p) => (
              <SelectItem key={p!} value={p!}>{p}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="date"
          className="h-9 w-[150px]"
          value={get("date_from")}
          onChange={(e) => setParam({ date_from: e.target.value || null })}
        />
        <span className="text-muted-foreground text-sm">to</span>
        <Input
          type="date"
          className="h-9 w-[150px]"
          value={get("date_to")}
          onChange={(e) => setParam({ date_to: e.target.value || null })}
        />
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : (
        <>
          <div className={`rounded-md border overflow-x-auto transition-opacity ${fetching ? "opacity-60" : ""}`}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Asset</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Fee</TableHead>
                  <TableHead>Platform</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                      No transactions found
                    </TableCell>
                  </TableRow>
                )}
                {data.items.map((tx) => (
                  <TableRow key={tx.id}>
                    <TableCell className="text-sm">
                      {new Date(tx.executed_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="font-medium">{tx.symbol}</TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[tx.type] ?? "bg-gray-100 text-gray-800"}`}>
                        {tx.type}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {parseFloat(tx.quantity).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <DualCurrencyAmount value={formatNative(tx.price, tx.currency ?? "USD")} />
                    </TableCell>
                    <TableCell className="text-right">
                      <DualCurrencyAmount value={formatNative(tx.fee, tx.currency ?? "USD")} />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">{tx.platform ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(tx)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(tx)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total > 0
                ? `${(data.page - 1) * data.page_size + 1}–${Math.min(data.page * data.page_size, data.total)} of ${data.total}`
                : "0 results"}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline" size="sm"
                onClick={() => setParam({ page: data.page - 1 }, false)}
                disabled={data.page <= 1}
              >← Prev</Button>
              <span className="flex items-center px-2">Page {data.page} of {totalPages}</span>
              <Button
                variant="outline" size="sm"
                onClick={() => setParam({ page: data.page + 1 }, false)}
                disabled={data.page >= totalPages}
              >Next →</Button>
            </div>
          </div>
        </>
      )}

      {/* Edit Dialog — keep existing verbatim */}
      {/* Delete Dialog — keep existing verbatim */}
    </div>
  );
}
```

> **Note:** Keep `TYPE_COLORS` constant, Edit Dialog, and Delete Dialog exactly as they are in the current file.

---

## Task 13: Frontend — Update watchlist page

**Files:**

- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Add imports**

Add to the existing import block:

```typescript
import { useTableParams } from "@/hooks/useTableParams";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import type { PaginatedResponse } from "@/lib/types";
import type { WatchlistParams } from "@/lib/services/watchlist";
```

- [ ] **Step 2: Update WatchlistPage state and fetching**

Add `useTableParams` and change `items` state from `WatchlistItem[]` to `PaginatedResponse<WatchlistItem>`:

```typescript
const { get, getInt, setParam } = useTableParams();
const [itemsPage, setItemsPage] = useState<PaginatedResponse<WatchlistItem>>({
  items: [],
  total: 0,
  page: 1,
  page_size: 25,
});
const [searchInput, setSearchInput] = useState(get("search"));
```

Remove the old `const [items, setItems] = useState<WatchlistItem[]>([])`.

Update `fetchAll` to pass params:

```typescript
const fetchAll = useCallback(async () => {
  const params: WatchlistParams = {
    search: get("search") || undefined,
    asset_type: get("asset_type") || undefined,
    alert_status: get("alert_status") || undefined,
    page: getInt("page", 1),
    page_size: getInt("page_size", 25),
  };
  setLoading(true);
  const [w, s] = await Promise.all([
    listWatchlist(params).catch(() => ({
      items: [],
      total: 0,
      page: 1,
      page_size: 25,
    })),
    listSuggestions().catch(() => []),
  ]);
  setItemsPage(w as PaginatedResponse<WatchlistItem>);
  setSuggestions(s);
  setLoading(false);
}, [get, getInt]); // eslint-disable-line react-hooks/exhaustive-deps
```

Add debounce for search:

```typescript
useEffect(() => {
  setSearchInput(get("search"));
}, [get("search")]); // eslint-disable-line react-hooks/exhaustive-deps

useEffect(() => {
  const t = setTimeout(() => {
    const current = get("search");
    if (searchInput !== current) setParam({ search: searchInput || null });
  }, 300);
  return () => clearTimeout(t);
}, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps
```

Re-trigger `fetchAll` when URL params change:

```typescript
useEffect(() => {
  fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [
  get("search"),
  get("asset_type"),
  get("alert_status"),
  getInt("page", 1),
  getInt("page_size", 25),
]);
```

Remove the old `useEffect(() => { fetchAll(); }, [fetchAll]);`.

- [ ] **Step 3: Add filter bar to JSX**

Add after `<PageHeader title="Watchlist" />` and before the action buttons row:

```typescript
{/* Filter bar */}
<div className="flex flex-wrap items-center gap-3">
  <div className="relative flex-1 min-w-[180px]">
    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
    <Input
      className="pl-8 h-9"
      placeholder="Search symbol or name…"
      value={searchInput}
      onChange={(e) => setSearchInput(e.target.value)}
    />
  </div>
  <Select
    value={get("asset_type") || "all"}
    onValueChange={(v) => setParam({ asset_type: v === "all" ? null : v })}
  >
    <SelectTrigger className="h-9 w-[150px]">
      <SelectValue placeholder="Asset Type" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Types</SelectItem>
      {["us_stock", "thai_stock", "crypto", "etf", "bond", "fund"].map((t) => (
        <SelectItem key={t} value={t}>{t}</SelectItem>
      ))}
    </SelectContent>
  </Select>
  <Select
    value={get("alert_status") || "all"}
    onValueChange={(v) => setParam({ alert_status: v === "all" ? null : v })}
  >
    <SelectTrigger className="h-9 w-[150px]">
      <SelectValue placeholder="Alert Status" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="all">All Statuses</SelectItem>
      <SelectItem value="enabled">Enabled</SelectItem>
      <SelectItem value="triggered">Triggered</SelectItem>
      <SelectItem value="disabled">Disabled</SelectItem>
    </SelectContent>
  </Select>
</div>
```

- [ ] **Step 4: Update table rendering and add pagination**

In the table section, change `items.map(...)` to `itemsPage.items.map(...)`, and `items.length === 0` to `itemsPage.items.length === 0`.

After the closing `</div>` of the table, add pagination:

```typescript
{/* Pagination */}
{itemsPage.total > 0 && (
  <div className="flex items-center justify-between text-sm text-muted-foreground">
    <span>
      {`${(itemsPage.page - 1) * itemsPage.page_size + 1}–${Math.min(itemsPage.page * itemsPage.page_size, itemsPage.total)} of ${itemsPage.total}`}
    </span>
    <div className="flex gap-2">
      <Button
        variant="outline" size="sm"
        onClick={() => setParam({ page: itemsPage.page - 1 }, false)}
        disabled={itemsPage.page <= 1}
      >← Prev</Button>
      <span className="flex items-center px-2">
        Page {itemsPage.page} of {Math.max(1, Math.ceil(itemsPage.total / itemsPage.page_size))}
      </span>
      <Button
        variant="outline" size="sm"
        onClick={() => setParam({ page: itemsPage.page + 1 }, false)}
        disabled={itemsPage.page >= Math.ceil(itemsPage.total / itemsPage.page_size)}
      >Next →</Button>
    </div>
  </div>
)}
```

Also add `Select` import if not present:

```typescript
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
```

---

## Self-Review Notes

- `PaginatedResponse` generic in Pydantic v2 requires `model_config = ConfigDict(arbitrary_types_allowed=True)` only if items contain non-Pydantic types — not needed here since all item types are already Pydantic models.
- `WatchlistItem` name conflict in `watchlist.py`: check if the model is imported as `WatchlistItem` or under another alias — adjust the endpoint code accordingly.
- `useSearchParams` in Next.js App Router works in Client Components without Suspense when pages are dynamically rendered (authenticated routes already are).
- The `fetchAll` dependency array in the watchlist page: listing `get(...)` and `getInt(...)` calls in the dep array is intentional — each returns a primitive derived from `searchParams`, so these are stable across renders when the URL doesn't change.
