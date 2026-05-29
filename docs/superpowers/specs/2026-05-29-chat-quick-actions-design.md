# Chat Quick Actions Chips — Design Spec

**Date:** 2026-05-29
**Status:** Approved

## Problem

The AI chat has tool triggers (get_holdings, get_portfolio_summary, etc.) that require the user to know the right phrasing. Users sometimes type the wrong thing and the model skips tools or gives evasive responses. There is no discoverable shortcut to the most common queries.

## Solution

A horizontally-scrollable row of quick-action chips, always visible above the chat input box. Clicking a chip fills the textarea with a pre-written prompt (no auto-send). A dynamic chip appears when a stock ticker is detected in recent conversation context.

---

## Architecture

### New file
`frontend/components/chat/ChatQuickActions.tsx`

### Modified file
`frontend/app/(auth)/chat/page.tsx` — insert `<ChatQuickActions>` between the message list and the input card.

---

## Component: `ChatQuickActions`

### Props
```ts
interface ChatQuickActionsProps {
  messages: ChatMessageWithMeta[];
  onSelect: (text: string) => void;
}
```

### Fixed chips (always shown, in this order)

| Label | Prompt injected into textarea |
|-------|-------------------------------|
| My portfolio | "Show my portfolio summary" |
| My holdings | "Show my holdings" |
| My watchlist | "Show my watchlist" |
| My cash | "How much cash do I have?" |
| Search news | "Search latest market news" |

### Dynamic ticker chip

- Scan the last 5 messages (all roles) for uppercase 2–5 letter words
- Regex: `\b[A-Z]{2,5}\b`
- Exclude noise words: `I`, `USD`, `THB`, `THB`, `ETF`, `IPO`, `ATH`, `YTD`, `P&L`, `OK`, `AI`
- Take the **most recently mentioned** unique match
- Render chip: `Analyze [TICKER]` with prompt `"Analyze [TICKER]"`
- Chip disappears when no ticker found in last 5 messages
- Chip appears **after** the fixed chips, visually distinguished

### Behavior
- Click → call `onSelect(prompt)` → sets `input` state in parent → focuses textarea
- No auto-send; user can review and edit before sending

---

## Placement in `chat/page.tsx`

```
[ message list ]
[ ChatQuickActions row ]   ← new
[ input card (textarea + send) ]
```

The component sits outside the scrollable message list, in the fixed bottom section alongside the input card.

---

## Styling

- Container: `flex gap-2 overflow-x-auto scrollbar-hide py-2 px-1 shrink-0`
- Fixed chips: `border border-border rounded-full px-3 py-1 text-xs whitespace-nowrap text-muted-foreground hover:text-foreground hover:bg-muted transition-colors`
- Ticker chip: same base styles + `bg-primary/10 text-primary border-primary/20` to distinguish
- No hardcoded colors — all values from `globals.css` tokens

---

## Out of Scope

- Auto-send on chip click
- Server-side suggested actions in the API response
- More than one dynamic ticker chip at a time
- Persisting chip state across sessions
