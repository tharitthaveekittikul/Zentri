# Edit Asset Ticker/Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Symbol and Name fields to the existing `EditHoldingDialog` so users can rename a ticker and its display name, which automatically updates all related transactions.

**Architecture:** `Asset.symbol` and `Asset.name` are the single source of truth — both holdings and transactions reference `asset_id`, so one asset update reflects everywhere. The dialog fetches the current asset on open, then on submit calls `updateAsset` and `updateHolding` concurrently via `Promise.all`.

**Tech Stack:** Next.js (frontend), React, TypeScript, existing `api` client from `@/lib/api`, FastAPI backend (`PATCH /api/v1/assets/{asset_id}` already exists).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/lib/services/portfolio.ts` | Modify | Add `fetchAsset` and `updateAsset` functions |
| `frontend/components/portfolio/EditHoldingDialog.tsx` | Modify | Add Symbol/Name fields, fetch asset on open, submit both updates |

---

### Task 1: Add `fetchAsset` and `updateAsset` to portfolio service

**Files:**
- Modify: `frontend/lib/services/portfolio.ts`

- [ ] **Step 1: Add `AssetDetail` interface and two new functions**

Open `frontend/lib/services/portfolio.ts` and add after the existing `Transaction` interface (around line 31):

```typescript
export interface AssetDetail {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
}

export async function fetchAsset(assetId: string): Promise<AssetDetail> {
  const res = await api.get(`/api/v1/assets/${assetId}`);
  if (!res.ok) throw new Error("Failed to fetch asset");
  return res.json();
}

export async function updateAsset(
  assetId: string,
  data: { symbol?: string; name?: string },
): Promise<AssetDetail> {
  const res = await api.patch(`/api/v1/assets/${assetId}`, data);
  if (!res.ok) throw new Error("Failed to update asset");
  return res.json();
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to `portfolio.ts`.

---

### Task 2: Update `EditHoldingDialog` to include asset Symbol and Name fields

**Files:**
- Modify: `frontend/components/portfolio/EditHoldingDialog.tsx`

- [ ] **Step 1: Add new imports and state**

Replace the import line for `updateHolding` and add the new ones:

```typescript
import { updateHolding, fetchAsset, updateAsset, HoldingRow } from "@/lib/services/portfolio";
```

Add new state variables inside the component (after existing `useState` calls):

```typescript
const [symbol, setSymbol] = useState("");
const [assetName, setAssetName] = useState("");
const [assetLoading, setAssetLoading] = useState(false);
```

- [ ] **Step 2: Fetch asset when dialog opens**

Replace the existing `useEffect` block:

```typescript
useEffect(() => {
  if (holding && open) {
    setQuantity(holding.outstanding_shares);
    setCostPerShare(holding.cost_per_share);
    setCurrency(holding.currency);
    setPlatform(holding.platform ?? "");
    setSymbol(holding.symbol);
    setAssetName("");
    setAssetLoading(true);
    fetchAsset(holding.asset_id)
      .then((asset) => {
        setSymbol(asset.symbol);
        setAssetName(asset.name);
      })
      .catch(() => toast.error("Could not load asset details"))
      .finally(() => setAssetLoading(false));
  }
}, [holding, open]);
```

- [ ] **Step 3: Update `handleSubmit` to call both APIs concurrently**

Replace the existing `handleSubmit` function:

```typescript
async function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  if (!holding) return;
  setLoading(true);
  try {
    await Promise.all([
      updateAsset(holding.asset_id, { symbol, name: assetName }),
      updateHolding(holding.id, {
        quantity,
        avg_cost_price: costPerShare,
        currency,
        platform: platform || null,
      }),
    ]);
    toast.success(`${symbol} updated`);
    onOpenChange(false);
    onUpdated();
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Failed to update");
  } finally {
    setLoading(false);
  }
}
```

- [ ] **Step 4: Add Asset section to the form**

Inside the `<form>` tag, add the Asset section **before** the existing holdings fields:

```tsx
<form onSubmit={handleSubmit} className="space-y-3">
  {/* Asset section */}
  <div className="space-y-2">
    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Asset</p>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-1">
        <Label>Symbol</Label>
        <Input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          disabled={assetLoading}
          required
        />
      </div>
      <div className="space-y-1">
        <Label>Name</Label>
        <Input
          value={assetName}
          onChange={(e) => setAssetName(e.target.value)}
          disabled={assetLoading}
          placeholder={assetLoading ? "Loading…" : ""}
        />
      </div>
    </div>
  </div>

  {/* Holding section */}
  <div className="space-y-2">
    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Holding</p>
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
  </div>

  <Button type="submit" className="w-full" disabled={loading}>
    {loading ? "Saving…" : "Save Changes"}
  </Button>
</form>
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Manual smoke test**

1. Open the app and go to the Portfolio / Holdings page.
2. Click the Pencil icon on any holding row.
3. Verify the dialog shows **Symbol** and **Name** pre-filled (after brief loading).
4. Change the Symbol to a new value (e.g., add `.BK` suffix for Thai stocks).
5. Click Save Changes.
6. Verify the holdings table refreshes and shows the new symbol.
7. Navigate to Transactions for that asset — verify the updated symbol appears there too.
8. Re-open the dialog — verify Symbol and Name fields show the updated values.

---

## Error Cases to Verify Manually

| Scenario | Expected behaviour |
|----------|--------------------|
| Asset fetch fails on open | Toast "Could not load asset details"; fields show pre-filled symbol from `HoldingRow`, name empty; user can still save holding fields |
| Save fails (network error) | Toast error; dialog stays open |
| Symbol field left empty | Form validation prevents submit (`required`) |
