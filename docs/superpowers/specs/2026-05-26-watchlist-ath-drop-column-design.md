# Watchlist ATH Drop Column & Alert

**Date:** 2026-05-26
**Status:** Approved

## Overview

Add an "ATH Drop" column to the watchlist table showing how far each asset has fallen from its all-time high (within a rolling 365-day window from stored price history). Per-item alert threshold lets users receive a Telegram notification when the drop exceeds their target (e.g. ≥ 20% = buy zone).

## ATH Definition

Consistent with `discover_top_down.py`:
- ATH = `max(Price.close)` over the last 365 days from the `prices` table
- `ath_drop_pct = (ath - current_price) / ath * 100`
- No yfinance dependency — uses existing stored price data

---

## Section 1: Data Layer

### Migration (`047_add_ath_alert_to_watchlist.py`)

Add to `watchlist_items`:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `ath_alert_threshold` | `Numeric(5,2)` | yes | e.g. `20.00` → alert when drop ≥ 20% |
| `ath_alerted_at` | `DateTime(timezone=True)` | yes | set when ATH alert fires; cleared on rearm |

---

## Section 2: Backend API

### `_item_to_out` (in `app/api/watchlist.py`)

Add after current price lookup:
```python
ATH_WINDOW_DAYS = 365
since = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
ath = (await db.execute(
    select(func.max(Price.close))
    .where(Price.asset_id == item.asset_id, Price.timestamp >= since)
)).scalar()
ath_drop_pct = None
if ath and current_price:
    ath_drop_pct = float((Decimal(str(ath)) - Decimal(str(current_price))) / Decimal(str(ath)) * 100)
```

### Schema changes (`app/schemas/watchlist.py`)

**`WatchlistItemOut`** — add fields:
- `ath_drop_pct: float | None`
- `ath_alert_threshold: Decimal | None`
- `ath_alerted_at: datetime | None`

**`WatchlistItemUpdate`** — add field:
- `ath_alert_threshold: Decimal | None`

### `/rearm` endpoint

Also reset `item.ath_alerted_at = None` so ATH alert fires again after rearm.

### `WatchlistItem` DB model

Add `ath_alert_threshold` and `ath_alerted_at` mapped columns.

---

## Section 3: Alert Service

### `app/services/watchlist_alert.py`

Add a second check after the existing target-price alert loop:

1. Query: items where `ath_alert_threshold IS NOT NULL` AND `ath_alerted_at IS NULL` AND user has Telegram configured
2. For each item: compute `ath_drop_pct` live (same formula)
3. If `ath_drop_pct >= ath_alert_threshold`: send Telegram, set `item.ath_alerted_at = now()`

**Telegram message format:**
```
📉 ATH Drop Alert — {symbol}
{asset.name}

Dropped -{ath_drop_pct:.1f}% from ATH (your threshold: {ath_alert_threshold}%)
Current price: {current_price:.4f} {currency}

Open Zentri to review.
```

---

## Section 4: Frontend

### Table column

Add "ATH Drop" column after "% From Target" in `WatchlistRow`:
- Shows `-X.X%` or `—` if no price history
- Color coding:
  - `< 10%` drop → `text-muted-foreground`
  - `10–20%` drop → `text-yellow-600 dark:text-yellow-400`
  - `> 20%` drop → `text-red-500`
- If `ath_alerted_at` is set → show a small `Bell` icon next to the value (alert already fired)
- Column header: `<TableHead className="hidden md:table-cell text-right">ATH Drop</TableHead>`

### Per-item threshold — Edit dialog

Add a pencil (`Pencil`) icon button to the Actions cell that opens an `EditItemDialog`:
- **Target price** input (pre-filled with `item.target_price`)
- **ATH alert threshold** input: "Alert when ATH drop ≥ X% (leave blank to disable)"
- Save calls `updateWatchlistItem(id, { target_price, ath_alert_threshold })`

### Type changes (`lib/services/watchlist.ts`)

Add to `WatchlistItem` interface:
```ts
ath_drop_pct: number | null;
ath_alert_threshold: string | null;
ath_alerted_at: string | null;
```

Add to `updateWatchlistItem` patch type:
```ts
ath_alert_threshold?: string | null;
```

---

## Implementation Order

1. Migration (`047_add_ath_alert_to_watchlist.py`)
2. `WatchlistItem` model — add 2 columns
3. `WatchlistItemOut` schema — add 3 fields; `WatchlistItemUpdate` — add 1 field
4. `_item_to_out` — compute `ath_drop_pct`, populate new schema fields
5. `/rearm` endpoint — reset `ath_alerted_at`
6. Alert service — add ATH drop alert loop
7. Frontend: type update → table column → edit dialog

## Out of Scope

- Sorting/filtering by ATH drop (future)
- ATH sourced from yfinance (current DB-only approach is consistent with Analysis page)
- Push notifications beyond Telegram
