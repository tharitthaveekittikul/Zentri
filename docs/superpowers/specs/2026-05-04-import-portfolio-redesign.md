# Import Simplification & Portfolio Redesign

**Date:** 2026-05-04  
**Status:** Approved

---

## Overview

Three coordinated changes:
1. Replace the over-engineered platform/template import wizard with a simple canonical-check → LLM-fallback pipeline.
2. Redesign the portfolio table with computed columns and correct currency display.
3. Remove the Broker Platforms settings section and clean up deprecated endpoints.

---

## 1. Import Pipeline

### New Flow

```
User uploads CSV or JSON
        ↓
Backend: detect file format, parse headers
        ↓
All headers ⊆ CANONICAL_FIELDS?
   YES → parse all rows directly (zero LLM cost)
   NO  → send headers + first 5 sample rows to LLM
         LLM returns field mapping
         apply mapping to all rows
        ↓
Return canonical rows to frontend
        ↓
Frontend: Review Preview — editable table of all rows
User corrects any LLM mistakes inline
        ↓
User clicks Confirm
POST /import/confirm → save transactions + upsert holdings
```

### CANONICAL_FIELDS (the contract)

```
trade_date, type, symbol, unit, price, currency,
exchange, gross_amount, fee, gross_thb, fee_thb,
exchange_rate, asset_type, platform, notes
```

Files whose headers are a subset of these fields import directly with no LLM call. Any other headers trigger LLM translation.

### LLM Translation

- Input: file headers + up to 5 sample rows
- Output: a field mapping `{source_col → canonical_field}` + derived/default values
- Applied to all rows on the backend
- **Not cached** — translation is one-time per upload (use case is one-time bootstrapping)

### API Changes

**New:**
- `POST /import/upload` — accepts file, returns `{rows: CanonicalRow[], method: "direct" | "llm_translated"}`
- `POST /import/confirm` — accepts edited canonical rows, saves transactions + upserts holdings

**Deleted:**
- `POST /import/analyze`
- `POST /import/generate-template`
- `POST /import/save-template`
- `DELETE /import/template/{platform_id}`
- `POST /portfolio/import/preview` (old CSV endpoint)
- `POST /portfolio/import/confirm` (old CSV endpoint)
- All `/platforms/*` endpoints

### Review Preview UI

- Shows all translated rows in an editable table
- Each cell is editable inline
- Columns match CANONICAL_FIELDS (hide null-only columns to reduce clutter)
- Validation: required fields (trade_date, type, symbol, unit) highlighted if blank
- "Confirm Import" button triggers `POST /import/confirm`

---

## 2. Portfolio Page

### Table Columns

| Column | Calculation | No Price |
|---|---|---|
| Symbol / Fund Code | `asset.symbol` | always shown |
| Outstanding Shares | `holding.quantity` | always shown |
| Cost per Share | `holding.avg_cost_price` | always shown |
| Total Cost | `quantity × avg_cost_price` | always shown |
| Current Price | price feed (future) | `—` |
| Price & 1D Change | price feed (future) | `—` |
| Holding Value | `quantity × current_price` | `—` |
| Unrealized P/L | `holding_value − total_cost` | `—` |

All monetary values rendered in `user.currency_primary` (default THB). No hardcoded `$`.

Backend computes all columns and returns them in the holdings list response. Frontend renders only.

### Add Holding Form

For entering existing/compressed positions (e.g. bootstrapping before using Zentri).

**User inputs:**
- Symbol (text)
- Asset Type (dropdown: us_stock / thai_stock / th_fund / etf / crypto / gold / cash)
- Date (user picks — typically first purchase date)
- Outstanding Shares (quantity)
- Cost per Share (avg cost price)
- Currency (default: user's primary currency)
- Platform (optional text)
- Notes (optional text)

**Auto-calculated (read-only):**
- Total Cost = Outstanding Shares × Cost per Share

Creates a `Holding` record directly. No transaction history generated.

### Add Transaction Form

For recording individual trade events that update the portfolio incrementally.

**Fields:**
- Trade Date
- Type (BUY / SELL / DIVIDEND / REWARD / FEE / TRANSFER)
- Symbol
- Units
- Price per Unit
- Fee
- Currency
- Platform (optional text)
- Notes (optional)

Creates a `Transaction` record + upserts the corresponding `Holding`.

### Removed

- "Import CSV" button on portfolio page (import is centralized at /import page)

---

## 3. Settings Page

### Broker Platforms Section — Removed

The "Broker Platforms" section is deleted from the Settings UI. No replacement.

### Display Currency Save Button — Bug Fix

Current behavior: API call succeeds but button gives no visual feedback.

Required fixes:
- Hover state (cursor pointer, color change)
- Active/click state (visual press feedback)
- Success toast: "Display settings saved"
- Error toast: "Failed to save settings" if API returns error

---

## 4. Database Migrations

### Tables to Drop

- `platforms`
- `import_templates`
- `import_profiles` (if exists)

### Table Alterations

`transactions` table:
- Drop column `platform_id` (UUID, FK to platforms)
- Add column `platform` (VARCHAR(100), nullable)

### Models to Delete

- `backend/app/models/platform.py`
- `backend/app/models/import_template.py`
- `backend/app/models/import_profile.py`

### Services/Schemas to Delete

- `backend/app/services/platform.py`
- `backend/app/services/csv_import.py`
- `backend/app/schemas/platform.py`
- `backend/app/schemas/csv_import.py`
- `backend/app/schemas/import_template.py`
- `backend/app/api/platforms.py`

---

## 5. What Does NOT Change

- `User.currency_primary` / `User.currency_secondary` — already correct in DB and API
- `GET /settings/display` and `PATCH /settings/display` — kept as-is
- `Holding` model columns — `quantity`, `avg_cost_price`, `currency` are sufficient; computed fields returned by API, not stored
- LLM gateway and LLM settings — unchanged
- Price fetch pipeline — out of scope; columns show `—` until implemented
