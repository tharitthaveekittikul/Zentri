# Cash & Bank Accounts — Edit & Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add edit (name, currency, account number) and delete with confirmation to each Cash & Bank Account card.

**Architecture:** Backend gains `PATCH` and `DELETE` endpoints on `/api/v1/assets/{id}`. Frontend adds pencil + trash icon buttons to each card header; edit opens a pre-filled `EditCashAccountDialog`; delete opens an `AlertDialog` confirm. `CashBalance` rows have no cascade delete, so the service deletes them manually before deleting the asset.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Next.js + shadcn/ui (frontend), pytest + httpx (tests)

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/app/schemas/asset.py` |
| Modify | `backend/app/services/asset.py` |
| Modify | `backend/app/api/assets.py` |
| Modify | `backend/tests/test_assets.py` |
| Create | `frontend/components/portfolio/EditCashAccountDialog.tsx` |
| Modify | `frontend/components/portfolio/CashAccountsSection.tsx` |

---

## Task 1: Extend asset schema

**Files:**
- Modify: `backend/app/schemas/asset.py`

- [ ] **Step 1: Add `AssetUpdate` and expose `metadata_` in `AssetResponse`**

Open `backend/app/schemas/asset.py`. Replace the entire file contents with:

```python
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class AssetCreate(BaseModel):
    symbol: str
    asset_type: Literal["us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash"]
    name: str
    currency: str = "USD"
    metadata_: dict[str, Any] = {}


class AssetUpdate(BaseModel):
    symbol: str | None = None
    name: str | None = None
    currency: str | None = None
    metadata_: dict[str, Any] | None = None


class AssetResponse(BaseModel):
    id: uuid.UUID
    symbol: str
    asset_type: str
    name: str
    currency: str
    metadata_: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}
```

---

## Task 2: Add `update_asset` and `delete_asset` to the service

**Files:**
- Modify: `backend/app/services/asset.py`

- [ ] **Step 1: Write failing tests first**

Add to `backend/tests/test_assets.py`:

```python
@pytest.mark.asyncio
async def test_patch_asset(auth_client):
    create = await auth_client.post("/api/v1/assets", json={
        "symbol": "SCB_THB", "asset_type": "cash", "name": "SCB_THB", "currency": "THB",
        "metadata_": {"account_number": "111-1-11111-1"},
    })
    asset_id = create.json()["id"]

    response = await auth_client.patch(f"/api/v1/assets/{asset_id}", json={
        "symbol": "SCB_THB2",
        "name": "SCB_THB2",
        "currency": "THB",
        "metadata_": {"account_number": "222-2-22222-2"},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "SCB_THB2"
    assert data["metadata_"]["account_number"] == "222-2-22222-2"


@pytest.mark.asyncio
async def test_patch_asset_not_found(auth_client):
    import uuid
    response = await auth_client.patch(f"/api/v1/assets/{uuid.uuid4()}", json={"symbol": "X"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_asset(auth_client):
    create = await auth_client.post("/api/v1/assets", json={
        "symbol": "KTB_THB", "asset_type": "cash", "name": "KTB_THB", "currency": "THB",
    })
    asset_id = create.json()["id"]

    # Add a cash balance to verify cascade
    await auth_client.post("/api/v1/cash-balances", json={
        "asset_id": asset_id, "balance": 5000.0, "snapshot_date": "2026-05-06",
    })

    response = await auth_client.delete(f"/api/v1/assets/{asset_id}")
    assert response.status_code == 204

    get = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_asset_not_found(auth_client):
    import uuid
    response = await auth_client.delete(f"/api/v1/assets/{uuid.uuid4()}")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_assets.py::test_patch_asset tests/test_assets.py::test_delete_asset -v
```

Expected: FAIL — `405 Method Not Allowed` or `404` (endpoints don't exist yet).

- [ ] **Step 3: Add service functions**

Open `backend/app/services/asset.py`. Append these two functions at the end of the file (after `get_all_assets`):

```python
async def update_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    updates: dict[str, Any],
) -> Asset | None:
    asset = await get_asset(db, user_id, asset_id)
    if asset is None:
        return None
    for field, value in updates.items():
        if value is not None:
            setattr(asset, field, value)
    await db.commit()
    await db.refresh(asset)
    logger.info("Asset updated: id=%s user=%s fields=%s", asset_id, user_id, list(updates.keys()))
    return asset


async def delete_asset(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> bool:
    from sqlalchemy import delete as sql_delete
    from app.models.cash_balance import CashBalance

    asset = await get_asset(db, user_id, asset_id)
    if asset is None:
        return False
    await db.execute(sql_delete(CashBalance).where(CashBalance.asset_id == asset_id))
    await db.delete(asset)
    await db.commit()
    logger.info("Asset deleted: id=%s user=%s", asset_id, user_id)
    return True
```

---

## Task 3: Add PATCH and DELETE endpoints

**Files:**
- Modify: `backend/app/api/assets.py`

- [ ] **Step 1: Update imports at the top of `backend/app/api/assets.py`**

The import for schemas needs `AssetUpdate`. Change the schemas import line from:

```python
from app.schemas.asset import AssetCreate, AssetResponse
```

to:

```python
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
```

Also add `update_asset` and `delete_asset` to the service import line. Change:

```python
from app.services import asset as asset_service
```

(stays the same — we call `asset_service.update_asset` and `asset_service.delete_asset`)

- [ ] **Step 2: Add the two new route handlers**

Append to the end of `backend/app/api/assets.py`:

```python
@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await asset_service.update_asset(
        db, current_user.id, asset_id, body.model_dump(exclude_none=True)
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return updated


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await asset_service.delete_asset(db, current_user.id, asset_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
```

- [ ] **Step 3: Run all new tests**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/backend
python -m pytest tests/test_assets.py -v
```

Expected: All tests pass including the 4 new ones.

---

## Task 4: Create `EditCashAccountDialog`

**Files:**
- Create: `frontend/components/portfolio/EditCashAccountDialog.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/portfolio/EditCashAccountDialog.tsx` with this content:

```tsx
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/lib/api";

const CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"];

interface CashAsset {
  id: string;
  symbol: string;
  currency: string;
  metadata_?: { account_number?: string };
}

interface Props {
  asset: CashAsset;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onEdited: () => void;
}

export function EditCashAccountDialog({ asset, open, onOpenChange, onEdited }: Props) {
  const [symbol, setSymbol] = useState(asset.symbol);
  const [currency, setCurrency] = useState(asset.currency);
  const [accountNumber, setAccountNumber] = useState(
    asset.metadata_?.account_number ?? ""
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setSymbol(asset.symbol);
      setCurrency(asset.currency);
      setAccountNumber(asset.metadata_?.account_number ?? "");
    }
  }, [open, asset]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.patch(`/api/v1/assets/${asset.id}`, {
        symbol: symbol.toUpperCase(),
        name: symbol.toUpperCase(),
        currency,
        metadata_: accountNumber ? { account_number: accountNumber } : {},
      });
      if (!res.ok) throw new Error("Failed to update account");
      toast.success("Account updated");
      onOpenChange(false);
      onEdited();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Account</DialogTitle>
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
              <Select value={currency} onValueChange={(v) => { if (v) setCurrency(v); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCIES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label>Account Number (optional)</Label>
            <Input
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              placeholder="xxx-x-xxxxx-x"
            />
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

---

## Task 5: Update `CashAccountsSection` with edit/delete UI

**Files:**
- Modify: `frontend/components/portfolio/CashAccountsSection.tsx`

- [ ] **Step 1: Add imports**

At the top of `frontend/components/portfolio/CashAccountsSection.tsx`, add these imports after the existing ones:

```tsx
import { Pencil, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { EditCashAccountDialog } from "./EditCashAccountDialog";
```

- [ ] **Step 2: Add state variables**

Inside `CashAccountsSection`, after the existing `updateOpen` state, add:

```tsx
const [editTarget, setEditTarget] = useState<CashAsset | null>(null);
const [editOpen, setEditOpen] = useState(false);
const [deleteTarget, setDeleteTarget] = useState<CashAsset | null>(null);
const [deleteOpen, setDeleteOpen] = useState(false);
const [deleteLoading, setDeleteLoading] = useState(false);
```

- [ ] **Step 3: Add delete handler**

After the `load` callback, add:

```tsx
async function handleDelete() {
  if (!deleteTarget) return;
  setDeleteLoading(true);
  try {
    const res = await api.delete(`/api/v1/assets/${deleteTarget.id}`);
    if (!res.ok) throw new Error("Failed to delete account");
    toast.success(`${deleteTarget.symbol} deleted`);
    setDeleteOpen(false);
    setDeleteTarget(null);
    load();
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Failed to delete account");
  } finally {
    setDeleteLoading(false);
  }
}
```

Also add `toast` to imports: `import { toast } from "sonner";`

- [ ] **Step 4: Update the card header to show edit/delete buttons**

In the JSX, replace the existing `<CardHeader>` block:

```tsx
<CardHeader className="pb-2 px-5 pt-5">
  <CardTitle className="text-base font-semibold text-foreground">
    {asset.symbol}
  </CardTitle>
  {asset.metadata_?.account_number && (
    <p className="text-xs text-muted-foreground">
      {asset.metadata_.account_number}
    </p>
  )}
</CardHeader>
```

with:

```tsx
<CardHeader className="pb-2 px-5 pt-5">
  <div className="flex items-start justify-between">
    <div>
      <CardTitle className="text-base font-semibold text-foreground">
        {asset.symbol}
      </CardTitle>
      {asset.metadata_?.account_number && (
        <p className="text-xs text-muted-foreground">
          {asset.metadata_.account_number}
        </p>
      )}
    </div>
    <div className="flex gap-1">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={() => {
          setEditTarget(asset);
          setEditOpen(true);
        }}
      >
        <Pencil className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 text-destructive hover:text-destructive"
        onClick={() => {
          setDeleteTarget(asset);
          setDeleteOpen(true);
        }}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </div>
  </div>
</CardHeader>
```

- [ ] **Step 5: Add EditCashAccountDialog and AlertDialog to JSX**

After the closing `</div>` of the accounts grid (and after the existing `UpdateCashBalanceDialog`), add:

```tsx
{editTarget && (
  <EditCashAccountDialog
    asset={editTarget}
    open={editOpen}
    onOpenChange={setEditOpen}
    onEdited={load}
  />
)}

<AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete {deleteTarget?.symbol}?</AlertDialogTitle>
      <AlertDialogDescription>
        This will permanently delete the account and all its balance history.
        This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel disabled={deleteLoading}>Cancel</AlertDialogCancel>
      <AlertDialogAction
        onClick={handleDelete}
        disabled={deleteLoading}
        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
      >
        {deleteLoading ? "Deleting…" : "Delete"}
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

- [ ] **Step 6: Check TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 7: Manual verification**

Start the dev stack and open the Portfolio page. Verify:
1. Each cash account card shows pencil + trash icons in the top-right
2. Clicking pencil opens "Edit Account" dialog pre-filled with current name, currency, account number
3. Saving edit reflects new values on the card
4. Clicking trash opens confirm dialog with account name in the title
5. Confirming delete removes the card and shows a toast
6. Cancelling delete does nothing

---

## Notes

- `api.patch` and `api.delete` must exist on the `api` client at `frontend/lib/api.ts`. If the client only has `get`/`post`, add `patch` and `delete` methods following the same pattern before starting Task 5.
- `AssetResponse` now includes `metadata_` — the backend returns it for all assets including non-cash types; this is harmless (defaults to `{}`).
