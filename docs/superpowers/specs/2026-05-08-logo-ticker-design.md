# Logo Ticker Design

**Date:** 2026-05-08  
**Status:** Approved

## Goal

Show company/asset logos next to ticker symbols throughout the app — portfolio, watchlist, events, transactions, and the symbol detail page. When no logo is available, show plain text ticker only (no fallback avatar).

## Approach: Hybrid

- Backend stores `logo_url` in the existing `metadata_` JSONB field — no DB migration needed.
- Frontend `TickerLogo` component reads `metadata_.logo_url` and renders it. On error, renders nothing.

## Logo Sources (validated)

| Asset Type | Source | Mechanism |
|---|---|---|
| `us_stock`, `etf`, `thai_stock`, `thai_dr` | yfinance `info.get("website")` → Google favicon API | `https://www.google.com/s2/favicons?domain={domain}&sz=64` |
| `crypto` | CoinGecko `thumb` (already returned at creation) | Pass through `metadata_.logo_url` at creation time |
| `th_fund`, `gold`, `cash` | None | Skip — no logo |

**Verified:** yfinance returns `website` for both US and Thai (`.BK`) stocks. Google favicon API returns `image/png` for all tested tickers (AAPL, PTT.BK, KBANK.BK, AOT.BK).

## Section 1: Frontend — `TickerLogo` Component

**File:** `frontend/components/ui/TickerLogo.tsx`

**Props:** `{ symbol: string; assetType: string; logoUrl?: string; size?: number }`

**Behavior:**
- Reads `logoUrl` (from `metadata_.logo_url`)
- If missing or image fails to load → renders `null` (parent shows plain text)
- Uses `next/image` with `unoptimized={true}` — logos come from dynamic external domains (Google favicon CDN), so Next.js optimization pipeline is bypassed. For 24px icons this is correct.
- `loading="lazy"` (default for `next/image`, explicit for clarity)
- `onError` flips `useState(false)` → component returns `null`

```tsx
"use client";
import Image from "next/image";
import { useState } from "react";

export function TickerLogo({ symbol, assetType, logoUrl, size = 24 }: {
  symbol: string; assetType: string; logoUrl?: string; size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!logoUrl || failed) return null;
  return (
    <Image src={logoUrl} alt={symbol} width={size} height={size}
      unoptimized loading="lazy" className="rounded-full object-contain"
      onError={() => setFailed(true)} />
  );
}
```

**Usage at call sites:**
```tsx
<div className="flex items-center gap-2">
  <TickerLogo symbol={row.symbol} assetType={row.asset_type} logoUrl={row.metadata_?.logo_url} />
  <span>{row.symbol}</span>
</div>
```

## Section 2: Backend — Populating `logo_url`

### Asset creation (`backend/app/services/asset.py`)

For `us_stock`, `etf`, `thai_stock`, `thai_dr`: fetch `website` from yfinance and construct Google favicon URL.

```python
import yfinance as yf

def get_logo_url(symbol: str, asset_type: str) -> str | None:
    if asset_type not in ("us_stock", "etf", "thai_stock", "thai_dr"):
        return None
    yf_symbol = f"{symbol}.BK" if asset_type in ("thai_stock", "thai_dr") else symbol
    try:
        info = yf.Ticker(yf_symbol).info
        website = info.get("website", "")
        if not website:
            return None
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    except Exception:
        return None
```

For `crypto`: pass CoinGecko `thumb` into `metadata_["logo_url"]` at creation time (already available in `CoinGeckoResult.thumb`).

### Backfill endpoint

`POST /api/v1/assets/backfill-logos` — iterates existing assets without `logo_url` in metadata, fetches and stores. Called once manually by the user.

## Section 3: Pages Updated

| Page | Location |
|---|---|
| `portfolio/page.tsx` | `HoldingsTable` symbol column |
| `portfolio/[symbol]/page.tsx` | Page header |
| `watchlist/page.tsx` | Ticker column |
| `events/page.tsx` | Symbol column (table + calendar chips) — verify `asset_type` is in `CalendarEvent` schema; add if missing |
| `transactions/page.tsx` | Symbol column |
