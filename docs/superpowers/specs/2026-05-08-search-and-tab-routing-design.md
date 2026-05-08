# Search & Tab Routing Design

**Date:** 2026-05-08  
**Status:** Approved

## Overview

Extend the global CommandPalette to search pages and tabs in addition to holdings. Make tab state URL-addressable via query params so users can bookmark and share deep links to specific tabs. Consolidate the duplicate `/settings/ai` page into `/ai-usage`.

## Goals

1. Search bar finds pages and tabs, not just holdings
2. Tab state is reflected in the URL (`?tab=`) for bookmarking and direct navigation
3. `/settings/ai` is removed — its content lives at `/ai-usage?tab=import-mapping`

## Section 1: Tab URL Routing

### Approach

Use `useSearchParams()` to read the current tab and `router.replace()` to write it. `router.replace` (not `push`) so tab switches don't pollute browser history. Both pages must be wrapped in `<Suspense>` as required by Next.js for `useSearchParams`.

### `/settings` — 6 tabs

| Tab label | `?tab=` value | Default |
|-----------|--------------|---------|
| General | `general` | ✅ yes |
| AI & LLM | `ai` | |
| Integrations | `integrations` | |
| Notifications | `notifications` | |
| Schedule | `schedule` | |
| Platforms | `platforms` | |

URL pattern: `/settings?tab=ai`

### `/ai-usage` — 3 tabs (expanded from 2)

| Tab label | `?tab=` value | Default |
|-----------|--------------|---------|
| Analyses | `analyses` | ✅ yes |
| LLM Call Logs | `call-logs` | |
| Import Mapping | `import-mapping` | (moved from `/settings/ai`) |

URL pattern: `/ai-usage?tab=import-mapping`

### `/settings/ai` — Delete & redirect

Replace `frontend/app/(auth)/settings/ai/page.tsx` with a server component that calls `redirect("/ai-usage?tab=import-mapping")`.

## Section 2: Static Page Search Index

New file: `frontend/lib/search/pages.ts`

```ts
export interface PageEntry {
  label: string;
  url: string;
  keywords: string[];
}
```

### Full page index

| Label | URL | Keywords |
|-------|-----|---------|
| Overview | `/overview` | dashboard, summary |
| Portfolio | `/portfolio` | holdings, assets |
| Transactions | `/transactions` | buy, sell, trade |
| Net Worth | `/net-worth` | wealth, total |
| Dividends | `/dividends` | income, yield |
| Events | `/events` | calendar, corporate |
| Documents | `/documents` | files, reports |
| Watchlist | `/watchlist` | watch |
| Import | `/import` | csv, upload |
| Pipeline | `/pipeline` | jobs, sync |
| Settings → General | `/settings?tab=general` | display, currency, privacy, profile |
| Settings → AI & LLM | `/settings?tab=ai` | llm, model, ollama, openai |
| Settings → Integrations | `/settings?tab=integrations` | sec, api, key |
| Settings → Notifications | `/settings?tab=notifications` | telegram, alert |
| Settings → Schedule | `/settings?tab=schedule` | cron, price fetch |
| Settings → Platforms | `/settings?tab=platforms` | broker, color |
| AI Usage → Analyses | `/ai-usage` | llm cost, spend |
| AI Usage → Call Logs | `/ai-usage?tab=call-logs` | logs, tokens |
| AI Usage → Import Mapping | `/ai-usage?tab=import-mapping` | import, mapping |

Search logic: case-insensitive substring match against `label` + `keywords[]`.

## Section 3: CommandPalette UI & Search Logic

### Display behavior

| State | What shows |
|-------|-----------|
| Empty query | Nothing (clean input only) |
| Query matches pages only | Pages group |
| Query matches holdings only | Holdings group |
| Query matches both | Pages group first, then Holdings |
| No matches | Empty state: "No results for …" |

### Result item appearance

```
Pages
  [icon] Settings → AI & LLM
  [icon] AI Usage → Import Mapping

Holdings
  AAPL   Apple Inc.
  BTC    Bitcoin
```

- Pages use a lucide icon (e.g. `LayoutDashboard` or `FileText`)
- Holdings keep existing layout (symbol + name in mono font)

### Navigation

- Page item: `router.push(entry.url)` → close palette → clear query
- Holding item: `router.push(/portfolio/${symbol})` → close palette → clear query (unchanged)

## Files to Create / Modify

| File | Action |
|------|--------|
| `frontend/lib/search/pages.ts` | Create — static page index |
| `frontend/components/layout/CommandPalette.tsx` | Modify — add Pages group + combined search |
| `frontend/app/(auth)/settings/page.tsx` | Modify — `useSearchParams` tab routing |
| `frontend/app/(auth)/ai-usage/page.tsx` | Modify — `useSearchParams` + Import Mapping tab |
| `frontend/app/(auth)/settings/ai/page.tsx` | Replace — redirect to `/ai-usage?tab=import-mapping` |

## Out of Scope

- `/portfolio/[symbol]` chart range tabs (1W/1M/3M/1Y) — UI state only, not navigation
- `/settings/backup` — standalone page, no tabs, include in page index as plain entry if needed later
- AI-powered fuzzy search — plain substring match is sufficient
