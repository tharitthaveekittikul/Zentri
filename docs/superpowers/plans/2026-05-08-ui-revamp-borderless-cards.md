# UI Revamp: Borderless Cards & Premium Minimal Design — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all card borders, give every component a white background so it lifts off the gray shell, and fix mobile text overflow — producing a premium minimal look across all pages.

**Architecture:** One CSS token change (`--card`) makes all shadcn `<Card>` and `.card-surface` elements white automatically. A single `border-width: 0` rule strips borders globally from those selectors. Pages with naked tables (not using Card) get a `bg-card card-surface rounded-2xl overflow-hidden` wrapper added around their table content.

**Tech Stack:** Next.js 15 app router, Tailwind CSS v4, shadcn/ui, TypeScript

---

## File Map

| File | Change |
|------|--------|
| `frontend/app/globals.css` | Token + border-removal rule |
| `frontend/app/(auth)/transactions/page.tsx` | Table wrapper + mobile |
| `frontend/app/(auth)/watchlist/page.tsx` | Table + suggestions wrappers + mobile |
| `frontend/app/(auth)/pipeline/page.tsx` | JobsTable wrapper |
| `frontend/app/(auth)/ai-usage/page.tsx` | Tabs wrapper |
| `frontend/app/(auth)/documents/page.tsx` | Table wrapper |
| `frontend/app/(auth)/events/page.tsx` | Calendar + upcoming table wrappers |
| `frontend/app/(auth)/net-worth/page.tsx` | Mobile chart min-h fix |
| `frontend/app/(auth)/import/page.tsx` | Responsive padding fix |

---

## Task 1: Token Change + Border Removal (`globals.css`)

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Change `--card` token in `:root`**

In `globals.css`, find the `:root` block. Change:
```css
--card: var(--page-bg);
```
to:
```css
--card: oklch(1 0 0);
```
This makes cards pure white in light mode. Dark mode (`--card: oklch(0.13 0 0)`) is already correct — do not touch the `.dark` block.

- [ ] **Step 2: Add border-removal rule**

In `globals.css`, inside the `@layer base` block, after the existing `[data-slot="card"], .card-surface { box-shadow: var(--card-shadow); }` rule, add:

```css
  /* Borderless cards — shadow provides depth */
  [data-slot="card"],
  .card-surface {
    border-width: 0;
  }
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors (CSS changes don't affect TS compilation — this just confirms nothing was accidentally broken).

- [ ] **Step 4: Visual check**

Open http://localhost:3000/overview in browser. Confirm:
- KPI cards are white with a subtle shadow, no visible border
- Chart/allocation panels are white, no border
- Background behind cards is light gray
- Dark mode toggle: cards are dark gray, no border visible

---

## Task 2: Transactions Page

**Files:**
- Modify: `frontend/app/(auth)/transactions/page.tsx`

- [ ] **Step 1: Replace skeleton loading wrapper**

Find:
```tsx
      {loading ? (
        <div className="rounded-md border">
          <div className="p-4 space-y-3">
```
Replace with:
```tsx
      {loading ? (
        <div className="bg-card card-surface rounded-2xl">
          <div className="p-4 space-y-3">
```

- [ ] **Step 2: Replace table wrapper**

Find:
```tsx
          <div
            className={`rounded-md border overflow-x-auto transition-opacity ${
              fetching ? "opacity-60" : ""
            }`}
          >
```
Replace with:
```tsx
          <div
            className={`bg-card card-surface rounded-2xl overflow-hidden overflow-x-auto transition-opacity ${
              fetching ? "opacity-60" : ""
            }`}
          >
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Visual check**

Open http://localhost:3000/transactions. Confirm:
- Table sits in a white rounded card with shadow, no border
- On mobile viewport (375px): table scrolls horizontally, no layout break
- Text in symbol/platform columns is not cut off

---

## Task 3: Watchlist Page

**Files:**
- Modify: `frontend/app/(auth)/watchlist/page.tsx`

- [ ] **Step 1: Replace skeleton loading wrapper**

Find:
```tsx
      {loading ? (
        <div className="rounded-md border">
          <div className="p-4 space-y-3">
```
Replace with:
```tsx
      {loading ? (
        <div className="bg-card card-surface rounded-2xl">
          <div className="p-4 space-y-3">
```

- [ ] **Step 2: Replace table wrapper**

Find:
```tsx
        <div className="rounded-md border overflow-x-auto">
          <Table>
```
Replace with:
```tsx
        <div className="bg-card card-surface rounded-2xl overflow-hidden overflow-x-auto">
          <Table>
```

- [ ] **Step 3: Wrap AI Suggestions section**

Find line ~610 in `watchlist/page.tsx`:
```tsx
      {suggestions.length > 0 && (
```
The block that follows contains the `<Sparkles>` heading and the suggestion items. Wrap it with a card div. Change from:
```tsx
      {suggestions.length > 0 && (
        <div className="space-y-4">
```
to:
```tsx
      {suggestions.length > 0 && (
        <div className="bg-card card-surface rounded-2xl p-5 space-y-4">
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Visual check**

Open http://localhost:3000/watchlist. Confirm:
- Watchlist table is in a white card, no border
- AI Suggestions section has its own white card below
- Mobile: table scrolls horizontally

---

## Task 4: Pipeline Page

**Files:**
- Modify: `frontend/app/(auth)/pipeline/page.tsx`

- [ ] **Step 1: Wrap JobsTable in a card**

The current return is:
```tsx
  return (
    <div className="space-y-4">
      <PageHeader title="Pipeline" />
      <p className="text-muted-foreground text-sm">
        Live price fetch job status. Updates every 3 seconds via SSE.
      </p>
      <TriggerButtons />
      <JobsTable jobs={jobs} />
    </div>
  );
```

Replace with:
```tsx
  return (
    <div className="space-y-4">
      <PageHeader title="Pipeline" />
      <p className="text-muted-foreground text-sm">
        Live price fetch job status. Updates every 3 seconds via SSE.
      </p>
      <TriggerButtons />
      <div className="bg-card card-surface rounded-2xl overflow-hidden overflow-x-auto">
        <JobsTable jobs={jobs} />
      </div>
    </div>
  );
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Visual check**

Open http://localhost:3000/pipeline. Confirm:
- Pipeline Jobs table is in a white rounded card
- Trigger buttons above remain unchanged
- Mobile: table scrolls horizontally if needed

---

## Task 5: AI Usage Page

**Files:**
- Modify: `frontend/app/(auth)/ai-usage/page.tsx`

The stat cards at the top already use `<Card>` — they'll be auto-fixed by Task 1. This task wraps the Tabs + tables section.

- [ ] **Step 1: Wrap the Tabs section in a card**

Find the return section. The structure after the stat cards is:
```tsx
      <Tabs ...>
        <TabsList>
          ...
        </TabsList>
        <TabsContent ...>
          ...tables...
        </TabsContent>
      </Tabs>
```

Wrap the entire `<Tabs>` block:
```tsx
      <div className="bg-card card-surface rounded-2xl p-5">
        <Tabs ...>
          <TabsList>
            ...
          </TabsList>
          <TabsContent ...>
            ...tables...
          </TabsContent>
        </Tabs>
      </div>
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Visual check**

Open http://localhost:3000/ai-usage. Confirm:
- Three stat cards are white with shadow
- The tabs + logs table are inside their own white card
- Mobile: tables scroll horizontally

---

## Task 6: Documents Page

**Files:**
- Modify: `frontend/app/(auth)/documents/page.tsx`

- [ ] **Step 1: Wrap the filter + table area in a card**

The current return after the upload button row is:
```tsx
      <Input
        placeholder="Filter by asset symbol…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="max-w-xs"
      />

      {loading ? (
        <div className="space-y-3">
          ...skeletons...
        </div>
      ) : (
      <div className="overflow-x-auto">
      <Table>
        ...
      </Table>
      </div>
      )}
```

Wrap the filter Input + loading/table conditional in a single card:
```tsx
      <div className="bg-card card-surface rounded-2xl p-5 space-y-4">
        <Input
          placeholder="Filter by asset symbol…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-xs"
        />

        {loading ? (
          <div className="space-y-3">
            ...skeletons...
          </div>
        ) : (
        <div className="overflow-x-auto">
        <Table>
          ...
        </Table>
        </div>
        )}
      </div>
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Visual check**

Open http://localhost:3000/documents. Confirm:
- Filter input and table are inside a white card
- Upload PDF button above the card is unaffected
- Mobile: table scrolls horizontally

---

## Task 7: Events Page

**Files:**
- Modify: `frontend/app/(auth)/events/page.tsx`

- [ ] **Step 1: Wrap CalendarGrid in a card**

In `events/page.tsx`, find the `<CalendarGrid>` component usage in the EventsPage return (after the filter pill buttons). It's rendered as a self-contained component. Wrap it:
```tsx
      <div className="bg-card card-surface rounded-2xl overflow-hidden">
        <CalendarGrid
          year={year}
          month={month}
          events={filteredEvents}
          onSelectDividend={setSelectedDividend}
          onSelectIpo={setSelectedIpo}
        />
      </div>
```
(Prop names may differ slightly — use whatever props are already passed to `<CalendarGrid>`.)

- [ ] **Step 2: Wrap Upcoming Events table in a card**

Find the "Upcoming Events" heading + `<Table>` block below the calendar. It will start with something like `<h2>Upcoming Events</h2>` or a similar heading. Wrap the heading + table together:
```tsx
      <div className="bg-card card-surface rounded-2xl overflow-hidden overflow-x-auto">
        <div className="p-5">
          <h2 className="font-semibold mb-4">Upcoming Events</h2>
        </div>
        <Table>
          ...existing table content...
        </Table>
      </div>
```
Keep the existing heading and table content unchanged — only add the outer wrapper and adjust padding if needed.

- [ ] **Step 3: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Visual check**

Open http://localhost:3000/events. Confirm:
- Calendar sits inside a white rounded card
- Upcoming events table is in its own white card below
- Mobile: calendar is usable; upcoming table scrolls horizontally

---

## Task 8: Net Worth + Import — Mobile Polish

**Files:**
- Modify: `frontend/app/(auth)/net-worth/page.tsx`
- Modify: `frontend/app/(auth)/import/page.tsx`

- [ ] **Step 1: Net Worth — add min-h-0 to chart container**

Current file:
```tsx
export default function NetWorthPage() {
  const { isPrivate } = usePrivacyStore();
  return (
    <div className="space-y-6">
      <PageHeader title="Net Worth" />
      <NetWorthChart privacyMode={isPrivate} />
    </div>
  );
}
```

Replace with:
```tsx
export default function NetWorthPage() {
  const { isPrivate } = usePrivacyStore();
  return (
    <div className="space-y-6 min-h-0">
      <PageHeader title="Net Worth" />
      <div className="min-h-0">
        <NetWorthChart privacyMode={isPrivate} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Import — fix idle state responsive layout**

Find the idle state return:
```tsx
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-16 px-6">
```
Replace with:
```tsx
  return (
    <div className="flex flex-col items-center justify-center gap-6 py-8 sm:py-16 px-4 sm:px-6">
```

Also find the dropzone div:
```tsx
      <div
        className="border-2 border-dashed rounded-xl p-12 flex flex-col items-center gap-4
                   cursor-pointer hover:border-primary transition-colors w-full max-w-md"
```
Replace with:
```tsx
      <div
        className="border-2 border-dashed rounded-xl p-8 sm:p-12 flex flex-col items-center gap-4
                   cursor-pointer hover:border-primary transition-colors w-full max-w-md"
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Visual check**

- http://localhost:3000/net-worth — chart fills card properly on mobile, no overflow
- http://localhost:3000/import — dropzone is not cramped on mobile, padding is comfortable

---

## Task 9: Final Cross-Page Review

- [ ] **Step 1: Check Portfolio page**

Open http://localhost:3000/portfolio. The Holdings cards and stat cards use `<Card>` and `bg-card card-surface` — Task 1 auto-fixes these. Confirm:
- Stat cards (Holdings, Total Cost) are white with shadow
- Platform breakdown cards are white
- Holdings table: `HoldingsTable` component — check if it has its own `rounded-md border` wrapper internally

- [ ] **Step 2: If HoldingsTable has internal border, fix it**

Run:
```bash
grep -n "rounded-md border\|border rounded" /Users/tharitthaveekittikul/Documents/03_Projects/Zentri/frontend/components/portfolio/HoldingsTable.tsx
```

If found, replace `rounded-md border` with `bg-card card-surface rounded-2xl overflow-hidden` in that component.

- [ ] **Step 3: Check Overview page**

Open http://localhost:3000/overview. Both chart sections use `bg-card card-surface rounded-2xl` already — confirm they render as white cards with shadow, no border.

- [ ] **Step 4: Check Settings and Backup**

- http://localhost:3000/settings — all sections use `<Card>` — auto-fixed
- http://localhost:3000/settings/backup — all sections use `<Card>` — auto-fixed
Confirm no borders visible on any card.

- [ ] **Step 5: Mobile sweep**

Using browser DevTools, set viewport to 375px wide. Check each page:
- [ ] Overview — KPI cards stack to 1 or 2 cols, no text overflow
- [ ] Portfolio — cards visible, table scrolls
- [ ] Transactions — table scrolls, no clipped text
- [ ] Watchlist — table scrolls
- [ ] Events — calendar is navigable
- [ ] Pipeline — table scrolls

Fix any remaining overflow issues found during this sweep.
