# Edit Asset Ticker/Name in EditHoldingDialog

**Date:** 2026-05-07  
**Status:** Approved

## Problem

A holding's ticker symbol can change (e.g., a company renames or relists). There is currently no UI to rename the ticker symbol or asset name.

## Data Model

- `Asset` table holds `symbol` and `name` — single source of truth.
- `Holding` and `Transaction` both reference `asset_id` → `Asset`.
- Updating `Asset.symbol` automatically reflects across all related holdings and transactions — no cascade needed.

## Backend

No backend changes required. `PATCH /api/v1/assets/{asset_id}` already accepts `{ symbol?, name? }` via `AssetUpdate` schema.

## Frontend Changes

### 1. `frontend/lib/services/portfolio.ts`

Add two functions:

**`fetchAsset(assetId: string)`** — calls `GET /api/v1/assets/{assetId}`, returns `{ id, symbol, name, asset_type, currency }`.

**`updateAsset(assetId: string, data: { symbol?: string; name?: string })`** — calls `PATCH /api/v1/assets/{assetId}`.

### 2. `frontend/components/portfolio/EditHoldingDialog.tsx`

- On dialog open: fetch asset via `fetchAsset(holding.asset_id)` to pre-fill `symbol` and `name`.
- Add an "Asset" section at the top of the form with two fields:
  - **Symbol** (pre-filled from fetched asset)
  - **Name** (pre-filled from fetched asset)
- Keep existing "Holding" fields below (Shares, Cost/Share, Currency, Platform).
- On submit: call `Promise.all([updateAsset(...), updateHolding(...)])` concurrently.
- Show single success toast. Call `onUpdated()` to refresh the holdings table.

### Form Layout

```
── Asset ──────────────────────────────
  Symbol          Name
  [AAPL       ]   [Apple Inc.       ]

── Holding ────────────────────────────
  Shares          Cost/Share
  Currency        Platform
                            [Save Changes]
```

## Error Handling

- If `fetchAsset` fails on open: show toast error, keep dialog open with empty symbol/name fields (user can still edit holding fields).
- If `updateAsset` or `updateHolding` fails on submit: show error toast, do not close dialog.

## Scope

- Only `symbol` and `name` are editable on the asset — not `asset_type` or `currency` (changing those could corrupt financial calculations).
- No changes to transaction UI — transactions reflect the updated ticker automatically via the asset join.
