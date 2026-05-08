# Search & Tab Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the CommandPalette to search pages and tabs, make tab state URL-addressable via `?tab=`, and consolidate `/settings/ai` into `/ai-usage`.

**Architecture:** A static page index (`lib/search/pages.ts`) is imported by the CommandPalette, which now shows a Pages group alongside the existing Holdings group. Tab routing is added to `/settings` and `/ai-usage` using `useSearchParams` + `router.replace`. The `/settings/ai` page is replaced with a server-side redirect.

**Tech Stack:** Next.js App Router, React, Zustand, Tailwind CSS, shadcn/ui (CommandDialog, Tabs), lucide-react

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/lib/search/pages.ts` | Create | Static index of all pages + tabs with search keywords |
| `frontend/components/layout/CommandPalette.tsx` | Modify | Add Pages group + combined search logic |
| `frontend/app/(auth)/settings/page.tsx` | Modify | Add `?tab=` URL routing via `useSearchParams` |
| `frontend/app/(auth)/ai-usage/page.tsx` | Modify | Add `?tab=` URL routing + Import Mapping tab |
| `frontend/app/(auth)/settings/ai/page.tsx` | Replace | Server redirect → `/ai-usage?tab=import-mapping` |

---

## Task 1: Create static page search index

**Files:**
- Create: `frontend/lib/search/pages.ts`

- [ ] **Step 1: Create the file**

```ts
export interface PageEntry {
  label: string;
  url: string;
  keywords: string[];
}

export const PAGES: PageEntry[] = [
  { label: "Overview", url: "/overview", keywords: ["dashboard", "summary"] },
  { label: "Portfolio", url: "/portfolio", keywords: ["holdings", "assets"] },
  { label: "Transactions", url: "/transactions", keywords: ["buy", "sell", "trade"] },
  { label: "Net Worth", url: "/net-worth", keywords: ["wealth", "total"] },
  { label: "Dividends", url: "/dividends", keywords: ["income", "yield"] },
  { label: "Events", url: "/events", keywords: ["calendar", "corporate"] },
  { label: "Documents", url: "/documents", keywords: ["files", "reports"] },
  { label: "Watchlist", url: "/watchlist", keywords: ["watch"] },
  { label: "Import", url: "/import", keywords: ["csv", "upload"] },
  { label: "Pipeline", url: "/pipeline", keywords: ["jobs", "sync"] },
  { label: "Settings → General", url: "/settings?tab=general", keywords: ["display", "currency", "privacy", "profile"] },
  { label: "Settings → AI & LLM", url: "/settings?tab=ai", keywords: ["llm", "model", "ollama", "openai"] },
  { label: "Settings → Integrations", url: "/settings?tab=integrations", keywords: ["sec", "api", "key"] },
  { label: "Settings → Notifications", url: "/settings?tab=notifications", keywords: ["telegram", "alert"] },
  { label: "Settings → Schedule", url: "/settings?tab=schedule", keywords: ["cron", "price fetch"] },
  { label: "Settings → Platforms", url: "/settings?tab=platforms", keywords: ["broker", "color"] },
  { label: "AI Usage → Analyses", url: "/ai-usage", keywords: ["llm cost", "spend", "analysis"] },
  { label: "AI Usage → Call Logs", url: "/ai-usage?tab=call-logs", keywords: ["logs", "tokens"] },
  { label: "AI Usage → Import Mapping", url: "/ai-usage?tab=import-mapping", keywords: ["import", "mapping"] },
];
```

- [ ] **Step 2: Verify TypeScript compiles**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors related to `lib/search/pages.ts`

---

## Task 2: Update CommandPalette with page search

**Files:**
- Modify: `frontend/components/layout/CommandPalette.tsx`

- [ ] **Step 1: Replace the entire file**

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LayoutDashboard } from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { usePaletteStore } from "@/store/palette";
import { PAGES, type PageEntry } from "@/lib/search/pages";

export function CommandPalette() {
  const { open, setOpen, assets } = usePaletteStore();
  const [query, setQuery] = useState("");
  const router = useRouter();

  const q = query.toLowerCase();

  const filteredPages = q
    ? PAGES.filter(
        (p) =>
          p.label.toLowerCase().includes(q) ||
          p.keywords.some((k) => k.toLowerCase().includes(q)),
      )
    : [];

  const filteredAssets = q
    ? assets.filter(
        (a) =>
          a.symbol.toLowerCase().includes(q) ||
          a.name.toLowerCase().includes(q),
      )
    : [];

  const hasPages = filteredPages.length > 0;
  const hasAssets = filteredAssets.length > 0;

  function handleSelectPage(entry: PageEntry) {
    router.push(entry.url);
    setOpen(false);
    setQuery("");
  }

  function handleSelectAsset(symbol: string) {
    router.push(`/portfolio/${symbol}`);
    setOpen(false);
    setQuery("");
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Search pages or holdings..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {q && !hasPages && !hasAssets && (
          <CommandEmpty>No results for &ldquo;{query}&rdquo;</CommandEmpty>
        )}

        {hasPages && (
          <CommandGroup heading="Pages">
            {filteredPages.map((entry) => (
              <CommandItem
                key={entry.url}
                onSelect={() => handleSelectPage(entry)}
                className="flex items-center gap-2"
              >
                <LayoutDashboard className="h-4 w-4 text-muted-foreground shrink-0" />
                <span>{entry.label}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {hasAssets && (
          <CommandGroup heading="Holdings">
            {filteredAssets.map((asset) => (
              <CommandItem
                key={asset.id}
                onSelect={() => handleSelectAsset(asset.symbol)}
                className="flex items-center gap-2"
              >
                <span className="font-mono font-medium">{asset.symbol}</span>
                <span className="text-muted-foreground text-sm">{asset.name}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  );
}
```

- [ ] **Step 2: Open the app and test the palette**

Start dev server if not running:
```bash
cd frontend && npm run dev
```

Open `http://localhost:3000`, trigger the palette (Cmd+K or however it's bound), then:
- Type `"ai"` → should see "Settings → AI & LLM", "AI Usage → Analyses", "AI Usage → Call Logs", "AI Usage → Import Mapping"
- Type `"AAPL"` (or any holding symbol) → should see it under Holdings
- Type `"telegram"` → should see "Settings → Notifications"
- Click a page result → should navigate to that URL
- Type something with no match → should see "No results for…"

---

## Task 3: Add URL tab routing to Settings page

**Files:**
- Modify: `frontend/app/(auth)/settings/page.tsx`

The settings page is already `"use client"`. The strategy: rename the main component to `SettingsContent`, add `useSearchParams` inside it, then export a thin `SettingsPage` wrapper with a `<Suspense>` boundary (required by Next.js for `useSearchParams`).

- [ ] **Step 1: Add imports**

At the top of the file, update the existing imports:

```tsx
// Change this line:
import { useEffect, useState } from "react";
// To:
import { Suspense, useEffect, useState } from "react";

// Add this new import line (settings page has no next/navigation import yet):
import { useRouter, useSearchParams } from "next/navigation";
```

- [ ] **Step 2: Rename the component and add tab state**

Find the line:
```tsx
export default function SettingsPage() {
```
Change to:
```tsx
function SettingsContent() {
```

Then add these two lines immediately after the opening brace (before any existing `const` declarations):
```tsx
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get("tab") ?? "general";
```

- [ ] **Step 3: Wire up the Tabs component**

Find:
```tsx
      <Tabs defaultValue="general">
```
Replace with:
```tsx
      <Tabs value={tab} onValueChange={(v) => router.replace(`/settings?tab=${v}`)}>
```

- [ ] **Step 4: Add the exported wrapper at the bottom of the file**

After the closing `}` of `SettingsContent`, add:
```tsx
export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsContent />
    </Suspense>
  );
}
```

- [ ] **Step 5: Verify in browser**

Navigate to `http://localhost:3000/settings`:
- Click the "AI & LLM" tab → URL should change to `/settings?tab=ai`
- Click "Schedule" → URL should change to `/settings?tab=schedule`
- Navigate directly to `http://localhost:3000/settings?tab=notifications` → Notifications tab should be active on load
- Navigate to `http://localhost:3000/settings` (no param) → General tab should be active

---

## Task 4: Add URL tab routing + Import Mapping tab to AI Usage page

**Files:**
- Modify: `frontend/app/(auth)/ai-usage/page.tsx`

Same Suspense pattern as settings. Additionally adds a third tab "Import Mapping" that fetches LLM call logs filtered by `feature_key=import_mapping`.

- [ ] **Step 1: Add imports**

At the top of the file, update existing imports:
```tsx
// Change:
import React, { useEffect, useState } from "react";
// To:
import React, { Suspense, useEffect, useState } from "react";

// Add this new import line (ai-usage page has no next/navigation import yet):
import { useRouter, useSearchParams } from "next/navigation";
```

- [ ] **Step 2: Rename the component**

Find:
```tsx
export default function AIUsagePage() {
```
Change to:
```tsx
function AIUsageContent() {
```

- [ ] **Step 3: Add tab state and import mapping state**

Add these lines immediately after the opening brace of `AIUsageContent` (before any existing `const` declarations):
```tsx
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get("tab") ?? "analyses";

  const [importLogs, setImportLogs] = useState<CallLog[]>([]);
  const [importLoading, setImportLoading] = useState(false);
```

- [ ] **Step 4: Add useEffect to load import mapping logs**

Add this `useEffect` after the existing `useEffect` hooks (before the function declarations):
```tsx
  useEffect(() => {
    if (tab !== "import-mapping" || importLogs.length > 0) return;
    setImportLoading(true);
    api
      .get("/api/v1/llm/call-logs?feature_key=import_mapping")
      .then((r) => (r.ok ? r.json() : { logs: [] }))
      .then((d) => setImportLogs(d.logs ?? []))
      .catch(() => setImportLogs([]))
      .finally(() => setImportLoading(false));
  }, [tab]);
```

- [ ] **Step 5: Wire up the Tabs component**

Find:
```tsx
      <Tabs defaultValue="analyses">
        <TabsList>
          <TabsTrigger value="analyses">Analyses</TabsTrigger>
          <TabsTrigger value="call-logs">LLM Call Logs</TabsTrigger>
        </TabsList>
```
Replace with:
```tsx
      <Tabs value={tab} onValueChange={(v) => router.replace(`/ai-usage?tab=${v}`)}>
        <TabsList>
          <TabsTrigger value="analyses">Analyses</TabsTrigger>
          <TabsTrigger value="call-logs">LLM Call Logs</TabsTrigger>
          <TabsTrigger value="import-mapping">Import Mapping</TabsTrigger>
        </TabsList>
```

- [ ] **Step 6: Add the Import Mapping TabsContent**

Find the closing `</Tabs>` tag and add the new tab content immediately before it:
```tsx
        <TabsContent value="import-mapping" className="pt-2">
          {importLoading ? (
            <div className="space-y-3 mt-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <div key={j} className="h-4 flex-1 bg-muted animate-pulse rounded" />
                  ))}
                </div>
              ))}
            </div>
          ) : importLogs.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center text-sm">
              No import mapping calls yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm mt-4">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Date</th>
                    <th className="text-left py-2">Feature</th>
                    <th className="text-left py-2">Provider / Model</th>
                    <th className="text-right py-2">Tokens In</th>
                    <th className="text-right py-2">Tokens Out</th>
                    <th className="text-right py-2">Cost (THB)</th>
                  </tr>
                </thead>
                <tbody>
                  {importLogs.map((log) => (
                    <tr key={log.id} className="border-b hover:bg-muted/50">
                      <td className="py-2">
                        {new Date(log.created_at).toLocaleDateString("en-GB")}
                      </td>
                      <td className="py-2">{log.feature_key.replace(/_/g, " ")}</td>
                      <td className="py-2">
                        {log.provider} / {log.model}
                      </td>
                      <td className="py-2 text-right">{log.tokens_in.toLocaleString()}</td>
                      <td className="py-2 text-right">{log.tokens_out.toLocaleString()}</td>
                      <td className="py-2 text-right">฿{log.cost_thb.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
```

- [ ] **Step 7: Add the exported wrapper at the bottom of the file**

After the closing `}` of `AIUsageContent`, add:
```tsx
export default function AIUsagePage() {
  return (
    <Suspense fallback={null}>
      <AIUsageContent />
    </Suspense>
  );
}
```

- [ ] **Step 8: Verify in browser**

Navigate to `http://localhost:3000/ai-usage`:
- Click "LLM Call Logs" → URL changes to `/ai-usage?tab=call-logs`
- Click "Import Mapping" → URL changes to `/ai-usage?tab=import-mapping`, table loads (or shows empty state)
- Navigate directly to `http://localhost:3000/ai-usage?tab=import-mapping` → Import Mapping tab is active on load
- Navigate to `http://localhost:3000/ai-usage` → Analyses tab is active

---

## Task 5: Replace /settings/ai with redirect

**Files:**
- Replace: `frontend/app/(auth)/settings/ai/page.tsx`

The existing page showed LLM call logs — that content now lives at `/ai-usage?tab=import-mapping`. Replace the entire file with a server-side redirect.

- [ ] **Step 1: Replace the entire file**

```tsx
import { redirect } from "next/navigation";

export default function SettingsAiPage() {
  redirect("/ai-usage?tab=import-mapping");
}
```

Note: No `"use client"` directive — this is a server component so `redirect()` from `next/navigation` works directly.

- [ ] **Step 2: Verify redirect works**

Navigate to `http://localhost:3000/settings/ai` → should immediately land on `/ai-usage?tab=import-mapping` with the Import Mapping tab active.

- [ ] **Step 3: Verify TypeScript compiles clean**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

---

## End-to-End Verification Checklist

- [ ] Palette opens → type `"settings"` → sees all 6 Settings tabs as separate entries
- [ ] Palette → type `"AI"` → sees "Settings → AI & LLM" and "AI Usage" entries
- [ ] Clicking "Settings → AI & LLM" from palette → navigates to `/settings?tab=ai`
- [ ] Clicking Settings tab in sidebar → `/settings` loads on General tab
- [ ] Clicking each Settings tab → URL updates accordingly
- [ ] Refreshing page on `/settings?tab=notifications` → Notifications tab is pre-selected
- [ ] Navigating to `/settings/ai` → redirects to `/ai-usage?tab=import-mapping`
- [ ] `/ai-usage?tab=import-mapping` → Import Mapping tab is active, shows table or empty state
- [ ] Back button from `/ai-usage?tab=call-logs` → goes back to previous page (not to analyses tab), because `router.replace` was used
