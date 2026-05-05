# Portfolio Page Redesign: Holdings Table + Cash Accounts

**Date:** 2026-05-05  
**Status:** Approved

## Overview

Redesign the portfolio page to:
1. Separate cash accounts from investment holdings (they are fundamentally different)
2. Make holdings rows editable via a pencil-icon dialog
3. Add sorting, pagination, platform filter, and page-size selector to the holdings table
4. Add a dedicated "Cash & Bank Accounts" section with simple balance cards

---

## 1. Page Layout

The portfolio page (`/app/(auth)/portfolio/page.tsx`) becomes two stacked sections on a single scrollable page.

```
[ Summary cards ]

Holdings                               [Add Holding] [Add Transaction]
┌───────────────────────────────────────────────────────────────┐
│ Platform: [All ▼]                            Rows: [10 ▼]    │
│───────────────────────────────────────────────────────────────│
│ Symbol ↕ | Shares ↕ | Cost ↕ | Value ↕ | P/L ↕ | Actions   │
│  AAPL      100        150      15,000    +12%     🖊 🗑       │
│  VOO        50        200      11,500     +8%     🖊 🗑       │
└───────────────────────────────────────────────────────────────┘
[< Prev]  Page 1 of 3  [Next >]

Cash & Bank Accounts                              [+ Add Account]
┌──────────────┐  ┌──────────────┐
│ SCB THB      │  │ IBKR USD     │
│ 500,000 THB  │  │  12,340 USD  │
│ Updated May 1│  │ Updated Apr30│
│  [Update]    │  │  [Update]    │
└──────────────┘  └──────────────┘
```

- Holdings table **filters out** rows where `asset_type === "cash"`.
- Cash section reads from `GET /assets` (filtered to `asset_type=cash`) + latest balance per asset from `GET /cash-balances/{asset_id}/latest`.

---

## 2. Holdings Table Enhancements

### Sorting
- Use TanStack Table `getSortedRowModel`.
- Clickable column headers toggle asc → desc → unsorted.
- Sort indicator (↑ / ↓) shown on active column.
- Sortable columns: Symbol, Outstanding Shares, Cost per Share, Total Cost, Current Price, Holding Value, Unrealized P/L.

### Pagination
- Use TanStack Table `getPaginationRowModel`.
- Page size options: 10 / 25 / 50 — selector bottom-right of table controls.
- Prev / Next buttons + "Page X of Y" label bottom-left.
- Changing page size resets to page 1.

### Platform Filter
- Dropdown above the table: "All Platforms" + unique platform values from current holdings data.
- Uses TanStack Table `getFilteredRowModel` with a column filter on the `platform` field.
- Changing the filter resets to page 1.

### Row Actions
- Add pencil icon (`Pencil` from lucide-react) alongside the existing trash icon.
- Pencil opens `EditHoldingDialog` for that row.

---

## 3. EditHoldingDialog (new component)

**File:** `frontend/components/portfolio/EditHoldingDialog.tsx`

Editable fields:
- Outstanding Shares (quantity)
- Cost per Share (avg_cost_price)
- Currency

Read-only display (not editable): Symbol, Asset Type.

On save → calls `PATCH /api/v1/portfolio/holdings/{id}` → refreshes holdings list.

---

## 4. Cash & Bank Accounts Section

### CashAccountsSection (new component)
**File:** `frontend/components/portfolio/CashAccountsSection.tsx`

- Fetches all user assets via `GET /api/v1/assets`, then filters client-side to `asset_type === "cash"` (the endpoint returns all assets; no server-side filter param exists).
- For each cash asset, fetches latest balance via `GET /api/v1/cash-balances/{asset_id}/latest`.
- Renders a card grid (responsive: 2 cols on md+, 1 col on mobile).
- "Add Account" button → opens `AddCashAccountDialog`.

### Card layout (per account):
- Account name (asset symbol, e.g., "SCB_THB")
- Balance (large number, formatted with currency)
- "Updated: [date]" subtitle
- "Update" button → opens `UpdateCashBalanceDialog`

### AddCashAccountDialog (new component)
**File:** `frontend/components/portfolio/AddCashAccountDialog.tsx`

Fields:
- Account Name / Symbol (e.g., `SCB_THB`) — uppercased
- Currency (e.g., `THB`)
- Initial Balance (number)

On save:
1. `POST /api/v1/assets` with `{ symbol, asset_type: "cash", name: symbol, currency }`
2. `POST /api/v1/cash-balances` with `{ asset_id, balance, snapshot_date: today }`

### UpdateCashBalanceDialog (new component)
**File:** `frontend/components/portfolio/UpdateCashBalanceDialog.tsx`

Fields:
- Balance (number, pre-filled with current balance)
- Date (defaults to today)

On save → `POST /api/v1/cash-balances` with new snapshot. The `GET /latest` endpoint always returns the most recent snapshot, so this effectively "updates" the balance.

---

## 5. New Backend Endpoint

### PATCH /api/v1/portfolio/holdings/{holding_id}

**File:** `backend/app/api/portfolio.py`

Request body (`HoldingUpdate` schema):
```python
class HoldingUpdate(BaseModel):
    quantity: float | None = None
    avg_cost_price: float | None = None
    currency: str | None = None
```

Behavior:
- Fetches holding by ID + user_id (ownership check).
- Applies only provided fields (partial update).
- Returns updated `HoldingRow`.

**Service:** `backend/app/services/portfolio.py` — add `update_holding(db, holding, data)`.

**Schema:** `backend/app/schemas/holding.py` — add `HoldingUpdate`.

---

## 6. Frontend Service Updates

**File:** `frontend/lib/services/portfolio.ts`

Add:
```ts
updateHolding(id: string, data: { quantity?: number; avg_cost_price?: number; currency?: string }): Promise<HoldingRow>
```

Calls `PATCH /api/v1/portfolio/holdings/{id}`. Uses backend field names (`quantity`, `avg_cost_price`) — the frontend display names (`outstanding_shares`, `cost_per_share`) are only for the `HoldingRow` response type.

---

## 7. Files to Create / Modify

### New files
| File | Purpose |
|------|---------|
| `frontend/components/portfolio/EditHoldingDialog.tsx` | Edit holding dialog |
| `frontend/components/portfolio/CashAccountsSection.tsx` | Cash cards section |
| `frontend/components/portfolio/AddCashAccountDialog.tsx` | Add cash account |
| `frontend/components/portfolio/UpdateCashBalanceDialog.tsx` | Update cash balance |

### Modified files
| File | Change |
|------|--------|
| `frontend/components/portfolio/HoldingsTable.tsx` | Add sorting, pagination, platform filter, page-size selector, pencil icon, filter out cash |
| `frontend/app/(auth)/portfolio/page.tsx` | Add CashAccountsSection below HoldingsTable |
| `frontend/lib/services/portfolio.ts` | Add `updateHolding()` |
| `backend/app/api/portfolio.py` | Add `PATCH /holdings/{id}` endpoint |
| `backend/app/services/portfolio.py` | Add `update_holding()` service function |
| `backend/app/schemas/holding.py` | Add `HoldingUpdate` schema |

---

## 8. Out of Scope

- Transaction history for cash (user confirmed: just one current balance number)
- Editing a cash account's name/symbol after creation
- Deleting cash accounts (can add later)
- Price feed for cash assets (not applicable)
