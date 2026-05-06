# Currency Display & Privacy Masking — Design Spec

**Date:** 2026-05-07  
**Status:** Approved

---

## Problem

Currency display across the app is inconsistent:

- `SummaryBar` (overview) hardcodes `$` regardless of user settings
- `net-worth-chart` labels values with the user's primary currency but the data itself is always in USD (`value_usd` / `cost_usd`) — the label is misleading
- `portfolio/[symbol]/page.tsx`, `watchlist/page.tsx`, `events/page.tsx` all hardcode `$`
- `transactions/page.tsx` shows raw numbers with no currency label
- `CashAccountsSection` shows the account's native currency with no secondary conversion
- Privacy mode (`PrivacyValue`) hides the entire string including the currency label, whereas the desired behaviour is to mask only the number and keep the label visible

---

## Goals

1. Every monetary value shows **primary currency** (user setting) with a **secondary currency** conversion below/inline.
2. Privacy mode shows `****** {CURRENCY}` — number masked, currency label always visible. Percentages and exchange rates stay visible.
3. A single shared component (`DualCurrencyAmount`) owns monetary display and privacy masking.
4. No hardcoded `$`, `฿`, or currency assumptions anywhere in the frontend.

---

## Privacy Behaviour (from reference image)

| Value type | Privacy OFF | Privacy ON |
|---|---|---|
| Primary amount | `1,234.56 THB` | `****** THB` |
| Secondary amount | `≈ 45.67 USD` | `≈ ****** USD` |
| Percentage | `+1.60%` | `+1.60%` (unchanged) |
| Exchange rate line | `1 USD = 32.16 THB` | `1 USD = 32.16 THB` (unchanged) |
| P&L with amount | `+40.32% (+1,234 USD)` | `+40.32% (****** USD)` |
| Account numbers / identifiers | masked by `PrivacyValue` | `******` |

Rule: **mask digits, preserve labels**.

---

## Architecture

### 1. `DualValue` interface update — `hooks/useDualCurrency.ts`

Add currency label fields so `DualCurrencyAmount` can construct masked strings without string parsing:

```typescript
export interface DualValue {
  primary: string;                // "1,234.56 THB"
  secondary: string | null;       // "≈ 45.67 USD"
  primaryCurrency: string;        // "THB"
  secondaryCurrency: string | null; // "USD"
}
```

`useDualCurrency().format()` already builds `primary` and `secondary`; add `primaryCurrency` and `secondaryCurrency` from the existing hook state. No other hook changes.

### 2. `DualCurrencyAmount` component — `components/ui/DualCurrencyAmount.tsx`

New shared component. Single source of truth for all monetary display.

**Props:**
```typescript
interface Props {
  value: DualValue;
  primaryClassName?: string;   // size / color override
  inline?: boolean;            // one-line: "1,234.56 THB (≈ 45.67 USD)"
}
```

**Behaviour:**
- Reads `isPrivate` from `usePrivacyStore`
- When private: constructs `****** {primaryCurrency}` and `≈ ****** {secondaryCurrency}` directly — no `PrivacyValue` wrapping needed
- When not private: renders `value.primary` and `value.secondary`
- `inline=false` (default): primary on top, secondary muted below — matches KpiCards style
- `inline=true`: single line for table cells

This component replaces the duplicated `PrivacyValue` + secondary pattern currently in `KpiCards` and `HoldingsSnapshot`.

### 3. `PrivacyValue` update — `components/ui/PrivacyValue.tsx`

Change mask from `••••` to `******` for visual consistency with the masked monetary values. Used only for non-monetary sensitive data (account numbers, identifiers).

### 4. `HoldingsTable` — `MoneyCell` update

`MoneyCell` already has its own primary/secondary conversion logic per native asset currency. Update it to apply the same privacy masking: when `isPrivate`, show `****** {currency}` instead of the formatted number.

---

## Files to Modify

| File | Change |
|---|---|
| `hooks/useDualCurrency.ts` | Add `primaryCurrency` / `secondaryCurrency` to `DualValue` return |
| `components/ui/DualCurrencyAmount.tsx` | **NEW** — stacked dual currency with privacy masking |
| `components/ui/PrivacyValue.tsx` | Change mask `••••` → `******` |
| `components/overview/SummaryBar.tsx` | Remove hardcoded `$`; use `useDualCurrency` + `DualCurrencyAmount` |
| `components/net-worth-chart.tsx` | Multiply `value_usd`/`cost_usd` by exchange rate from hook to display in primary currency |
| `components/portfolio/HoldingsTable.tsx` | Update `MoneyCell` privacy masking |
| `components/portfolio/CashAccountsSection.tsx` | Balance is in the account's native currency — use `MoneyCell`-style native→primary conversion (same pattern as `HoldingsTable`), then show primary + secondary with `DualCurrencyAmount` |
| `app/(auth)/portfolio/[symbol]/page.tsx` | Replace `$${tx.price}`, `$${tx.fee}`, `$${latestBar.close}` with `useDualCurrency` |
| `app/(auth)/watchlist/page.tsx` | Replace `$${current_price}`, `$${target_price}` |
| `app/(auth)/events/page.tsx` | Replace `$${amount_per_share}` |
| `app/(auth)/transactions/page.tsx` | Transaction `price` and `fee` are in the asset's native currency — use `MoneyCell`-style native→primary conversion with `DualCurrencyAmount` |

---

## Data Notes

### net-worth-chart
The `/api/v1/overview/net-worth` endpoint returns `value_usd` and `cost_usd` (always USD). The chart must multiply these by the exchange rate (available from `useDualCurrency`) to plot in the user's primary currency. The y-axis label becomes `primaryCurrency`.

No backend changes required — the conversion happens in the chart component using the live exchange rate from the hook.

### exchange rate direction
`useDualCurrency` fetches rate as `from=primaryCurrency, to=secondaryCurrency`. The `format()` function multiplies by this rate to get the secondary value. For `net-worth-chart`, if primary is THB and data is USD, the rate needed is `from=USD, to=THB`. The hook already handles this via `fetchExchangeRate(primaryCurrency, secondaryCurrency)` — but `value_usd` is in USD and primary might be THB. Need to fetch the inverse rate (`from=USD, to=primaryCurrency`) separately in the chart component, or use `1 / rate` when primary ≠ USD.

**Decision:** In `net-worth-chart`, if the primary currency is not USD, fetch `fetchExchangeRate("USD", primaryCurrency)` independently (1-hour cache, same as hook). If primary IS USD, no conversion needed.

---

## Out of Scope

- Cash inclusion in `OverviewSummary.total_value` — separate backend investigation
- AI cost display in `settings/ai/page.tsx` — intentionally always USD/THB (AI billing is in USD)
- Adding more currencies beyond THB/USD — settings page already handles this generically

---

## Acceptance Criteria

- [ ] No `$` hardcoded in any page or component (except AI cost pages)
- [ ] Every monetary value shows both primary and secondary currency
- [ ] Privacy ON: amounts show `****** {CURRENCY}`, percentages and exchange rates unchanged
- [ ] `DualCurrencyAmount` is the only place that constructs monetary display strings
- [ ] `net-worth-chart` y-axis and tooltip values match the user's primary currency
- [ ] `CashAccountsSection` shows balance with secondary currency conversion
- [ ] `transactions/page.tsx` price and fee columns have currency labels
