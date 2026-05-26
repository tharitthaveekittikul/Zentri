# Watchlist Scan: AI Price Auto-Fill Design

**Date:** 2026-05-26
**Status:** Approved

## Problem

After running a watchlist scan, the Target, % to Target, and AI Price columns all show `—`. The cause is two-fold:

1. The `watchlist_scan` LLM prompt allows `suggested_price: null`, and the AI returns null for HOLD verdicts.
2. The scan job saves `suggested_price` to `AIAnalysis.target_price` only — it never writes back to `WatchlistItem.target_price`, so Target and % to Target remain empty.

## Solution

Two backend changes:

### 1. `llm_gateway.py` — System prompt update

Change the `watchlist_scan` system prompt to always require a numeric price target. Replace the `suggested_price: <number or null>` field with a required number, and add guidance:

> "Always provide a numeric 12-month price target. If verdict is HOLD or AVOID, provide the price level where the thesis would change (fair value or support level)."

### 2. `watchlist_scan.py` — Backfill WatchlistItem.target_price

In `job_scan_watchlist_item`, step 4 (save_suggestion), after creating the `AIAnalysis` record, also update `item.target_price` with the AI's suggested price before committing.

**Data flow after fix:**

```
LLM → suggested_price (always numeric)
  → AIAnalysis.target_price    → "AI Price" column
  → WatchlistItem.target_price → "Target" column → "% to Target" computed
```

### Validation tightening

`_parse_scan_response` currently only validates `verdict`. Add validation that `suggested_price` is present and is a finite number. Return `None` (malformed) if it is missing or non-numeric.

## Scope

| File | Change |
|------|--------|
| `backend/app/services/llm_gateway.py` | Update `watchlist_scan` system prompt |
| `backend/worker/jobs/watchlist_scan.py` | Backfill `WatchlistItem.target_price`; tighten `_parse_scan_response` |

No schema migrations required. `WatchlistItem.target_price` already exists as `Numeric(20, 8)`.

## Behavior

- Scan always overwrites `WatchlistItem.target_price` with the AI's latest price target.
- If the user has manually set a target, the scan will overwrite it.
- Currency: price is stored as-is in the item's native currency (same as current behavior — price data fed to LLM is already in native currency).

## Out of Scope

- Renaming `suggested_price` to `target_price` in the prompt JSON (nice-to-have, not needed for this fix).
- Per-item opt-out of AI target overwrite.
