# Crypto Holdings Support

**Date:** 2026-05-07
**Status:** Approved

## Summary

Add the ability for users to add and track cryptocurrency holdings. The backend price-fetching infrastructure (`crypto` asset type, `fetch_crypto_prices` via CoinGecko, scheduler job) is already fully implemented. The missing piece is the frontend UX to set `coingecko_id` in `metadata_`, which the price fetcher requires to look up the correct coin.

## Architecture

Follows the existing `th_fund → proj_id` pattern:

1. A new backend endpoint proxies CoinGecko's search API.
2. Frontend calls it and shows a coin picker dropdown in both Add and Edit holding dialogs.
3. The selected `coingecko_id` is saved in `asset.metadata_`.
4. The existing `fetch_crypto_prices()` reads `metadata_.coingecko_id` and fetches prices — no changes needed.

## Backend

### New endpoint: `GET /api/v1/assets/search-coingecko`

- **File:** `backend/app/api/assets.py`
- **Query param:** `q: str` (coin name or symbol, e.g. `bitcoin` or `BTC`)
- **Auth:** `get_current_user` (existing dep)
- **Implementation:** call `https://api.coingecko.com/api/v3/search?query=<q>` via `httpx.AsyncClient` (already used in `price_feed.py`), return top 10 results
- **Response shape:**
  ```json
  [
    { "id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "thumb": "https://..." },
    ...
  ]
  ```
- No new service file — logic lives directly in the route handler (~20 lines).

## Frontend

### `addHolding` service function (`frontend/lib/services/portfolio.ts`)

`addHolding` currently does not accept `metadata_`. Add it as an optional field so `AddHoldingDialog` can pass `{ coingecko_id }` for crypto holdings. The backend `POST /api/v1/holdings` already accepts `metadata_` via the asset creation step.

### `AddHoldingDialog` (`frontend/components/portfolio/AddHoldingDialog.tsx`)

When `assetType === "crypto"`:

- Show a **CoinGecko ID** field below Symbol.
- On symbol input change (500 ms debounce), call `GET /api/v1/assets/search-coingecko?q=<symbol>`.
- Render a small dropdown list of matches showing `name (SYMBOL)` with a thumbnail.
- Selecting a match fills both the symbol field and `coingeckoId` state.
- On submit: pass `metadata_: { coingecko_id: coingeckoId }` to `addHolding`.
- If no match selected yet, require the user to pick one before submitting (form validation).

### `EditHoldingDialog` (`frontend/components/portfolio/EditHoldingDialog.tsx`)

Mirror the `th_fund → proj_id` pattern:

- On dialog open, read `asset.metadata_?.coingecko_id` and populate `coingeckoId` state.
- When `assetType === "crypto"`, show the same CoinGecko ID field with search + dropdown UX.
- On save: `assetUpdate.metadata_ = { coingecko_id: coingeckoId.trim() }`.

### New service helper (`frontend/lib/services/portfolio.ts`)

```ts
export interface CoinGeckoResult {
  id: string;
  symbol: string;
  name: string;
  thumb: string;
}

export async function searchCoinGecko(q: string): Promise<CoinGeckoResult[]> {
  const res = await api.get(`/api/v1/assets/search-coingecko?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return res.json();
}
```

## Data Flow

```
User types "BTC" in AddHoldingDialog (assetType=crypto)
  → 500ms debounce → searchCoinGecko("BTC")
  → GET /api/v1/assets/search-coingecko?q=BTC
  → backend calls CoinGecko /search
  → returns [{ id:"bitcoin", symbol:"BTC", name:"Bitcoin", thumb:"..." }, ...]
  → dropdown shown → user selects "Bitcoin (BTC)"
  → coingeckoId = "bitcoin", symbol = "BTC"
  → on submit: addHolding({ symbol:"BTC", asset_type:"crypto", metadata_:{ coingecko_id:"bitcoin" }, ... })
  → asset saved with metadata_.coingecko_id = "bitcoin"
  → next price job: fetch_crypto_prices reads coingecko_id → fetches USD price ✓
```

## Currency

Crypto prices are fetched in **USD** (CoinGecko `/simple/price` with `vs_currencies=usd`). Default currency for new crypto holdings should be `USD`.

## Error Handling

- CoinGecko search failure (network/rate limit): show a warning toast, allow manual coingecko_id entry as fallback.
- Asset saved without `coingecko_id`: price fetcher already logs a warning and skips — no crash.

## Out of Scope

- Multi-currency crypto pricing (THB, EUR) — not supported by existing `fetch_crypto_prices`.
- Historical OHLCV for crypto — CoinGecko free tier only returns spot price; current `fetch_crypto_prices` stores only `close`, which is fine.
- Crypto-specific display (24h change %) — existing `price_1d_change` field on `HoldingRow` will populate once two price rows exist.
