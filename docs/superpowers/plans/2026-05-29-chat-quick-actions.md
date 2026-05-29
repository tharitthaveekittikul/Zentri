# Chat Quick Actions Chips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a horizontally-scrollable row of quick-action chips above the chat input that fill the textarea with pre-written prompts when clicked, including a dynamic "Analyze [TICKER]" chip based on recent conversation context.

**Architecture:** Create a standalone `ChatQuickActions` component that receives the message history and an `onSelect` callback. Fixed chips are always shown; a dynamic ticker chip is derived from the last 5 messages using regex. The component is placed between the message list and the input card in `chat/page.tsx`.

**Tech Stack:** React, TypeScript, Tailwind CSS (design tokens only)

---

## Files

- **Create:** `frontend/components/chat/ChatQuickActions.tsx`
- **Modify:** `frontend/app/(auth)/chat/page.tsx`

---

### Task 1: Create `ChatQuickActions` component

**Files:**
- Create: `frontend/components/chat/ChatQuickActions.tsx`

- [ ] **Step 1: Create the component file**

Create `frontend/components/chat/ChatQuickActions.tsx` with this exact content:

```tsx
"use client";

import { ChatMessageWithMeta } from "@/lib/services/chat";

const STATIC_CHIPS: { label: string; prompt: string }[] = [
  { label: "My portfolio", prompt: "Show my portfolio summary" },
  { label: "My holdings", prompt: "Show my holdings" },
  { label: "My watchlist", prompt: "Show my watchlist" },
  { label: "My cash", prompt: "How much cash do I have?" },
  { label: "Search news", prompt: "Search latest market news" },
];

const TICKER_NOISE = new Set([
  "I", "USD", "THB", "ETF", "IPO", "ATH", "YTD", "OK", "AI", "PL",
  "AND", "OR", "THE", "FOR", "NOT", "ARE", "HAS", "WAS",
]);
const TICKER_RE = /\b([A-Z]{2,5})\b/g;

function extractLatestTicker(messages: ChatMessageWithMeta[]): string | null {
  const last5 = messages.slice(-5);
  for (let i = last5.length - 1; i >= 0; i--) {
    const text = last5[i].content ?? "";
    const matches = [...text.matchAll(TICKER_RE)].map((m) => m[1]);
    const tickers = matches.filter((t) => !TICKER_NOISE.has(t));
    if (tickers.length > 0) return tickers[tickers.length - 1];
  }
  return null;
}

interface ChatQuickActionsProps {
  messages: ChatMessageWithMeta[];
  onSelect: (text: string) => void;
}

export function ChatQuickActions({ messages, onSelect }: ChatQuickActionsProps) {
  const ticker = extractLatestTicker(messages);

  return (
    <div className="flex gap-2 overflow-x-auto scrollbar-hide py-2 px-1 shrink-0">
      {STATIC_CHIPS.map((chip) => (
        <button
          key={chip.label}
          onClick={() => onSelect(chip.prompt)}
          className="border border-border rounded-full px-3 py-1 text-xs whitespace-nowrap text-muted-foreground hover:text-foreground hover:bg-muted transition-colors shrink-0"
        >
          {chip.label}
        </button>
      ))}
      {ticker && (
        <button
          onClick={() => onSelect(`Analyze ${ticker}`)}
          className="border border-primary/20 rounded-full px-3 py-1 text-xs whitespace-nowrap bg-primary/10 text-primary shrink-0 transition-colors"
        >
          Analyze {ticker}
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors related to `ChatQuickActions.tsx`.

---

### Task 2: Wire up in `chat/page.tsx`

**Files:**
- Modify: `frontend/app/(auth)/chat/page.tsx`

- [ ] **Step 1: Add the import**

At the top of `frontend/app/(auth)/chat/page.tsx`, add this import alongside the other component imports:

```tsx
import { ChatQuickActions } from "@/components/chat/ChatQuickActions";
```

- [ ] **Step 2: Add the `handleQuickAction` callback**

Inside `ChatPage`, add this function alongside the other handlers (e.g. after `handleKeyDown`):

```tsx
function handleQuickAction(text: string) {
  setInput(text);
  textareaRef.current?.focus();
}
```

- [ ] **Step 3: Place the component in the layout**

In the JSX return, find this comment block (the bottom fixed section):

```tsx
      <div className="pt-3 pb-4 shrink-0">
```

Insert `<ChatQuickActions>` **immediately before** that div:

```tsx
      <ChatQuickActions messages={messages} onSelect={handleQuickAction} />

      <div className="pt-3 pb-4 shrink-0">
```

- [ ] **Step 4: Verify TypeScript compiles**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

---

### Task 3: Manual verification

- [ ] **Step 1: Start the dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Verify fixed chips**

Open the chat page. Confirm:
- 5 chips are visible in a horizontal row: "My portfolio", "My holdings", "My watchlist", "My cash", "Search news"
- Chips are scrollable horizontally if the screen is narrow
- Clicking any chip fills the textarea with the correct prompt and focuses it
- No chip auto-sends

- [ ] **Step 3: Verify dynamic ticker chip**

Send a message that mentions a stock ticker (e.g. "Tell me about NVTS"). After the AI responds, confirm:
- An "Analyze NVTS" chip appears after the fixed chips with a blue/primary tint
- Clicking it fills the textarea with "Analyze NVTS"
- The chip disappears when starting a new session with no messages

- [ ] **Step 4: Verify dark mode**

Toggle dark mode. Confirm chips use CSS variable colors (no hardcoded hex), contrast is readable, primary tint is visible on the ticker chip.

- [ ] **Step 5: Verify noise word filtering**

Check that sending a message like "I have USD in my portfolio" does NOT produce a chip for "I", "USD", or "IN".
