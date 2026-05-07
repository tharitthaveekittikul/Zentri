# Logo Ticker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show company logos (24px circle) left of every ticker symbol across portfolio, watchlist, events, and transactions pages, stored as `logo_url` in `metadata_` JSONB.

**Architecture:** A `get_logo_url` backend utility fetches the Google favicon URL via yfinance's `website` field at asset creation time and stores it in `metadata_["logo_url"]`. The frontend `TickerLogo` component reads this field and renders a lazy-loaded `next/image`; `onError` hides it so plain-text ticker shows instead. No DB migration needed.

**Tech Stack:** Python/FastAPI backend, yfinance, Next.js 14 App Router, `next/image`, shadcn/ui tables.

---

## File Map

| Action | File |
|---|---|
| Create | `backend/app/services/logo.py` |
| Modify | `backend/app/api/assets.py` |
| Modify | `backend/app/services/portfolio.py` |
| Modify | `backend/app/schemas/holding.py` |
| Modify | `backend/app/schemas/transaction.py` |
| Modify | `backend/app/schemas/watchlist.py` |
| Modify | `backend/app/schemas/events.py` |
| Modify | `backend/app/services/events_calendar.py` |
| Create | `frontend/components/ui/TickerLogo.tsx` |
| Modify | `frontend/lib/services/portfolio.ts` |
| Modify | `frontend/lib/services/watchlist.ts` |
| Modify | `frontend/lib/services/events.ts` |
| Modify | `frontend/app/(auth)/portfolio/page.tsx` (via HoldingsTable) |
| Modify | `frontend/app/(auth)/watchlist/page.tsx` |
| Modify | `frontend/app/(auth)/events/page.tsx` |
| Modify | `frontend/app/(auth)/transactions/page.tsx` |
| Modify | `frontend/app/(auth)/portfolio/[symbol]/page.tsx` |

---

## Task 1: `get_logo_url` utility

**Files:**
- Create: `backend/app/services/logo.py`

- [ ] **Step 1: Create the utility**

```python
# backend/app/services/logo.py
from app.core.logging import get_logger

logger = get_logger(__name__)

_THAI_TYPES = {"thai_stock", "thai_dr"}
_SUPPORTED_TYPES = {"us_stock", "etf", "thai_stock", "thai_dr"}


def get_logo_url(symbol: str, asset_type: str) -> str | None:
    if asset_type not in _SUPPORTED_TYPES:
        return None
    try:
        import yfinance as yf
        yf_symbol = f"{symbol}.BK" if asset_type in _THAI_TYPES else symbol
        info = yf.Ticker(yf_symbol).info
        website = info.get("website", "")
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        url = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        logger.info("Logo URL resolved: symbol=%s url=%s", symbol, url)
        return url
    except Exception:
        logger.warning("Failed to resolve logo for symbol=%s", symbol)
        return None
```

- [ ] **Step 2: Verify the import works in the container**

```bash
docker exec zentri-backend-1 python -c "from app.services.logo import get_logo_url; print(get_logo_url('AAPL', 'us_stock'))"
```

Expected output: `https://www.google.com/s2/favicons?domain=www.apple.com&sz=64`

---

## Task 2: Populate `logo_url` at asset creation in `assets.py`

**Files:**
- Modify: `backend/app/api/assets.py`

- [ ] **Step 1: Add logo fetch to the `create_asset` endpoint**

In `backend/app/api/assets.py`, find the `create_asset` endpoint. Update it to populate `logo_url` in metadata before calling the service:

```python
@router.post("", response_model=AssetResponse, status_code=201)
async def create_asset(
    body: AssetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.logo import get_logo_url
    import asyncio
    metadata = dict(body.metadata_)
    if "logo_url" not in metadata:
        logo = await asyncio.get_event_loop().run_in_executor(
            None, get_logo_url, body.symbol, body.asset_type
        )
        if logo:
            metadata["logo_url"] = logo
    return await asset_service.create_asset(
        db, current_user.id, body.symbol, body.asset_type, body.name, body.currency, metadata
    )
```

- [ ] **Step 2: Add logo fetch to `backfill-logos` endpoint**

Add after the existing `refresh-names` endpoint in `backend/app/api/assets.py`:

```python
@router.post("/backfill-logos")
async def backfill_logos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import asyncio
    from app.services.logo import get_logo_url

    assets = await asset_service.get_all_assets(db, current_user.id)
    updated = 0
    for asset in assets:
        if asset.metadata_.get("logo_url"):
            continue
        logo = await asyncio.get_event_loop().run_in_executor(
            None, get_logo_url, asset.symbol, asset.asset_type
        )
        if logo:
            asset.metadata_ = {**asset.metadata_, "logo_url": logo}
            updated += 1
    await db.commit()
    return {"updated": updated, "total": len(assets)}
```

- [ ] **Step 3: Verify the endpoint registers**

```bash
docker exec zentri-backend-1 python -c "from app.api.assets import router; print([r.path for r in router.routes])"
```

Expected: list includes `/backfill-logos`

---

## Task 3: Populate `logo_url` when `add_holding` creates a new asset

**Files:**
- Modify: `backend/app/services/portfolio.py`

- [ ] **Step 1: Add logo fetch in `add_holding` when asset is new**

In `backend/app/services/portfolio.py`, find the `add_holding` function. In the `if asset is None:` branch, add logo fetch before creating the `Asset`:

```python
# At top of file add:
import asyncio

# Inside add_holding, in the `if asset is None:` block, replace:
#   asset = Asset(... metadata_=metadata_ or {} ...)
# with:
        from app.services.logo import get_logo_url
        resolved_meta = dict(metadata_ or {})
        if "logo_url" not in resolved_meta:
            logo = await asyncio.get_event_loop().run_in_executor(
                None, get_logo_url, symbol, asset_type
            )
            if logo:
                resolved_meta["logo_url"] = logo
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_=resolved_meta,
        )
```

- [ ] **Step 2: Same change in `add_manual_transaction` when asset is new**

In `backend/app/services/portfolio.py`, find `add_manual_transaction`. In its `if asset is None:` branch, replace:

```python
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_={},
        )
```

with:

```python
        from app.services.logo import get_logo_url
        resolved_meta: dict = {}
        logo = await asyncio.get_event_loop().run_in_executor(
            None, get_logo_url, symbol, asset_type
        )
        if logo:
            resolved_meta["logo_url"] = logo
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_=resolved_meta,
        )
```

- [ ] **Step 3: Restart backend and verify no import errors**

```bash
docker restart zentri-backend-1 && sleep 3 && docker logs zentri-backend-1 --tail 10
```

Expected: no `ImportError` or `TypeError` in logs.

---

## Task 4: Add `metadata_` to `HoldingRow` backend + query

**Files:**
- Modify: `backend/app/schemas/holding.py`
- Modify: `backend/app/services/portfolio.py`

- [ ] **Step 1: Add `metadata_` field to `HoldingRow` schema**

In `backend/app/schemas/holding.py`, add to `HoldingRow`:

```python
class HoldingRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    currency: str
    platform: str | None = None
    purchased_at: date | None
    outstanding_shares: Decimal
    cost_per_share: Decimal
    total_cost: Decimal
    current_price: Decimal | None = None
    holding_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_1d_change: Decimal | None = None
    metadata_: dict = {}          # ← add this line

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Include `metadata_` in the holdings row dicts from `list_holdings_paginated`**

In `backend/app/services/portfolio.py`, find `list_holdings_paginated`. The function builds a `list[dict]` passed to `HoldingRow(**r)`. Find where rows are assembled (look for `"symbol"`, `"asset_type"` keys in the dict) and add `"metadata_": asset.metadata_` to each row dict.

The assembly likely looks like:
```python
rows.append({
    ...existing fields...,
    "metadata_": asset.metadata_,
})
```

Add `"metadata_": asset.metadata_` wherever `"symbol"` and `"asset_type"` are set in the row dict.

- [ ] **Step 3: Verify holdings API returns metadata**

```bash
docker exec zentri-backend-1 python -c "
import asyncio
from app.core.database import get_async_session
async def test():
    async for db in get_async_session():
        from app.services.portfolio import list_holdings_paginated
        from uuid import UUID
        rows, _ = await list_holdings_paginated(db, UUID('00000000-0000-0000-0000-000000000000'))
        print('metadata_ key present:', 'metadata_' in (rows[0] if rows else {}))
        break
asyncio.run(test())
"
```

Expected: `metadata_ key present: True` (or empty list if no holdings for that UUID — just verifies no crash)

---

## Task 5: Add `metadata_` to `TransactionRow` backend + query

**Files:**
- Modify: `backend/app/schemas/transaction.py`
- Modify: `backend/app/services/portfolio.py` (transaction list function)

- [ ] **Step 1: Add `metadata_` to `TransactionRow`**

In `backend/app/schemas/transaction.py`, update `TransactionRow`:

```python
class TransactionRow(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    asset_type: str
    platform: str | None
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    created_at: datetime
    metadata_: dict = {}          # ← add this line

    model_config = {"from_attributes": False}
```

- [ ] **Step 2: Include `metadata_` in the transaction list query**

In `backend/app/services/portfolio.py`, find the function that builds `TransactionRow` dicts (search for `"TransactionRow"` or the transaction list function). Add `"metadata_": asset.metadata_` to the row dict. The transaction query already joins `Asset`, so `asset.metadata_` is available.

- [ ] **Step 3: Restart and confirm no errors**

```bash
docker restart zentri-backend-1 && sleep 3 && docker logs zentri-backend-1 --tail 5
```

---

## Task 6: Add `asset_type` + `metadata_` to watchlist `AssetSummary`

**Files:**
- Modify: `backend/app/schemas/watchlist.py`

- [ ] **Step 1: Extend `AssetSummary`**

In `backend/app/schemas/watchlist.py`, update `AssetSummary`:

```python
class AssetSummary(BaseModel):
    id: uuid.UUID
    symbol: str
    name: str
    currency: str
    asset_type: str               # ← add
    metadata_: dict = {}          # ← add
    model_config = ConfigDict(from_attributes=True)
```

Because `AssetSummary` uses `from_attributes=True` and reads from the `Asset` ORM model (which has both `asset_type` and `metadata_`), no query changes are needed.

- [ ] **Step 2: Restart and verify watchlist API response includes new fields**

```bash
docker restart zentri-backend-1 && sleep 3
curl -s -H "Authorization: Bearer <your_token>" http://localhost:8000/api/v1/watchlist | python3 -m json.tool | grep -A2 '"asset"'
```

Expected: `asset` object now includes `"asset_type"` and `"metadata_"` keys.

---

## Task 7: Add `asset_type` + `metadata_` to calendar event schemas

**Files:**
- Modify: `backend/app/schemas/events.py`
- Modify: `backend/app/services/events_calendar.py`

- [ ] **Step 1: Add fields to event schemas**

In `backend/app/schemas/events.py`:

```python
class DividendCalendarEvent(BaseModel):
    event_type: Literal["dividend"] = "dividend"
    id: uuid.UUID
    symbol: str
    asset_id: uuid.UUID
    event_date: date
    pay_date: Optional[date] = None
    amount_per_share: Decimal
    currency: str
    status: str
    projected_total_usd: Decimal
    quantity_held: Decimal
    is_in_watchlist: bool = False
    asset_type: str = "us_stock"    # ← add
    metadata_: dict = {}            # ← add


class IpoCalendarEvent(BaseModel):
    event_type: Literal["ipo"] = "ipo"
    id: uuid.UUID
    symbol: str
    event_date: date
    company_name: Optional[str] = None
    price_low: Optional[Decimal] = None
    price_high: Optional[Decimal] = None
    sector: Optional[str] = None
    status: str
    is_in_watchlist: bool = False
    asset_type: Optional[str] = None  # ← add (IPOs may not have a user asset)
    metadata_: dict = {}              # ← add
```

- [ ] **Step 2: Populate the new fields in `events_calendar.py`**

In `backend/app/services/events_calendar.py`, find where `DividendCalendarEvent` is constructed. Add `asset_type=asset.asset_type, metadata_=asset.metadata_` (the dividend event already joins the `Asset` model via `asset_id`).

For `IpoCalendarEvent`, if the IPO is linked to a user asset (via `is_in_watchlist`), populate from that asset. Otherwise leave as defaults.

- [ ] **Step 3: Restart and verify**

```bash
docker restart zentri-backend-1 && sleep 3 && docker logs zentri-backend-1 --tail 5
```

---

## Task 8: `TickerLogo` frontend component

**Files:**
- Create: `frontend/components/ui/TickerLogo.tsx`

- [ ] **Step 1: Create the component**

```tsx
"use client";

import Image from "next/image";
import { useState } from "react";

export function TickerLogo({
  symbol,
  logoUrl,
  size = 24,
}: {
  symbol: string;
  logoUrl?: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);

  if (!logoUrl || failed) return null;

  return (
    <Image
      src={logoUrl}
      alt={symbol}
      width={size}
      height={size}
      unoptimized
      loading="lazy"
      className="rounded-full object-contain shrink-0"
      onError={() => setFailed(true)}
    />
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /path/to/project/frontend && npx tsc --noEmit 2>&1 | grep TickerLogo
```

Expected: no output (no errors for this file).

---

## Task 9: Update frontend types for `metadata_`

**Files:**
- Modify: `frontend/lib/services/portfolio.ts`
- Modify: `frontend/lib/services/watchlist.ts`
- Modify: `frontend/lib/services/events.ts`

- [ ] **Step 1: Add `metadata_` to `HoldingRow` interface in `portfolio.ts`**

In `frontend/lib/services/portfolio.ts`, find `export interface HoldingRow` and add:

```ts
export interface HoldingRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency: string;
  platform: string | null;
  purchased_at: string | null;
  outstanding_shares: string;
  cost_per_share: string;
  total_cost: string;
  current_price: string | null;
  holding_value: string | null;
  unrealized_pnl: string | null;
  price_1d_change: string | null;
  metadata_?: Record<string, unknown>;   // ← add
}
```

- [ ] **Step 2: Add `asset_type` + `metadata_` to `WatchlistItem` in `watchlist.ts`**

In `frontend/lib/services/watchlist.ts`, find `WatchlistItem` interface (or the `asset` nested type) and add the new fields. Since the backend sends `asset: { id, symbol, name, currency, asset_type, metadata_ }`, update or add the `asset` nested type:

```ts
export interface WatchlistAsset {
  id: string;
  symbol: string;
  name: string;
  currency: string;
  asset_type: string;               // ← add
  metadata_?: Record<string, unknown>; // ← add
}
```

- [ ] **Step 3: Add `asset_type` + `metadata_` to calendar event types in `events.ts`**

In `frontend/lib/services/events.ts`:

```ts
export type DividendCalendarEvent = {
  event_type: "dividend";
  id: string;
  symbol: string;
  asset_id: string;
  event_date: string;
  pay_date: string | null;
  amount_per_share: string;
  currency: string;
  status: "upcoming" | "payable" | "paid";
  projected_total_usd: string;
  quantity_held: string;
  is_in_watchlist: boolean;
  asset_type: string;                    // ← add
  metadata_?: Record<string, unknown>;   // ← add
};

export type IpoCalendarEvent = {
  event_type: "ipo";
  id: string;
  symbol: string;
  event_date: string;
  company_name: string | null;
  price_low: string | null;
  price_high: string | null;
  sector: string | null;
  status: "upcoming" | "priced" | "listed";
  is_in_watchlist: boolean;
  asset_type?: string | null;            // ← add
  metadata_?: Record<string, unknown>;   // ← add
};
```

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new type errors related to `metadata_`, `asset_type`, or `TickerLogo`.

---

## Task 10: Update `HoldingsTable` — portfolio symbol column

**Files:**
- Modify: Find the `HoldingsTable` component file (search `grep -r "HoldingsTable" frontend/app --include="*.tsx" -l`)

- [ ] **Step 1: Find the HoldingsTable component**

```bash
grep -r "HoldingsTable" /path/to/frontend --include="*.tsx" -l
```

- [ ] **Step 2: Update the symbol cell**

Find where `row.symbol` is rendered in the table cell. Replace:

```tsx
<TableCell className="font-medium">{row.symbol}</TableCell>
```

with:

```tsx
<TableCell className="font-medium">
  <div className="flex items-center gap-2">
    <TickerLogo
      symbol={row.symbol}
      logoUrl={row.metadata_?.logo_url as string | undefined}
    />
    <span>{row.symbol}</span>
  </div>
</TableCell>
```

Add the import at the top of the file:

```tsx
import { TickerLogo } from "@/components/ui/TickerLogo";
```

- [ ] **Step 3: Verify in browser**

Start dev server (`docker logs zentri-frontend-1` or local `npm run dev`). Open `/portfolio`. Confirm logos appear for US and Thai stocks, plain text for assets without logos. No console errors.

---

## Task 11: Update watchlist page — ticker column

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Find the ticker cell**

In `watchlist/page.tsx`, find the `<TableHead>Ticker</TableHead>` column. Find the corresponding `<TableCell>` that renders the symbol. It likely renders `item.asset.symbol` or similar.

- [ ] **Step 2: Update the cell**

Replace the symbol-only render with:

```tsx
<TableCell>
  <div className="flex items-center gap-2">
    <TickerLogo
      symbol={item.asset.symbol}
      logoUrl={item.asset.metadata_?.logo_url as string | undefined}
    />
    <span className="font-medium">{item.asset.symbol}</span>
  </div>
</TableCell>
```

Add import:

```tsx
import { TickerLogo } from "@/components/ui/TickerLogo";
```

- [ ] **Step 3: Verify in browser**

Open `/watchlist`. Logos appear next to tickers. No layout shift from missing logos.

---

## Task 12: Update events page — symbol column + calendar chips

**Files:**
- Modify: `frontend/app/(auth)/events/page.tsx`

- [ ] **Step 1: Update the upcoming events table symbol cell**

In `events/page.tsx`, find `<TableCell className="font-medium">` that renders `{ev.symbol}`. Replace:

```tsx
<TableCell className="font-medium">
  {ev.is_in_watchlist && <span className="text-yellow-500 mr-1">★</span>}
  {ev.symbol}
</TableCell>
```

with:

```tsx
<TableCell className="font-medium">
  <div className="flex items-center gap-2">
    {ev.is_in_watchlist && <span className="text-yellow-500">★</span>}
    <TickerLogo
      symbol={ev.symbol}
      logoUrl={ev.metadata_?.logo_url as string | undefined}
    />
    <span>{ev.symbol}</span>
  </div>
</TableCell>
```

- [ ] **Step 2: Update calendar chip symbol display**

In the calendar grid, find where `{ev.symbol}` is rendered inside a chip div. Replace:

```tsx
{ev.is_in_watchlist && <span>★</span>}
{ev.symbol}
```

with:

```tsx
{ev.is_in_watchlist && <span>★</span>}
<TickerLogo symbol={ev.symbol} logoUrl={ev.metadata_?.logo_url as string | undefined} size={16} />
{ev.symbol}
```

Add import:

```tsx
import { TickerLogo } from "@/components/ui/TickerLogo";
```

- [ ] **Step 3: Verify in browser**

Open `/events`. Logos appear in the table and calendar chips.

---

## Task 13: Update transactions page — asset column

**Files:**
- Modify: `frontend/app/(auth)/transactions/page.tsx`

- [ ] **Step 1: Find the asset column cell**

In `transactions/page.tsx`, find:

```tsx
<TableCell className="font-medium">{tx.symbol}</TableCell>
```

- [ ] **Step 2: Update the cell**

Replace with:

```tsx
<TableCell className="font-medium">
  <div className="flex items-center gap-2">
    <TickerLogo
      symbol={tx.symbol}
      logoUrl={tx.metadata_?.logo_url as string | undefined}
    />
    <span>{tx.symbol}</span>
  </div>
</TableCell>
```

Add the `TransactionRow` type update (add `metadata_?: Record<string, unknown>` to the frontend transaction type if defined locally in this file, otherwise it was already done in Task 9).

Add import:

```tsx
import { TickerLogo } from "@/components/ui/TickerLogo";
```

- [ ] **Step 3: Verify in browser**

Open `/transactions`. Logos appear in asset column.

---

## Task 14: Update portfolio detail page header

**Files:**
- Modify: `frontend/app/(auth)/portfolio/[symbol]/page.tsx`

- [ ] **Step 1: Find the page header symbol display**

In `portfolio/[symbol]/page.tsx`, find where the symbol is displayed in the page header (likely a `<h1>` or `PageHeader` component with the symbol string).

- [ ] **Step 2: Fetch asset data and add logo**

The page already fetches asset data (it uses `symbol` from params). Find the asset data fetch and add logo display. The pattern will be:

```tsx
<div className="flex items-center gap-3">
  <TickerLogo
    symbol={asset.symbol}
    logoUrl={asset.metadata_?.logo_url as string | undefined}
    size={32}
  />
  <h1 className="text-2xl font-bold">{asset.symbol}</h1>
</div>
```

Add import:

```tsx
import { TickerLogo } from "@/components/ui/TickerLogo";
```

- [ ] **Step 3: Verify in browser**

Open any stock detail page (e.g. `/portfolio/AAPL`). 32px logo appears in the header.

---

## Task 15: Run backfill for existing assets

- [ ] **Step 1: Call the backfill endpoint**

```bash
curl -X POST http://localhost:8000/api/v1/assets/backfill-logos \
  -H "Authorization: Bearer <your_token>"
```

Expected response: `{"updated": N, "total": M}` where N > 0.

- [ ] **Step 2: Reload portfolio and verify logos appear for existing assets**

Hard-refresh `/portfolio`. Logos should now appear for previously-created US and Thai stock holdings.

---

## Self-Review Checklist

- [x] `logo.py` utility covered (Task 1)
- [x] Logo populated at `create_asset` API (Task 2)
- [x] Logo populated at `add_holding` (Task 3)
- [x] Logo populated at `add_manual_transaction` (Task 3)
- [x] Backfill endpoint (Task 2)
- [x] `HoldingRow` metadata propagated backend + frontend (Tasks 4, 9)
- [x] `TransactionRow` metadata propagated backend + frontend (Tasks 5, 9)
- [x] Watchlist `AssetSummary` has `asset_type` + `metadata_` (Tasks 6, 9)
- [x] Calendar events have `asset_type` + `metadata_` (Tasks 7, 9)
- [x] `TickerLogo` component (Task 8)
- [x] All 5 UI locations updated (Tasks 10–14)
- [x] Crypto logo: `CoinGeckoResult.thumb` — **NOTE**: The crypto path goes through `create_asset` API which calls `get_logo_url`. `get_logo_url` skips crypto (not in `_SUPPORTED_TYPES`). The caller (the import pipeline or add-holding flow) must pass `metadata_={"logo_url": coingecko_thumb}` when creating crypto assets. Check `backend/app/api/assets.py` create flow for crypto — the `body.metadata_` already passes through, so if the frontend passes `thumb` as `metadata_.logo_url` at creation time, it works. No extra task needed if the existing asset creation forms already send this.
