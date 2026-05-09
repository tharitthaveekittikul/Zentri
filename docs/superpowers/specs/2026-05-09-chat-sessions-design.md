# Chat Sessions + Per-Message Token Usage Design

**Date:** 2026-05-09
**Status:** Approved

## Overview

Upgrade the Chat page with three features:
1. Persistent chat sessions stored in the DB (with session strip navigation)
2. Per-message token/cost metadata displayed inline under each assistant response
3. Active session total tokens + cost shown in the footer

The AI Usage page remains unchanged.

---

## Backend

### New DB Models

**`chat_session`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users | |
| title | varchar(100) | First user message, truncated to 60 chars |
| created_at | timestamp | |
| updated_at | timestamp | |

**`chat_message`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| session_id | UUID FK → chat_session | |
| role | varchar(10) | "user" or "assistant" |
| content | text | |
| tokens_in | int | null for user messages |
| tokens_out | int | null for user messages |
| cost_usd | numeric | null for user messages |
| cost_thb | numeric | null for user messages |
| model | varchar(100) | null for user messages |
| provider | varchar(50) | null for user messages |
| created_at | timestamp | |

### New API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/chat/sessions` | List user's sessions (id, title, created_at, updated_at), ordered by updated_at desc, limit 20 |
| POST | `/api/v1/chat/sessions` | Create new session — accepts `title: str` (first user message text truncated to 60 chars), returns `{ id: string }` |
| PATCH | `/api/v1/chat/sessions/{id}` | Rename session title (user-initiated) |
| GET | `/api/v1/chat/sessions/{id}/messages` | Load all messages for a session, ordered by created_at asc |

### Modified Endpoint

`POST /api/v1/chat` gains a required `session_id: str` param. On each call:
1. Saves the incoming user message to `chat_message`
2. Runs the LLM as today
3. Saves the assistant response with token/cost metadata to `chat_message`
4. Updates `chat_session.updated_at`
5. Returns `ChatResponse` unchanged

Session title is set once: when `session_id` is first created, the title = first user message text, truncated to 60 chars.

---

## Frontend

### New Types (extend `lib/services/chat.ts`)

```ts
interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatMessageWithMeta extends ChatMessage {
  id?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  cost_thb?: number;
  model?: string;
  provider?: string;
}
```

### New Service Functions

- `listChatSessions(): Promise<ChatSessionSummary[]>`
- `createChatSession(title: string): Promise<{ id: string }>`
- `renameChatSession(id, title): Promise<void>`
- `getChatMessages(sessionId): Promise<ChatMessageWithMeta[]>`
- `sendChatMessage(sessionId, messages): Promise<ChatResponse>` — adds `session_id` to request body

### Page Structure (`app/(auth)/chat/page.tsx`)

```
┌─ SessionStrip ──────────────────────────────────┐
│ [+ New]  [Session 1 ▸]  [Session 2]  [Session 3] │
└──────────────────────────────────────────────────┘
┌─ Messages area (flex-1 overflow-y-auto) ─────────┐
│  [User bubble]                                    │
│  [Assistant bubble]                               │
│    ↑234 ↓89 · $0.001 / ฿0.03 · gemini-flash      │
│  ...                                              │
└──────────────────────────────────────────────────┘
┌─ Footer ─────────────────────────────────────────┐
│  [textarea]                      [Send]           │
│  Finance topics only...  [Session: ↑1.2k ↓340 · $0.004] │
└──────────────────────────────────────────────────┘
```

### SessionStrip Component (`components/chat/SessionStrip.tsx`)

- Horizontally scrollable row, `overflow-x-auto`
- "+ New" button on the left
- Each session chip: title (max ~35 chars, truncated with ellipsis), active chip has a highlighted border/background
- Click chip → load session
- Double-click chip title (or single-click active chip title) → inline editable input, blur/Enter saves via PATCH API

### MessageMetaRow Component

Rendered below each assistant `MessageBubble` when `tokens_in` is present:

```
↑234 ↓89 · $0.001 / ฿0.03 · gemini-flash
```

- `text-[10px] text-muted-foreground/70`, left-aligned under the bubble (matching bubble indent)
- Hidden for user messages and out-of-scope responses
- Note: `tokens_in` = total LLM input tokens for that call (full conversation history sent), not just the single message

### Session Total in Footer

Replace `ChatCostBadge` with an enhanced badge that shows:
- Total tokens in/out for the session (sum across all assistant messages)
- Total cost USD / THB
- Message count

### State on Page Load

1. Fetch `listChatSessions()`
2. If sessions exist → load the most recent one (fetch messages, set as active)
3. If no sessions → show empty state (current Finance Assistant welcome screen)

### Session Lifecycle

- "New Chat" clicked → set `activeSessionId = null`, clear messages, show empty state
- User sends first message → call `createChatSession(firstMessageText)` to create session with title already set, then `sendChatMessage(sessionId, messages)`
- Switching sessions → fetch messages for selected session, replace messages state
- All subsequent sends → use active `sessionId`

---

## Files to Create / Modify

**Backend:**
- `backend/app/models/chat_session.py` — new SQLAlchemy models
- `backend/alembic/versions/XXXX_add_chat_sessions.py` — migration
- `backend/app/api/chat.py` — add session endpoints, modify POST /chat

**Frontend:**
- `frontend/lib/services/chat.ts` — extend types + add service functions
- `frontend/components/chat/SessionStrip.tsx` — new component
- `frontend/app/(auth)/chat/page.tsx` — integrate session strip, metadata rows, updated footer
- `frontend/components/llm/ChatCostBadge.tsx` — extend to show token totals

---

## Out of Scope

- Pagination of session list (limit 20 most recent is sufficient)
- Search across sessions
- Deleting sessions
- Multi-device sync beyond what DB storage provides
