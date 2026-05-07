# Server-Side Search & Filter for Portfolio, Watchlist, Transactions

**Date:** 2026-05-07  
**Scope:** Portfolio (holdings), Watchlist, Transactions tables

---

## Goal

Replace client-side filtering/pagination on all three tables with server-side search, filtering, and pagination. Filter state is synced to the URL so views are shareable and bookmarkable.

---

## Backend

### Shared Schema

New file: `backend/app/schemas/common.py`

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

### Endpoints

#### `GET /portfolio/holdings`
| Param | Type | Description |
|---|---|---|
| `search` | `str \| None` | ILIKE match on symbol or asset name |
| `platform` | `str \| None` | Exact match |
| `asset_type` | `str \| None` | Exact match (stock, crypto, etf, etc.) |
| `page` | `int` | Default: 1 |
| `page_size` | `int` | Default: 25 |

Returns: `PaginatedResponse[HoldingRow]`

#### `GET /portfolio/transactions`
| Param | Type | Description |
|---|---|---|
| `search` | `str \| None` | ILIKE match on symbol or asset name |
| `asset_id` | `uuid \| None` | Kept for backward compat (portfolio detail page uses this) |
| `type` | `str \| None` | buy, sell, dividend |
| `platform` | `str \| None` | Exact match |
| `date_from` | `date \| None` | Filter executed_at >= date_from |
| `date_to` | `date \| None` | Filter executed_at <= date_to |
| `page` | `int` | Default: 1 |
| `page_size` | `int` | Default: 25 |

Returns: `PaginatedResponse[TransactionRow]`

#### `GET /watchlist`
| Param | Type | Description |
|---|---|---|
| `search` | `str \| None` | ILIKE match on symbol or asset name |
| `asset_type` | `str \| None` | Exact match |
| `alert_status` | `str \| None` | `enabled` = alert_enabled=True AND alerted_at IS NULL; `triggered` = alerted_at IS NOT NULL; `disabled` = alert_enabled=False |
| `page` | `int` | Default: 1 |
| `page_size` | `int` | Default: 25 |

Returns: `PaginatedResponse[WatchlistItemOut]`

### Service Layer

New service functions (query logic stays out of the API layer):

- `portfolio_service.list_holdings_paginated(db, user_id, params)` 
- `portfolio_service.list_transactions_paginated(db, user_id, params)`
- Watchlist pagination logic stays inline in `backend/app/api/watchlist.py` — consistent with existing pattern (no separate watchlist service file)

Each function:
1. Builds a base query filtered by `user_id`
2. Applies `ILIKE %search%` on symbol/name if `search` is provided
3. Applies exact-match filters where provided
4. Runs `COUNT(*)` on the filtered query for `total`
5. Applies `LIMIT page_size OFFSET (page-1)*page_size`
6. Clamps `page` to last valid page if it exceeds total pages

---

## Frontend

### Shared Hook: `useTableParams`

File: `frontend/hooks/useTableParams.ts`

Reads and writes URL search params via Next.js `useSearchParams` + `useRouter`. Exposes:

```ts
{ params, setParam, resetParams }
```

- Text search is debounced 300ms before being pushed to the URL
- Any filter change resets `page` to 1 automatically

### Data Fetching

Each table page uses React Query with URL params as the query key:

```ts
useQuery(['holdings', params], () => fetchHoldings(params))
```

Changing any filter or page automatically triggers a refetch. `isFetching` drives a loading indicator.

### Table Components

All three table components updated to accept:
- `data: PaginatedResponse<T>` instead of a raw array
- `params` + `onParamChange` props

Changes per component:

**HoldingsTable** (`frontend/components/portfolio/HoldingsTable.tsx`):
- Remove client-side `platformFilter` state and `filteredHoldings` memo
- Remove `getPaginationRowModel` from React Table config (pagination now server-driven)
- Add filter bar: text search input + platform select + asset type select
- Add server-driven pagination controls (prev/next + "Page X of Y")

**TransactionsTable** (new component or existing page update):
- Filter bar: text search + type select (buy/sell/dividend) + platform select + date range (from/to)
- Server-driven pagination

**WatchlistTable** (existing watchlist page update):
- Filter bar: text search + asset type select + alert status select (enabled/triggered/disabled)
- Server-driven pagination

### URL Structure

Example URLs after filter interaction:
- `/portfolio?search=AAPL&platform=Robinhood&page=2`
- `/transactions?search=BTC&type=buy&date_from=2026-01-01&date_to=2026-03-31`
- `/watchlist?search=&asset_type=crypto&alert_status=enabled&page=1`

---

## Error Handling & Edge Cases

| Case | Behavior |
|---|---|
| `page` exceeds total pages | Backend clamps to last valid page |
| `date_from` > `date_to` | Returns empty results, no error |
| No results | Existing empty-state UI, no change |
| Filter change | `page` resets to 1 |
| Page load with URL params | Params read from URL, used as initial query — bookmark/share works |
| Refetching | `isFetching` shows skeleton/spinner over table rows |

---

## Files to Create / Modify

### Create
- `backend/app/schemas/common.py` — `PaginatedResponse[T]`
- `frontend/hooks/useTableParams.ts` — shared URL param hook

### Modify
- `backend/app/api/portfolio.py` — update `list_holdings`, `list_transactions` endpoints
- `backend/app/api/watchlist.py` — update `list_watchlist` endpoint
- `backend/app/services/portfolio.py` — add `list_holdings_paginated`, `list_transactions_paginated`
- `frontend/components/portfolio/HoldingsTable.tsx` — server-side filter/pagination
- `frontend/app/(auth)/transactions/page.tsx` — add filter bar + server pagination
- `frontend/app/(auth)/watchlist/page.tsx` — add filter bar + server pagination
- `frontend/lib/services/portfolio.ts` — update API call to accept paginated params
- `frontend/lib/services/watchlist.ts` — update API call to accept paginated params
