# Cash & Bank Accounts — Edit & Delete

**Date:** 2026-05-06  
**Status:** Approved

## Overview

Add edit and delete to existing Cash & Bank Account cards. Each card gets pencil + trash icon buttons in the top-right corner of the `CardHeader`. Edit opens a pre-filled dialog. Delete shows an `AlertDialog` confirm before deleting.

## Backend

### 1. `app/schemas/asset.py`

- Add `AssetUpdate` schema: all fields optional (`symbol`, `name`, `currency`, `metadata_`)
- Add `metadata_` to `AssetResponse` so the frontend can pre-fill the account number field

### 2. `app/services/asset.py`

- Add `update_asset(db, user_id, asset_id, **fields) -> Asset | None`  
  Fetches asset (user-scoped), applies non-None field updates, commits, returns updated asset.
- Add `delete_asset(db, user_id, asset_id) -> bool`  
  Deletes `CashBalance` rows for this asset first (FK has no cascade), then deletes the asset. Returns `False` if not found.

### 3. `app/api/assets.py`

- `PATCH /api/v1/assets/{asset_id}` — calls `update_asset`, returns `AssetResponse` (404 if not found)
- `DELETE /api/v1/assets/{asset_id}` — calls `delete_asset`, returns `204 No Content` (404 if not found)

## Frontend

### 1. `EditCashAccountDialog.tsx` (new component)

Same fields as `AddCashAccountDialog` minus the balance field:
- Account Name (symbol)
- Currency (select)
- Account Number (optional)

Props: `{ asset: CashAsset; open: boolean; onOpenChange: (v: boolean) => void; onEdited: () => void }`

On submit: `PATCH /api/v1/assets/{asset.id}` with `{ symbol, name: symbol, currency, metadata_: { account_number } }`.

### 2. `CashAccountsSection.tsx`

- Add state: `editTarget: CashAsset | null`, `editOpen: boolean`, `deleteTarget: CashAsset | null`, `deleteOpen: boolean`, `deleteLoading: boolean`
- In each card's `CardHeader`: add a `flex justify-between` wrapper — left side has symbol + account number, right side has pencil button + trash button (both `size="icon"` `variant="ghost"`)
- Add `EditCashAccountDialog` (same controlled pattern as `UpdateCashBalanceDialog`)
- Add `AlertDialog` for delete confirm — on confirm calls `DELETE /api/v1/assets/{deleteTarget.id}`, then `load()`

## Data flow

```
User clicks pencil → editTarget set → EditCashAccountDialog opens (pre-filled)
User submits edit → PATCH /api/v1/assets/{id} → onEdited() → load() reloads cards

User clicks trash → deleteTarget set → AlertDialog opens
User confirms → DELETE /api/v1/assets/{id} → load() reloads cards
```

## Constraints

- `CashBalance` FK to `assets.id` has no `ON DELETE CASCADE` — service must delete balances manually before deleting the asset
- `AssetResponse` currently omits `metadata_` — must be added for edit pre-fill to work
- Delete is permanent; toast confirmation shown after success
