# Portfolio Holdings + Cash Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate cash accounts from holdings, add sort/filter/pagination/edit to the holdings table, and add a dedicated Cash & Bank Accounts card section.

**Architecture:** Backend gains a `platform` field on `Holding` (migration 009) and a `PATCH /portfolio/holdings/{id}` endpoint. Frontend splits the portfolio page into two stacked sections: an enhanced `HoldingsTable` (TanStack sort + filter + pagination + edit) and a new `CashAccountsSection` (cards + dialogs).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Next.js 14, TanStack Table v8, React Query, Tailwind, shadcn/ui, lucide-react

---

## File Map

### New files

| Path                                                        | Purpose                                             |
| ----------------------------------------------------------- | --------------------------------------------------- |
| `backend/alembic/versions/009_add_platform_to_holding.py`   | Migration: nullable `platform` column on `holdings` |
| `backend/tests/test_update_holding.py`                      | Tests for PATCH endpoint                            |
| `frontend/components/portfolio/EditHoldingDialog.tsx`       | Edit holding dialog (quantity, cost, currency)      |
| `frontend/components/portfolio/CashAccountsSection.tsx`     | Cash cards grid + "Add Account" button              |
| `frontend/components/portfolio/AddCashAccountDialog.tsx`    | Create cash asset + initial balance                 |
| `frontend/components/portfolio/UpdateCashBalanceDialog.tsx` | Update current balance                              |

### Modified files

| Path                                              | Change                                                                     |
| ------------------------------------------------- | -------------------------------------------------------------------------- |
| `backend/app/models/holding.py`                   | Add `platform: str \| None` field                                          |
| `backend/app/schemas/holding.py`                  | Add `platform` to `HoldingCreate`, `HoldingRow`; add `HoldingUpdate`       |
| `backend/app/services/portfolio.py`               | Update `add_holding`, `list_holdings_with_assets`; add `update_holding`    |
| `backend/app/api/portfolio.py`                    | Update `add_holding` endpoint; add `PATCH /holdings/{id}`                  |
| `frontend/lib/services/portfolio.ts`              | Add `platform` to `HoldingRow`; add `updateHolding()`                      |
| `frontend/components/portfolio/HoldingsTable.tsx` | Sort, pagination, platform filter, page-size, pencil icon, filter out cash |
| `frontend/app/(auth)/portfolio/page.tsx`          | Add `CashAccountsSection` below holdings                                   |

---

## Task 1: Add `platform` to Holding model + Alembic migration

**Files:**

- Modify: `backend/app/models/holding.py`
- Create: `backend/alembic/versions/009_add_platform_to_holding.py`

- [ ] **Step 1: Read the current Holding model**

```bash
cat backend/app/models/holding.py
```

- [ ] **Step 2: Add `platform` column to the model**

In `backend/app/models/holding.py`, add after the `updated_at` field:

```python
platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

Full imports already include `String` — confirm it's imported, add if not:

```python
from sqlalchemy import DateTime, Numeric, String, ForeignKey
```

- [ ] **Step 3: Create Alembic migration**

Create `backend/alembic/versions/009_add_platform_to_holding.py`:

```python
"""add platform to holding

Revision ID: 009
Revises: 008
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("holdings", sa.Column("platform", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("holdings", "platform")
```

- [ ] **Step 4: Apply the migration**

```bash
cd backend && alembic upgrade head
```

Expected output ends with: `Running upgrade 008 -> 009`

---

## Task 2: Update schemas + service + API for platform + update endpoint

**Files:**

- Modify: `backend/app/schemas/holding.py`
- Modify: `backend/app/services/portfolio.py`
- Modify: `backend/app/api/portfolio.py`

- [ ] **Step 1: Update `holding.py` schemas**

Replace the contents of `backend/app/schemas/holding.py` with:

```python
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str = "us_stock"
    purchased_at: date | None = None
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str = "THB"
    platform: str | None = None


class HoldingUpdate(BaseModel):
    quantity: Decimal | None = None
    avg_cost_price: Decimal | None = None
    currency: str | None = None
    platform: str | None = None


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

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    holdings_count: int
    total_cost: Decimal
    total_cost_secondary: Decimal | None = None
    primary_currency: str
    secondary_currency: str
    exchange_rate: Decimal | None = None
    exchange_rate_date: str | None = None
```

- [ ] **Step 2: Update `add_holding` service to accept + store platform**

In `backend/app/services/portfolio.py`, update `add_holding` signature and `Holding(...)` constructor:

```python
async def add_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    quantity: Decimal,
    avg_cost_price: Decimal,
    currency: str,
    purchased_at: date | None = None,
    platform: str | None = None,
) -> tuple[Holding, Asset]:
    symbol = symbol.strip().upper()
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_={},
        )
        db.add(asset)
        await db.flush()

    holding = Holding(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
        quantity=quantity, avg_cost_price=avg_cost_price,
        currency=currency, purchased_at=purchased_at,
        platform=platform,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    logger.info("Holding added: symbol=%s qty=%s user=%s", symbol, quantity, user_id)
    return holding, asset
```

- [ ] **Step 3: Update `list_holdings_with_assets` to include platform**

In `backend/app/services/portfolio.py`, update the dict inside the loop:

```python
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
    "current_price": None,
    "holding_value": None,
    "unrealized_pnl": None,
    "price_1d_change": None,
})
```

- [ ] **Step 4: Add `update_holding` service function**

Add to `backend/app/services/portfolio.py` after `delete_holding`:

```python
async def update_holding(
    db: AsyncSession,
    holding: Holding,
    data: dict,
) -> Holding:
    for field, value in data.items():
        if value is not None:
            setattr(holding, field, value)
    holding.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(holding)
    logger.info("Holding updated: id=%s", holding.id)
    return holding
```

- [ ] **Step 5: Update `add_holding` API endpoint to pass platform**

In `backend/app/api/portfolio.py`, update the `add_holding` endpoint:

```python
@router.post("/holdings", response_model=HoldingRow, status_code=201)
async def add_holding(
    body: HoldingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding, asset = await portfolio_service.add_holding(
        db, current_user.id, body.symbol, body.asset_type,
        body.quantity, body.avg_cost_price, body.currency,
        body.purchased_at, body.platform,
    )
    total_cost = holding.quantity * holding.avg_cost_price
    return HoldingRow(
        id=holding.id, asset_id=holding.asset_id,
        symbol=asset.symbol, asset_type=asset.asset_type,
        currency=holding.currency, platform=holding.platform,
        purchased_at=holding.purchased_at,
        outstanding_shares=holding.quantity, cost_per_share=holding.avg_cost_price,
        total_cost=total_cost,
    )
```

- [ ] **Step 6: Add `PATCH /holdings/{holding_id}` endpoint**

Add to `backend/app/api/portfolio.py` after the `delete_holding` route. Also add `HoldingUpdate` to the schema import:

```python
from app.schemas.holding import HoldingCreate, HoldingRow, HoldingUpdate, PortfolioSummary
```

```python
@router.patch("/holdings/{holding_id}", response_model=HoldingRow)
async def update_holding(
    holding_id: uuid.UUID,
    body: HoldingUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    holding = await portfolio_service.get_holding(db, current_user.id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    updated = await portfolio_service.update_holding(
        db, holding, body.model_dump(exclude_none=True)
    )
    # Fetch asset for symbol/asset_type
    result = await db.execute(
        select(Asset).where(Asset.id == updated.asset_id)
    )
    asset = result.scalar_one()
    total_cost = updated.quantity * updated.avg_cost_price
    return HoldingRow(
        id=updated.id, asset_id=updated.asset_id,
        symbol=asset.symbol, asset_type=asset.asset_type,
        currency=updated.currency, platform=updated.platform,
        purchased_at=updated.purchased_at,
        outstanding_shares=updated.quantity, cost_per_share=updated.avg_cost_price,
        total_cost=total_cost,
    )
```

Add `Asset` to the imports in `portfolio.py` if not already present:

```python
from app.models.asset import Asset
from sqlalchemy import select
```

---

## Task 3: Backend tests for update_holding

**Files:**

- Create: `backend/tests/test_update_holding.py`

- [ ] **Step 1: Write tests**

Create `backend/tests/test_update_holding.py`:

```python
import pytest
from decimal import Decimal


async def test_update_holding_quantity(auth_client):
    # Add a holding first
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "AAPL", "asset_type": "us_stock",
        "quantity": "10", "avg_cost_price": "150", "currency": "USD",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]

    # Update quantity
    patch = await auth_client.patch(f"/api/v1/portfolio/holdings/{holding_id}", json={
        "quantity": "20",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert data["outstanding_shares"] == "20"
    assert data["cost_per_share"] == "150"  # unchanged


async def test_update_holding_currency_and_platform(auth_client):
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "VOO", "asset_type": "etf",
        "quantity": "5", "avg_cost_price": "400", "currency": "USD",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]

    patch = await auth_client.patch(f"/api/v1/portfolio/holdings/{holding_id}", json={
        "currency": "THB",
        "platform": "Interactive Brokers",
    })
    assert patch.status_code == 200
    data = patch.json()
    assert data["currency"] == "THB"
    assert data["platform"] == "Interactive Brokers"


async def test_update_holding_not_found(auth_client):
    import uuid
    patch = await auth_client.patch(
        f"/api/v1/portfolio/holdings/{uuid.uuid4()}", json={"quantity": "5"}
    )
    assert patch.status_code == 404


async def test_update_holding_returns_platform_in_list(auth_client):
    resp = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "MSFT", "asset_type": "us_stock",
        "quantity": "3", "avg_cost_price": "300", "currency": "USD",
        "platform": "Schwab",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]
    assert resp.json()["platform"] == "Schwab"

    # Confirm it appears in list
    list_resp = await auth_client.get("/api/v1/portfolio/holdings")
    assert list_resp.status_code == 200
    match = next((h for h in list_resp.json() if h["id"] == holding_id), None)
    assert match is not None
    assert match["platform"] == "Schwab"
```

- [ ] **Step 2: Run tests**

```bash
cd backend && pytest tests/test_update_holding.py -v
```

Expected: 4 tests PASSED

---

## Task 4: Frontend service — add `platform` + `updateHolding`

**Files:**

- Modify: `frontend/lib/services/portfolio.ts`

- [ ] **Step 1: Add `platform` to `HoldingRow` interface and add `updateHolding`**

In `frontend/lib/services/portfolio.ts`, update `HoldingRow` to add `platform`, then add `updateHolding`:

```typescript
export interface HoldingRow {
  id: string;
  asset_id: string;
  symbol: string;
  asset_type: string;
  currency: string;
  platform: string | null; // ← add this
  purchased_at: string | null;
  outstanding_shares: string;
  cost_per_share: string;
  total_cost: string;
  current_price: string | null;
  holding_value: string | null;
  unrealized_pnl: string | null;
  price_1d_change: string | null;
}
```

Add after `deleteHolding`:

```typescript
export async function updateHolding(
  id: string,
  data: {
    quantity?: string;
    avg_cost_price?: string;
    currency?: string;
    platform?: string | null;
  },
): Promise<HoldingRow> {
  const res = await api.patch(`/api/v1/portfolio/holdings/${id}`, data);
  if (!res.ok) throw new Error("Failed to update holding");
  return res.json();
}
```

---

## Task 5: EditHoldingDialog component

**Files:**

- Create: `frontend/components/portfolio/EditHoldingDialog.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/portfolio/EditHoldingDialog.tsx`:

```typescript
"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { updateHolding, HoldingRow } from "@/lib/services/portfolio";

interface Props {
  holding: HoldingRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function EditHoldingDialog({ holding, open, onOpenChange, onUpdated }: Props) {
  const [quantity, setQuantity] = useState("");
  const [costPerShare, setCostPerShare] = useState("");
  const [currency, setCurrency] = useState("");
  const [platform, setPlatform] = useState("");
  const [loading, setLoading] = useState(false);

  // Sync state when holding changes
  useState(() => {
    if (holding) {
      setQuantity(holding.outstanding_shares);
      setCostPerShare(holding.cost_per_share);
      setCurrency(holding.currency);
      setPlatform(holding.platform ?? "");
    }
  });

  if (!holding) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!holding) return;
    setLoading(true);
    try {
      await updateHolding(holding.id, {
        quantity,
        avg_cost_price: costPerShare,
        currency,
        platform: platform || null,
      });
      toast.success(`${holding.symbol} updated`);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {holding.symbol}</DialogTitle>
        </DialogHeader>
        <div className="text-sm text-muted-foreground mb-2">
          {holding.asset_type}
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Outstanding Shares</Label>
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Cost per Share</Label>
              <Input
                value={costPerShare}
                onChange={(e) => setCostPerShare(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Platform (optional)</Label>
              <Input
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                placeholder="Interactive Brokers"
              />
            </div>
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Save Changes"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Fix sync — replace the broken `useState` with `useEffect`**

The `useState(() => {...})` in step 1 is wrong for syncing — replace it:

```typescript
import { useState, useEffect } from "react";

// Replace the broken useState sync with:
useEffect(() => {
  if (holding) {
    setQuantity(holding.outstanding_shares);
    setCostPerShare(holding.cost_per_share);
    setCurrency(holding.currency);
    setPlatform(holding.platform ?? "");
  }
}, [holding]);
```

Remove the `useState(() => {...})` block entirely.

---

## Task 6: Enhance HoldingsTable (sort, pagination, filter, edit)

**Files:**

- Modify: `frontend/components/portfolio/HoldingsTable.tsx`

- [ ] **Step 1: Rewrite HoldingsTable with all enhancements**

Replace the full contents of `frontend/components/portfolio/HoldingsTable.tsx`:

```typescript
"use client";

import { useMemo, useState } from "react";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Trash2, Pencil, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { HoldingRow } from "@/lib/services/portfolio";
import { PrivacyValue } from "@/components/ui/PrivacyValue";
import { EditHoldingDialog } from "./EditHoldingDialog";

interface Props {
  holdings: HoldingRow[];
  primaryCurrency: string;
  secondaryCurrency?: string;
  primaryToSecondaryRate?: number;
  onDelete: (id: string) => void;
  onUpdated: () => void;
}

export function HoldingsTable({
  holdings,
  primaryCurrency,
  secondaryCurrency,
  primaryToSecondaryRate,
  onDelete,
  onUpdated,
}: Props) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [platformFilter, setPlatformFilter] = useState<string>("all");
  const [pageSize, setPageSize] = useState(10);
  const [editHolding, setEditHolding] = useState<HoldingRow | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  // Filter out cash assets — cash is shown in the separate cash section
  const nonCashHoldings = useMemo(
    () => holdings.filter((h) => h.asset_type !== "cash"),
    [holdings],
  );

  // Unique platforms for the filter dropdown
  const platforms = useMemo(() => {
    const seen = new Set<string>();
    for (const h of nonCashHoldings) {
      if (h.platform) seen.add(h.platform);
    }
    return Array.from(seen).sort();
  }, [nonCashHoldings]);

  // Apply platform filter manually before passing to table
  const filteredHoldings = useMemo(() => {
    if (platformFilter === "all") return nonCashHoldings;
    return nonCashHoldings.filter((h) => h.platform === platformFilter);
  }, [nonCashHoldings, platformFilter]);

  function fmt(val: string | number | null | undefined, currency: string): string {
    if (val == null) return "—";
    return `${Number(val).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ${currency}`;
  }

  function MoneyCell({
    val,
    nativeCurrency,
  }: {
    val: string | null | undefined;
    nativeCurrency: string;
  }) {
    if (val == null) return <span>—</span>;
    const num = Number(val);
    const native = nativeCurrency.toUpperCase();
    const primary = primaryCurrency.toUpperCase();
    const secondary = secondaryCurrency?.toUpperCase();

    let primaryVal: number = num;
    let secondaryVal: number | null = null;

    if (native === primary) {
      primaryVal = num;
      if (primaryToSecondaryRate != null && secondaryCurrency) {
        secondaryVal = num * primaryToSecondaryRate;
      }
    } else if (native === secondary && primaryToSecondaryRate != null && primaryToSecondaryRate > 0) {
      primaryVal = num / primaryToSecondaryRate;
      secondaryVal = num;
    } else {
      return <span>{fmt(num, nativeCurrency)}</span>;
    }

    return (
      <span>
        {fmt(primaryVal, primaryCurrency)}
        {secondaryCurrency && secondaryVal != null && (
          <span className="block text-xs text-muted-foreground">
            ≈ {fmt(secondaryVal, secondaryCurrency)}
          </span>
        )}
      </span>
    );
  }

  function SortIcon({ isSorted }: { isSorted: false | "asc" | "desc" }) {
    if (!isSorted) return <ArrowUpDown className="ml-1 h-3 w-3 inline opacity-40" />;
    if (isSorted === "asc") return <ArrowUp className="ml-1 h-3 w-3 inline" />;
    return <ArrowDown className="ml-1 h-3 w-3 inline" />;
  }

  const columns: ColumnDef<HoldingRow>[] = [
    {
      accessorKey: "symbol",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Symbol <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
    },
    {
      accessorKey: "outstanding_shares",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Shares <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => Number(row.original.outstanding_shares).toLocaleString(),
    },
    {
      accessorKey: "cost_per_share",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Cost/Share <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <PrivacyValue value={<MoneyCell val={row.original.cost_per_share} nativeCurrency={row.original.currency} />} />
      ),
    },
    {
      accessorKey: "total_cost",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Total Cost <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <PrivacyValue value={<MoneyCell val={row.original.total_cost} nativeCurrency={row.original.currency} />} />
      ),
    },
    {
      accessorKey: "current_price",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Price <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <PrivacyValue value={<MoneyCell val={row.original.current_price} nativeCurrency={row.original.currency} />} />
      ),
    },
    {
      accessorKey: "price_1d_change",
      header: "1D Change",
      cell: ({ row }) => {
        const val = row.original.price_1d_change;
        if (val == null) return "—";
        const num = Number(val);
        const color = num >= 0 ? "text-green-600" : "text-red-600";
        return (
          <span className={color}>
            {num >= 0 ? "+" : ""}
            {num.toFixed(2)}%
          </span>
        );
      },
    },
    {
      accessorKey: "holding_value",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          Value <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => (
        <PrivacyValue value={<MoneyCell val={row.original.holding_value} nativeCurrency={row.original.currency} />} />
      ),
    },
    {
      accessorKey: "unrealized_pnl",
      header: ({ column }) => (
        <button
          className="flex items-center"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          P/L <SortIcon isSorted={column.getIsSorted()} />
        </button>
      ),
      cell: ({ row }) => {
        const val = row.original.unrealized_pnl;
        if (val == null) return <span>—</span>;
        const num = Number(val);
        const color = num >= 0 ? "text-green-600" : "text-red-600";
        return (
          <span className={color}>
            <PrivacyValue value={<MoneyCell val={val} nativeCurrency={row.original.currency} />} />
          </span>
        );
      },
    },
    {
      id: "actions",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              setEditHolding(row.original);
              setEditOpen(true);
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onDelete(row.original.id)}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ),
    },
  ];

  const table = useReactTable({
    data: filteredHoldings,
    columns,
    state: { sorting, pagination: { pageIndex: 0, pageSize } },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <div className="space-y-2">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Platform:</span>
          <Select
            value={platformFilter}
            onValueChange={(v) => {
              if (v !== null) {
                setPlatformFilter(v);
                table.setPageIndex(0);
              }
            }}
          >
            <SelectTrigger className="h-8 w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Platforms</SelectItem>
              {platforms.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Rows:</span>
          <Select
            value={String(pageSize)}
            onValueChange={(v) => {
              if (v !== null) {
                setPageSize(Number(v));
                table.setPageIndex(0);
              }
            }}
          >
            <SelectTrigger className="h-8 w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {[10, 25, 50].map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border">
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
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="text-center text-muted-foreground py-8"
                >
                  No holdings. Add one or import from the Import page.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Page {table.getState().pagination.pageIndex + 1} of{" "}
          {Math.max(1, table.getPageCount())}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            ← Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next →
          </Button>
        </div>
      </div>

      <EditHoldingDialog
        holding={editHolding}
        open={editOpen}
        onOpenChange={setEditOpen}
        onUpdated={onUpdated}
      />
    </div>
  );
}
```

---

## Task 7: Cash accounts components

**Files:**

- Create: `frontend/components/portfolio/AddCashAccountDialog.tsx`
- Create: `frontend/components/portfolio/UpdateCashBalanceDialog.tsx`
- Create: `frontend/components/portfolio/CashAccountsSection.tsx`

- [ ] **Step 1: Create AddCashAccountDialog**

Create `frontend/components/portfolio/AddCashAccountDialog.tsx`:

```typescript
"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { createBalance } from "@/lib/services/cash-balance";

interface Props {
  onAdded: () => void;
}

export function AddCashAccountDialog({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [symbol, setSymbol] = useState("");
  const [currency, setCurrency] = useState("");
  const [balance, setBalance] = useState("");
  const [loading, setLoading] = useState(false);

  function reset() {
    setSymbol("");
    setCurrency("");
    setBalance("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      // 1. Create the cash asset
      const assetRes = await api.post("/api/v1/assets", {
        symbol: symbol.toUpperCase(),
        asset_type: "cash",
        name: symbol.toUpperCase(),
        currency: currency.toUpperCase(),
      });
      if (!assetRes.ok) throw new Error("Failed to create account");
      const asset = await assetRes.json();

      // 2. Record initial balance snapshot
      await createBalance(
        asset.id,
        parseFloat(balance),
        new Date().toISOString().slice(0, 10),
      );

      toast.success(`${symbol.toUpperCase()} account added`);
      setOpen(false);
      reset();
      onAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={
        <Button size="sm">
          <Plus className="h-4 w-4 mr-1" />
          Add Account
        </Button>
      } />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Cash Account</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Account Name</Label>
              <Input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="SCB_THB"
                required
              />
            </div>
            <div className="space-y-1">
              <Label>Currency</Label>
              <Input
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="THB"
                required
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Initial Balance</Label>
            <Input
              type="number"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              placeholder="0"
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Adding…" : "Add Account"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Create UpdateCashBalanceDialog**

Create `frontend/components/portfolio/UpdateCashBalanceDialog.tsx`:

```typescript
"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { createBalance } from "@/lib/services/cash-balance";

interface Props {
  assetId: string;
  assetSymbol: string;
  currentBalance: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function UpdateCashBalanceDialog({
  assetId,
  assetSymbol,
  currentBalance,
  open,
  onOpenChange,
  onUpdated,
}: Props) {
  const [balance, setBalance] = useState(String(currentBalance));
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setBalance(String(currentBalance));
    setDate(new Date().toISOString().slice(0, 10));
  }, [currentBalance, open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await createBalance(assetId, parseFloat(balance), date);
      toast.success(`${assetSymbol} balance updated`);
      onOpenChange(false);
      onUpdated();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update balance");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update {assetSymbol} Balance</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label>Balance</Label>
            <Input
              type="number"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label>Date</Label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Saving…" : "Update Balance"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Create CashAccountsSection**

Create `frontend/components/portfolio/CashAccountsSection.tsx`:

```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { getLatestBalance, CashBalance } from "@/lib/services/cash-balance";
import { AddCashAccountDialog } from "./AddCashAccountDialog";
import { UpdateCashBalanceDialog } from "./UpdateCashBalanceDialog";
import { PrivacyValue } from "@/components/ui/PrivacyValue";

interface CashAsset {
  id: string;
  symbol: string;
  currency: string;
}

interface CashAccountState {
  asset: CashAsset;
  latest: CashBalance | null;
}

export function CashAccountsSection() {
  const [accounts, setAccounts] = useState<CashAccountState[]>([]);
  const [updateTarget, setUpdateTarget] = useState<CashAccountState | null>(null);
  const [updateOpen, setUpdateOpen] = useState(false);

  const load = useCallback(async () => {
    const res = await api.get("/api/v1/assets");
    if (!res.ok) return;
    const all: CashAsset[] = await res.json();
    const cashAssets = all.filter((a: any) => a.asset_type === "cash");

    const states = await Promise.all(
      cashAssets.map(async (asset) => {
        let latest: CashBalance | null = null;
        try {
          latest = await getLatestBalance(asset.id);
        } catch {
          // no snapshot yet
        }
        return { asset, latest };
      }),
    );
    setAccounts(states);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Cash &amp; Bank Accounts</h2>
        <AddCashAccountDialog onAdded={load} />
      </div>

      {accounts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No cash accounts yet. Add one to track bank balances.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {accounts.map(({ asset, latest }) => (
            <Card key={asset.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{asset.symbol}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-2xl font-bold">
                  <PrivacyValue
                    value={
                      latest
                        ? `${Number(latest.balance).toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                          })} ${asset.currency}`
                        : "—"
                    }
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {latest
                    ? `Updated: ${latest.snapshot_date}`
                    : "No balance recorded"}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => {
                    setUpdateTarget({ asset, latest });
                    setUpdateOpen(true);
                  }}
                >
                  Update Balance
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {updateTarget && (
        <UpdateCashBalanceDialog
          assetId={updateTarget.asset.id}
          assetSymbol={updateTarget.asset.symbol}
          currentBalance={updateTarget.latest ? Number(updateTarget.latest.balance) : 0}
          open={updateOpen}
          onOpenChange={setUpdateOpen}
          onUpdated={load}
        />
      )}
    </div>
  );
}
```

---

## Task 8: Wire everything into the portfolio page

**Files:**

- Modify: `frontend/app/(auth)/portfolio/page.tsx`

- [ ] **Step 1: Add `onUpdated` prop pass and import CashAccountsSection**

In `frontend/app/(auth)/portfolio/page.tsx`:

1. Add import at the top:

```typescript
import { CashAccountsSection } from "@/components/portfolio/CashAccountsSection";
```

2. Update `HoldingsTable` usage — add `onUpdated={refresh}` prop:

```tsx
<HoldingsTable
  holdings={holdings}
  primaryCurrency={displayCurrency}
  secondaryCurrency={displaySecondaryCurrency}
  primaryToSecondaryRate={...}
  onDelete={(id) => deleteMutation.mutate(id)}
  onUpdated={refresh}
/>
```

3. Add `CashAccountsSection` after the holdings section (after the `</div>` that closes the holdings block):

```tsx
<CashAccountsSection />
```

- [ ] **Step 2: Verify the page renders without TypeScript errors**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: no errors (or only pre-existing unrelated errors).

---

## Self-Review Checklist

- [x] **Task 1** covers migration 009 + model update
- [x] **Task 2** covers `HoldingUpdate` schema, `update_holding` service, `PATCH` endpoint, `platform` in all service outputs
- [x] **Task 3** covers 4 backend tests using `auth_client` fixture (matches existing test pattern)
- [x] **Task 4** adds `platform` to `HoldingRow` TS interface + `updateHolding()`
- [x] **Task 5** creates `EditHoldingDialog` with `useEffect` sync
- [x] **Task 6** rewrites `HoldingsTable` — filters cash, adds sort/pagination/filter/page-size/pencil/edit dialog trigger, passes `onUpdated` prop
- [x] **Task 7** creates all 3 cash components; `CashAccountsSection` filters assets client-side (no server-side filter)
- [x] **Task 8** wires page together + TS check
- [x] No TBD or placeholder steps
- [x] Type names consistent: `HoldingRow.platform`, `updateHolding()`, `HoldingUpdate`, `update_holding()`
