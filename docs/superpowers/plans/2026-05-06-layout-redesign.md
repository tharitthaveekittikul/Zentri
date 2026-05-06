# Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the app shell (Sidebar, TopNav, BottomTabBar) to match the Donezo reference, move page titles into content via a new PageHeader component.

**Architecture:** New `PageHeader` component handles all page-level titles. `TopNav` becomes a pure utility bar (search pill + actions). `Sidebar` gets a stronger filled active state. `BottomTabBar` gets a landscape pill active indicator.

**Tech Stack:** Next.js App Router, React, Tailwind CSS, Lucide icons, shadcn/ui Button

---

## File Map

| Action | File |
|--------|------|
| CREATE | `frontend/components/layout/PageHeader.tsx` |
| MODIFY | `frontend/components/layout/Sidebar.tsx` |
| MODIFY | `frontend/components/layout/TopNav.tsx` |
| MODIFY | `frontend/components/layout/BottomTabBar.tsx` |
| MODIFY | `frontend/app/(auth)/page.tsx` |
| MODIFY | `frontend/app/(auth)/overview/page.tsx` |
| MODIFY | `frontend/app/(auth)/portfolio/page.tsx` |
| MODIFY | `frontend/app/(auth)/portfolio/[symbol]/page.tsx` |
| MODIFY | `frontend/app/(auth)/watchlist/page.tsx` |
| MODIFY | `frontend/app/(auth)/net-worth/page.tsx` |
| MODIFY | `frontend/app/(auth)/events/page.tsx` |
| MODIFY | `frontend/app/(auth)/transactions/page.tsx` |
| MODIFY | `frontend/app/(auth)/documents/page.tsx` |
| MODIFY | `frontend/app/(auth)/pipeline/page.tsx` |
| MODIFY | `frontend/app/(auth)/import/page.tsx` |
| MODIFY | `frontend/app/(auth)/ai-usage/page.tsx` |
| MODIFY | `frontend/app/(auth)/dividends/page.tsx` |
| MODIFY | `frontend/app/(auth)/settings/page.tsx` |
| MODIFY | `frontend/app/(auth)/settings/ai/page.tsx` |
| MODIFY | `frontend/app/(auth)/settings/backup/page.tsx` |

---

## Task 1: PageHeader Component

**Files:**
- Create: `frontend/components/layout/PageHeader.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/layout/PageHeader.tsx
import React from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
}

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      {description && (
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the file exists and has no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep PageHeader`
Expected: no output (no errors)

---

## Task 2: Sidebar Redesign

**Files:**
- Modify: `frontend/components/layout/Sidebar.tsx`

- [ ] **Step 1: Update NavItem for stronger active fill and taller padding**

Replace the entire `NavItem` function with:

```tsx
function NavItem({ href, label, icon: Icon, pathname }: { href: string; label: string; icon: React.ElementType; pathname: string }) {
  const isActive = pathname === href;
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2.5 px-3 py-2 rounded-[10px] text-sm font-medium transition-all duration-150",
        isActive
          ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
      )}
    >
      <Icon
        className={cn(
          "h-[15px] w-[15px] shrink-0",
          isActive ? "opacity-100" : "opacity-50"
        )}
      />
      {label}
    </Link>
  );
}
```

- [ ] **Step 2: Update section label styling for more prominent look**

Replace both `<p>` section label elements. First one (Portfolio):
```tsx
<p className="px-3 mb-1.5 text-[10px] font-semibold tracking-[0.12em] uppercase text-sidebar-foreground/40">
  Portfolio
</p>
```

Second one (Tools):
```tsx
<p className="px-3 mb-1.5 text-[10px] font-semibold tracking-[0.12em] uppercase text-sidebar-foreground/40">
  Tools
</p>
```

- [ ] **Step 3: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep Sidebar`
Expected: no output

- [ ] **Step 4: Start dev server and visually verify sidebar**

Run: `cd frontend && npm run dev`

Open browser at `http://localhost:3000`. Check:
- Active nav item has solid filled background (not subtle/transparent)
- Section labels ("Portfolio", "Tools") are uppercase with tighter tracking
- Nav items have slightly more vertical padding

---

## Task 3: TopNav Redesign

**Files:**
- Modify: `frontend/components/layout/TopNav.tsx`

- [ ] **Step 1: Replace the entire TopNav component**

Replace the full file content with:

```tsx
"use client";

import { useRef } from "react";
import { Eye, EyeOff, LogOut, Sun, Moon, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { usePaletteStore } from "@/store/palette";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const { setOpen } = usePaletteStore();
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const toggleRef = useRef<HTMLButtonElement>(null);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  function toggleTheme() {
    if (!resolvedTheme) return;
    const newTheme = resolvedTheme === "dark" ? "light" : "dark";
    const btn = toggleRef.current;
    const rect = btn?.getBoundingClientRect();
    const x = rect ? rect.left + rect.width / 2 : window.innerWidth / 2;
    const y = rect ? rect.top + rect.height / 2 : window.innerHeight / 2;

    document.documentElement.style.setProperty("--vt-x", `${x}px`);
    document.documentElement.style.setProperty("--vt-y", `${y}px`);

    if (!("startViewTransition" in document)) {
      setTheme(newTheme);
      return;
    }

    (document as Document & { startViewTransition: (cb: () => void | Promise<void>) => void })
      .startViewTransition(() => setTheme(newTheme));
  }

  return (
    <header className="h-14 border-b border-[var(--glass-border)] glass-chrome flex items-center px-3 gap-2">
      {/* Search pill */}
      <button
        onClick={() => setOpen(true)}
        className="flex flex-1 items-center gap-2 h-9 px-3 rounded-full bg-muted/60 hover:bg-muted transition-colors text-left min-w-0"
        title="Search (⌘K)"
      >
        <Search className="h-[15px] w-[15px] text-muted-foreground shrink-0" />
        <span className="text-sm text-muted-foreground flex-1 truncate">Search...</span>
        <kbd className="hidden sm:flex items-center text-[11px] text-muted-foreground/60 font-mono bg-background/60 px-1.5 py-0.5 rounded-md border border-border/40 shrink-0">
          ⌘K
        </kbd>
      </button>

      {/* Action buttons */}
      <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" onClick={toggle} title="Toggle privacy mode">
        {isPrivate ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
      </Button>
      <Button
        ref={toggleRef}
        variant="ghost"
        size="icon"
        className="h-9 w-9 shrink-0 relative"
        onClick={toggleTheme}
        title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        <span
          key={resolvedTheme}
          style={{ animation: "icon-spin-in 300ms cubic-bezier(0.16,1,0.3,1) both", display: "flex" }}
        >
          {resolvedTheme === "dark" ? (
            <Sun className="h-[18px] w-[18px]" />
          ) : (
            <Moon className="h-[18px] w-[18px]" />
          )}
        </span>
      </Button>
      <Button variant="ghost" size="icon" className="h-9 w-9 shrink-0" onClick={handleLogout} title="Log out">
        <LogOut className="h-[18px] w-[18px]" />
      </Button>
    </header>
  );
}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep TopNav`
Expected: no output

- [ ] **Step 3: Visually verify header**

In browser at `http://localhost:3000`:
- Header shows a pill-shaped search bar that spans most of the width
- `⌘K` hint badge visible on right side of pill (hidden on very small screens)
- Clicking search pill opens command palette
- Right side: privacy, theme, logout icon buttons
- No page title in header

---

## Task 4: BottomTabBar Restyle

**Files:**
- Modify: `frontend/components/layout/BottomTabBar.tsx`

- [ ] **Step 1: Update active indicator to landscape pill**

Replace the inner `<div>` that wraps the icon (the one with `w-9 h-[26px] rounded-[10px]`) with:

```tsx
<div
  className={cn(
    "flex items-center justify-center w-14 h-[28px] rounded-full",
    "transition-all duration-200",
    isActive ? "bg-foreground/10" : ""
  )}
>
  <Icon
    className="h-[20px] w-[20px] transition-all duration-150"
    strokeWidth={isActive ? 2.25 : 1.5}
  />
</div>
```

The full updated `tabs.map` block should look like:

```tsx
{tabs.map(({ href, label, icon: Icon }) => {
  const isActive = pathname.startsWith(href);
  return (
    <Link
      key={href}
      href={href}
      className={cn(
        "flex-1 flex flex-col items-center justify-center gap-[3px]",
        "rounded-[20px] h-[54px] transition-all duration-200 active:scale-[0.93]",
        isActive ? "text-foreground" : "text-muted-foreground"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center w-14 h-[28px] rounded-full",
          "transition-all duration-200",
          isActive ? "bg-foreground/10" : ""
        )}
      >
        <Icon
          className="h-[20px] w-[20px] transition-all duration-150"
          strokeWidth={isActive ? 2.25 : 1.5}
        />
      </div>
      <span
        className={cn(
          "text-[10px] leading-none tracking-[0.01em] transition-all duration-150",
          isActive ? "font-semibold opacity-100" : "font-medium opacity-50"
        )}
      >
        {label}
      </span>
    </Link>
  );
})}
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep BottomTabBar`
Expected: no output

- [ ] **Step 3: Visually verify on mobile**

Resize browser to mobile width (~375px). Check:
- Active tab shows a wide landscape pill (wider than the icon, shorter than square)
- Inactive tabs have no background
- Outer floating container shape unchanged

---

## Task 5: Add PageHeader to All Pages

**Files:** All pages listed in the File Map above.

**Pattern for each page:**
1. Add import: `import { PageHeader } from "@/components/layout/PageHeader";`
2. Add `<PageHeader title="..." />` as the **first child** inside the page's return statement
3. Remove any existing `<h1>`, `<h2>`, or title `<div>` that duplicates the page title

**Title mapping:**

| File | Title |
|------|-------|
| `app/(auth)/page.tsx` | `"Overview"` |
| `app/(auth)/overview/page.tsx` | `"Overview"` |
| `app/(auth)/portfolio/page.tsx` | `"Portfolio"` |
| `app/(auth)/portfolio/[symbol]/page.tsx` | `"Asset"` |
| `app/(auth)/watchlist/page.tsx` | `"Watchlist"` |
| `app/(auth)/net-worth/page.tsx` | `"Net Worth"` |
| `app/(auth)/events/page.tsx` | `"Events"` |
| `app/(auth)/transactions/page.tsx` | `"Transactions"` |
| `app/(auth)/documents/page.tsx` | `"Documents"` |
| `app/(auth)/pipeline/page.tsx` | `"Pipeline"` |
| `app/(auth)/import/page.tsx` | `"Import"` |
| `app/(auth)/ai-usage/page.tsx` | `"AI Usage"` |
| `app/(auth)/dividends/page.tsx` | `"Dividends"` |
| `app/(auth)/settings/page.tsx` | `"Settings"` |
| `app/(auth)/settings/ai/page.tsx` | `"AI & LLM"` |
| `app/(auth)/settings/backup/page.tsx` | `"Backup"` |

- [ ] **Step 1: Add PageHeader to each page**

For each file in the table above, open the file, add the import at the top, and add `<PageHeader title="..." />` as the first child in the returned JSX. Example pattern:

```tsx
import { PageHeader } from "@/components/layout/PageHeader";

// In the return:
return (
  <div>  {/* or <> or whatever the page wraps with */}
    <PageHeader title="Overview" />
    {/* ... rest of existing page content ... */}
  </div>
);
```

If the page has an existing `<h1>` or top-level title heading, remove it to avoid duplication.

- [ ] **Step 2: Verify no TypeScript errors across all pages**

Run: `cd frontend && npx tsc --noEmit`
Expected: exit 0, no errors

- [ ] **Step 3: Visually spot-check 3 pages**

In browser, navigate to: Overview, Portfolio, Settings.

Each page should show:
- Large bold page title at the top of the content area (not in the header)
- Header shows only the search pill + action buttons (no title)
- No duplicate titles

---

## Final Visual Check

- [ ] Sidebar: active item has solid filled background, section labels are uppercase with tight tracking
- [ ] TopNav: search pill spans width, ⌘K hint visible, no page title
- [ ] Mobile (375px): floating bottom tab bar has landscape pill active indicator
- [ ] All pages: bold title appears at top of content, not header
