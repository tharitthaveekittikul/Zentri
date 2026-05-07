# Crypto Holdings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to add and track crypto holdings by storing a `coingecko_id` in asset metadata, using a new CoinGecko search endpoint for discovery.

**Architecture:** Backend already has `fetch_crypto_prices()` and the scheduler — the only backend gap is (1) a CoinGecko search proxy endpoint and (2) threading `metadata_` through the `add_holding` path. Frontend needs a coin-search dropdown in both Add and Edit holding dialogs, mirroring the existing `th_fund → proj_id` pattern.

**Tech Stack:** FastAPI + httpx (backend), Next.js + React (frontend), CoinGecko public API (no key required)

---

## File Map

| File | Change |
|------|--------|
| `backend/app/schemas/holding.py` | Add `metadata_` field to `HoldingCreate` |
| `backend/app/services/portfolio.py` | Accept + use `metadata_` in `add_holding` |
| `backend/app/api/portfolio.py` | Pass `body.metadata_` to service |
| `backend/app/schemas/asset.py` | Add `CoinGeckoMatch` response model |
| `backend/app/api/assets.py` | Add `GET /search-coingecko` endpoint |
| `backend/tests/test_assets.py` | Tests for the new endpoint |
| `frontend/lib/services/portfolio.ts` | Add `CoinGeckoResult`, `searchCoinGecko()`, update `addHolding` |
| `frontend/components/portfolio/AddHoldingDialog.tsx` | Crypto coingecko_id UI |
| `frontend/components/portfolio/EditHoldingDialog.tsx` | Crypto coingecko_id UI |

---

## Task 1: Thread `metadata_` through the add-holding backend path

**Files:**
- Modify: `backend/app/schemas/holding.py`
- Modify: `backend/app/services/portfolio.py`
- Modify: `backend/app/api/portfolio.py`
- Test: `backend/tests/test_portfolio.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_portfolio.py`:

```python
@pytest.mark.asyncio
async def test_add_holding_persists_metadata(auth_client):
    response = await auth_client.post("/api/v1/portfolio/holdings", json={
        "symbol": "BTC",
        "asset_type": "crypto",
        "quantity": "0.5",
        "avg_cost_price": "50000",
        "currency": "USD",
        "metadata_": {"coingecko_id": "bitcoin"},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"

    # Verify asset was stored with coingecko_id
    asset_id = data["asset_id"]
    asset_res = await auth_client.get(f"/api/v1/assets/{asset_id}")
    assert asset_res.status_code == 200
    assert asset_res.json()["metadata_"]["coingecko_id"] == "bitcoin"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_portfolio.py::test_add_holding_persists_metadata -v
```

Expected: FAIL — `metadata_` is not accepted (field ignored or 422 error)

- [ ] **Step 3: Update `HoldingCreate` schema**

Open `backend/app/schemas/holding.py`. Locate the `HoldingCreate` class and add the `metadata_` field:

```python
class HoldingCreate(BaseModel):
    symbol: str
    asset_type: str
    purchased_at: date | None = None
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str
    platform: str | None = None
    metadata_: dict | None = None          # ← add this line
```

- [ ] **Step 4: Update `portfolio_service.add_holding` to accept and use `metadata_`**

Open `backend/app/services/portfolio.py`. Change the `add_holding` signature and the asset creation block:

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
    metadata_: dict | None = None,         # ← add this parameter
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
            metadata_=metadata_ or {},     # ← was {}, now uses param
        )
        db.add(asset)
```

Leave the rest of the function unchanged.

- [ ] **Step 5: Update `portfolio` API endpoint to pass `metadata_`**

Open `backend/app/api/portfolio.py`. Find the `add_holding` route and add `body.metadata_`:

```python
holding, asset = await portfolio_service.add_holding(
    db, current_user.id, body.symbol, body.asset_type,
    body.quantity, body.avg_cost_price, body.currency,
    body.purchased_at, body.platform,
    body.metadata_,                         # ← add this line
)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_portfolio.py::test_add_holding_persists_metadata -v
```

Expected: PASS

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest tests/test_portfolio.py -v
```

Expected: all existing tests still PASS

---

## Task 2: Backend — CoinGecko search endpoint

**Files:**
- Modify: `backend/app/schemas/asset.py`
- Modify: `backend/app/api/assets.py`
- Test: `backend/tests/test_assets.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_assets.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_search_coingecko_returns_coins(auth_client):
    mock_data = {
        "coins": [
            {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "thumb": "https://example.com/btc.png"},
            {"id": "bitcoin-cash", "symbol": "bch", "name": "Bitcoin Cash", "thumb": "https://example.com/bch.png"},
        ]
    }
    mock_response = MagicMock()
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("app.api.assets.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        res = await auth_client.get("/api/v1/assets/search-coingecko?q=bitcoin")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["id"] == "bitcoin"
    assert data[0]["symbol"] == "BTC"
    assert data[0]["name"] == "Bitcoin"
    assert "thumb" in data[0]


@pytest.mark.asyncio
async def test_search_coingecko_requires_auth(client):
    res = await client.get("/api/v1/assets/search-coingecko?q=bitcoin")
    assert res.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_assets.py::test_search_coingecko_returns_coins tests/test_assets.py::test_search_coingecko_requires_auth -v
```

Expected: FAIL — endpoint does not exist (404)

- [ ] **Step 3: Add `CoinGeckoMatch` schema**

Open `backend/app/schemas/asset.py`. Add at the bottom:

```python
class CoinGeckoMatch(BaseModel):
    id: str
    symbol: str
    name: str
    thumb: str
```

Make sure `BaseModel` is already imported from `pydantic` (it will be, as the other schemas use it).

- [ ] **Step 4: Add the endpoint to `assets.py`**

Open `backend/app/api/assets.py`. Add `import httpx` at the top (after existing imports). Then add this route — place it **before** any `/{asset_id}` routes to avoid path conflicts:

```python
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate, CoinGeckoMatch

@router.get("/search-coingecko", response_model=list[CoinGeckoMatch])
async def search_coingecko(
    q: str,
    _: User = Depends(get_current_user),
):
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.coingecko.com/api/v3/search",
            params={"query": q},
        )
        resp.raise_for_status()
        data = resp.json()
    coins = data.get("coins", [])[:10]
    return [
        CoinGeckoMatch(
            id=c["id"],
            symbol=c["symbol"].upper(),
            name=c["name"],
            thumb=c.get("thumb", ""),
        )
        for c in coins
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_assets.py::test_search_coingecko_returns_coins tests/test_assets.py::test_search_coingecko_requires_auth -v
```

Expected: PASS

- [ ] **Step 6: Run full assets test suite**

```bash
cd backend && python -m pytest tests/test_assets.py -v
```

Expected: all tests PASS

---

## Task 3: Frontend — service helpers

**Files:**
- Modify: `frontend/lib/services/portfolio.ts`

- [ ] **Step 1: Add `CoinGeckoResult` type and `searchCoinGecko()` function**

Open `frontend/lib/services/portfolio.ts`. Add after the existing imports and before the first `export` function:

```typescript
export interface CoinGeckoResult {
  id: string;
  symbol: string;
  name: string;
  thumb: string;
}

export async function searchCoinGecko(q: string): Promise<CoinGeckoResult[]> {
  if (!q || q.length < 2) return [];
  const res = await api.get(`/api/v1/assets/search-coingecko?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}
```

- [ ] **Step 2: Update `addHolding` to accept `metadata_`**

Find the existing `addHolding` function:

```typescript
export async function addHolding(body: {
  symbol: string;
  asset_type: string;
  purchased_at: string | null;
  quantity: string;
  avg_cost_price: string;
  currency: string;
}): Promise<HoldingRow> {
```

Replace it with:

```typescript
export async function addHolding(body: {
  symbol: string;
  asset_type: string;
  purchased_at: string | null;
  quantity: string;
  avg_cost_price: string;
  currency: string;
  metadata_?: Record<string, unknown>;
}): Promise<HoldingRow> {
```

The function body (`api.post(...)`) stays unchanged — the extra field in `body` is already forwarded.

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

---

## Task 4: Frontend — `AddHoldingDialog` crypto UI

**Files:**
- Modify: `frontend/components/portfolio/AddHoldingDialog.tsx`

- [ ] **Step 1: Add imports and state**

Open `frontend/components/portfolio/AddHoldingDialog.tsx`. 

Update the import from `portfolio` to include the new helpers:

```typescript
import { addHolding, searchCoinGecko, CoinGeckoResult } from "@/lib/services/portfolio";
```

Add two new state variables inside the component (after existing `useState` calls):

```typescript
const [coingeckoId, setCoingeckoId] = useState("");
const [coinResults, setCoinResults] = useState<CoinGeckoResult[]>([]);
```

- [ ] **Step 2: Auto-set currency to USD when switching to crypto**

Find the Asset Type `<Select>` `onValueChange` handler:

```tsx
onValueChange={(v) => { if (v !== null) setAssetType(v); }}
```

Replace with:

```tsx
onValueChange={(v) => {
  if (v !== null) {
    setAssetType(v);
    if (v === "crypto") setCurrency("USD");
    setCoingeckoId("");
    setCoinResults([]);
  }
}}
```

- [ ] **Step 3: Add the search-on-type effect**

Add this `useEffect` inside the component (after the existing state declarations). It debounces the search by 500 ms whenever the symbol changes and the asset type is `crypto`:

```typescript
useEffect(() => {
  if (assetType !== "crypto" || symbol.length < 2) {
    setCoinResults([]);
    return;
  }
  const timer = setTimeout(() => {
    searchCoinGecko(symbol).then(setCoinResults).catch(() => {});
  }, 500);
  return () => clearTimeout(timer);
}, [symbol, assetType]);
```

Also add `useEffect` to the React import at the top if it isn't already there:

```typescript
import { useMemo, useState, useEffect } from "react";
```

- [ ] **Step 4: Pass `metadata_` on submit and reset on close**

Find `handleSubmit`. Replace the `addHolding(...)` call with:

```typescript
await addHolding({
  symbol,
  asset_type: assetType,
  purchased_at: purchasedAt || null,
  quantity,
  avg_cost_price: avgCost,
  currency,
  ...(assetType === "crypto" && coingeckoId
    ? { metadata_: { coingecko_id: coingeckoId } }
    : {}),
});
```

Find the reset block after `toast.success(...)` and add:

```typescript
setCoingeckoId("");
setCoinResults([]);
```

- [ ] **Step 5: Add the crypto-only UI block in the form**

In the JSX, find the Symbol input block:

```tsx
<div className="space-y-1">
  <Label>Symbol</Label>
  <Input
    value={symbol}
    onChange={(e) => setSymbol(e.target.value.toUpperCase())}
    placeholder="AAPL"
    required
  />
</div>
```

Add the CoinGecko picker immediately after the closing `</div>` of the grid block (after both Symbol and Asset Type inputs), but still inside `<form>`:

```tsx
{assetType === "crypto" && (
  <div className="space-y-1 relative">
    <Label>CoinGecko ID</Label>
    <Input
      value={coingeckoId}
      onChange={(e) => { setCoingeckoId(e.target.value); setCoinResults([]); }}
      placeholder="e.g. bitcoin"
      required
    />
    {coinResults.length > 0 && (
      <div className="absolute z-10 w-full bg-background border rounded shadow-md top-full mt-1">
        {coinResults.map((coin) => (
          <button
            key={coin.id}
            type="button"
            className="w-full text-left px-3 py-2 hover:bg-muted text-sm flex items-center gap-2"
            onClick={() => {
              setSymbol(coin.symbol);
              setCoingeckoId(coin.id);
              setCoinResults([]);
            }}
          >
            {coin.thumb && <img src={coin.thumb} alt="" className="w-4 h-4 shrink-0" />}
            {coin.name} <span className="text-muted-foreground">({coin.symbol})</span>
          </button>
        ))}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 7: Manual smoke test**

Start the dev server (`npm run dev` in `frontend/`). Open the portfolio page. Click **Add Holding**, select `crypto` as the type, type `BTC`. Verify:
- A dropdown appears with "Bitcoin (BTC)" and other matches
- Clicking "Bitcoin (BTC)" fills in symbol = `BTC` and CoinGecko ID = `bitcoin`
- Submitting the form succeeds and the holding appears in the table

---

## Task 5: Frontend — `EditHoldingDialog` crypto UI

**Files:**
- Modify: `frontend/components/portfolio/EditHoldingDialog.tsx`

- [ ] **Step 1: Add imports and state**

Open `frontend/components/portfolio/EditHoldingDialog.tsx`.

Update the `portfolio` import to include the new helpers:

```typescript
import {
  updateHolding, fetchAsset, updateAsset, lookupThFund,
  searchCoinGecko, CoinGeckoResult,
  ThFundMatch, HoldingRow,
} from "@/lib/services/portfolio";
```

Add state variables inside the component (after existing `useState` calls):

```typescript
const [coingeckoId, setCoingeckoId] = useState("");
const [coinResults, setCoinResults] = useState<CoinGeckoResult[]>([]);
```

- [ ] **Step 2: Load `coingecko_id` from metadata on open**

Find the `useEffect` that loads asset details on open. It already handles `th_fund` — add the `crypto` case right after:

```typescript
fetchAsset(holding.asset_id)
  .then((asset) => {
    if (cancelled) return;
    const fetchedSymbol = asset.symbol;
    const fetchedProjId = (asset.metadata_?.proj_id as string) ?? "";
    const fetchedCoinId = (asset.metadata_?.coingecko_id as string) ?? "";  // ← add
    setSymbol(fetchedSymbol);
    setAssetName(asset.name);
    setAssetType(asset.asset_type);
    setProjId(fetchedProjId);
    setCoingeckoId(fetchedCoinId);                                           // ← add
    // existing th_fund auto-lookup block stays unchanged
    ...
  })
```

Also reset `coingeckoId` and `coinResults` at the top of the `useEffect`, alongside the existing resets:

```typescript
setCoingeckoId("");
setCoinResults([]);
```

- [ ] **Step 3: Add search-on-type effect**

Add inside the component:

```typescript
useEffect(() => {
  if (assetType !== "crypto" || symbol.length < 2) {
    setCoinResults([]);
    return;
  }
  const timer = setTimeout(() => {
    searchCoinGecko(symbol).then(setCoinResults).catch(() => {});
  }, 500);
  return () => clearTimeout(timer);
}, [symbol, assetType]);
```

- [ ] **Step 4: Save `coingecko_id` in metadata on submit**

Find `handleSubmit`. The existing code already handles `th_fund`:

```typescript
const assetUpdate: Parameters<typeof updateAsset>[1] = { symbol, name: assetName, asset_type: assetType };
if (assetType === "th_fund") {
  assetUpdate.metadata_ = { proj_id: projId.trim() };
}
```

Add the `crypto` case right after:

```typescript
if (assetType === "th_fund") {
  assetUpdate.metadata_ = { proj_id: projId.trim() };
}
if (assetType === "crypto") {                                  // ← add
  assetUpdate.metadata_ = { coingecko_id: coingeckoId.trim() };
}
```

- [ ] **Step 5: Add the crypto UI block in the form JSX**

Find the existing `th_fund` block in the JSX. It looks like:

```tsx
{assetType === "th_fund" && (
  ...proj_id UI...
)}
```

Add this immediately after it:

```tsx
{assetType === "crypto" && (
  <div className="space-y-1 relative">
    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">CoinGecko ID</p>
    <Input
      value={coingeckoId}
      onChange={(e) => { setCoingeckoId(e.target.value); setCoinResults([]); }}
      placeholder="e.g. bitcoin"
    />
    {coinResults.length > 0 && (
      <div className="absolute z-10 w-full bg-background border rounded shadow-md top-full mt-1">
        {coinResults.map((coin) => (
          <button
            key={coin.id}
            type="button"
            className="w-full text-left px-3 py-2 hover:bg-muted text-sm flex items-center gap-2"
            onClick={() => {
              setSymbol(coin.symbol);
              setCoingeckoId(coin.id);
              setCoinResults([]);
            }}
          >
            {coin.thumb && <img src={coin.thumb} alt="" className="w-4 h-4 shrink-0" />}
            {coin.name} <span className="text-muted-foreground">({coin.symbol})</span>
          </button>
        ))}
      </div>
    )}
  </div>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors

- [ ] **Step 7: Manual smoke test**

Open the portfolio page. Find an existing holding with `asset_type = crypto` (or edit any holding and change its type to `crypto`). Verify:
- The CoinGecko ID field appears pre-filled if the holding already had `coingecko_id` in metadata
- Typing a new symbol triggers the search dropdown
- Saving updates the metadata correctly (verify via browser devtools network tab — `PATCH /api/v1/assets/<id>` should include `metadata_: { coingecko_id: "..." }`)
- Run `price_fetch_crypto` manually from the pipeline page to confirm the price is fetched for the new coin

---

## Final Verification

- [ ] Run the full backend test suite: `cd backend && python -m pytest -v`
- [ ] Trigger `price_fetch_crypto` from the pipeline page and confirm the price fetcher picks up the `coingecko_id` and logs a successful price upsert
