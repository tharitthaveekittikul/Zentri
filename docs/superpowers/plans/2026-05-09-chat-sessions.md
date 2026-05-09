# Chat Sessions + Per-Message Token Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent chat sessions with per-message token/cost metadata and a session strip navigation to the Chat page.

**Architecture:** Backend adds two new tables (`chat_sessions`, `chat_session_messages`) and new REST endpoints under `/api/v1/chat/sessions`; the existing `POST /api/v1/chat` is extended to accept a `session_id` and persist every message+response. Frontend adds a `SessionStrip` component, a per-message `MessageMetaRow`, and an enhanced session-total footer badge.

**Tech Stack:** FastAPI + SQLAlchemy async + PostgreSQL (Alembic migrations), Next.js App Router + TypeScript, Tailwind CSS, shadcn/ui components.

**Spec:** `docs/superpowers/specs/2026-05-09-chat-sessions-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/app/models/chat_session.py` | Create | `ChatSession` + `ChatSessionMessage` SQLAlchemy models |
| `backend/alembic/versions/035_add_chat_sessions.py` | Create | DB migration for the two new tables |
| `backend/alembic/env.py` | Modify | Import new model so Alembic detects it |
| `backend/app/api/chat.py` | Modify | Session CRUD endpoints + updated `POST /chat` |
| `backend/tests/test_chat_sessions.py` | Create | Integration tests for session endpoints |
| `frontend/lib/services/chat.ts` | Modify | New types + service functions for sessions |
| `frontend/components/llm/ChatCostBadge.tsx` | Modify | Add token totals display |
| `frontend/components/chat/SessionStrip.tsx` | Create | Horizontal session strip with inline rename |
| `frontend/app/(auth)/chat/page.tsx` | Modify | Wire session strip, metadata rows, updated footer |

---

## Task 1: Backend DB Models

**Files:**
- Create: `backend/app/models/chat_session.py`

- [ ] **Step 1: Create the model file**

```python
# backend/app/models/chat_session.py
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ChatSessionMessage(Base):
    __tablename__ = "chat_session_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    cost_thb: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/035_add_chat_sessions.py`
- Modify: `backend/alembic/env.py`

- [ ] **Step 1: Create migration file**

```python
# backend/alembic/versions/035_add_chat_sessions.py
"""add chat_sessions and chat_session_messages tables

Revision ID: 035
Revises: 034
Create Date: 2026-05-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])

    op.create_table(
        "chat_session_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("cost_thb", sa.Numeric(10, 6), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_session_messages_session_id",
        "chat_session_messages",
        ["session_id"],
    )
    op.create_index(
        "ix_chat_session_messages_created_at",
        "chat_session_messages",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_session_messages_created_at", table_name="chat_session_messages")
    op.drop_index("ix_chat_session_messages_session_id", table_name="chat_session_messages")
    op.drop_table("chat_session_messages")
    op.drop_index("ix_chat_sessions_updated_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
```

- [ ] **Step 2: Register model in Alembic env.py**

Open `backend/alembic/env.py`. After the existing model imports, add:

```python
from app.models import chat_session  # noqa: F401
```

- [ ] **Step 3: Run migration**

```bash
cd backend
docker compose exec backend alembic upgrade head
```

Expected: `Running upgrade 034 -> 035, add chat_sessions and chat_session_messages tables`

---

## Task 3: Backend Session Endpoints

**Files:**
- Modify: `backend/app/api/chat.py`

Replace the entire file with the following (preserves existing `chat` endpoint, adds session routes):

- [ ] **Step 1: Write the failing test first** (see Task 5 — write tests before this step, run them first)

- [ ] **Step 2: Update `backend/app/api/chat.py`**

```python
# backend/app/api/chat.py
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.chat_session import ChatSession, ChatSessionMessage
from app.models.user import User
from app.services.llm_gateway import LLMGateway

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str


class ChatResponse(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    model: str
    provider: str


class CreateSessionRequest(BaseModel):
    title: str


class RenameSessionRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    cost_thb: Optional[float] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime


# ── Session endpoints ──────────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(20)
    )
    sessions = result.scalars().all()
    return [
        SessionResponse(
            id=str(s.id),
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    title = (body.title or "New Chat")[:60]
    session = ChatSession(user_id=current_user.id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == uuid.UUID(session_id),
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = (body.title or "Chat")[:60]
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ownership = await db.execute(
        select(ChatSession).where(
            ChatSession.id == uuid.UUID(session_id),
            ChatSession.user_id == current_user.id,
        )
    )
    if not ownership.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatSessionMessage)
        .where(ChatSessionMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatSessionMessage.created_at.asc())
    )
    msgs = result.scalars().all()
    return [
        MessageResponse(
            id=str(m.id),
            role=m.role,
            content=m.content,
            tokens_in=m.tokens_in,
            tokens_out=m.tokens_out,
            cost_usd=float(m.cost_usd) if m.cost_usd is not None else None,
            cost_thb=float(m.cost_thb) if m.cost_thb is not None else None,
            model=m.model,
            provider=m.provider,
            created_at=m.created_at,
        )
        for m in msgs
    ]


# ── Chat endpoint ──────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == uuid.UUID(body.session_id),
            ChatSession.user_id == current_user.id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = ChatSessionMessage(
        session_id=session.id,
        role="user",
        content=body.messages[-1].content,
    )
    db.add(user_msg)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    gateway = LLMGateway(db)
    result = await gateway.complete_chat(current_user.id, messages)

    assistant_msg = ChatSessionMessage(
        session_id=session.id,
        role="assistant",
        content=result.content,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        cost_thb=result.cost_thb,
        model=result.model,
        provider=result.provider,
    )
    db.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return ChatResponse(
        content=result.content,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost_usd=result.cost_usd,
        cost_thb=result.cost_thb,
        model=result.model,
        provider=result.provider,
    )
```

---

## Task 4: Backend Tests

**Files:**
- Create: `backend/tests/test_chat_sessions.py`

Note: Tests use a real test PostgreSQL DB (see `TEST_DB_URL` in `tests/test_auth.py`). Run the test DB migration before running these tests.

- [ ] **Step 1: Create test file**

```python
# backend/tests/test_chat_sessions.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:zentri-password-paotharit@localhost:5432/zentri_test"


@pytest.fixture
async def setup_test_db():
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(setup_test_db):
    engine = setup_test_db
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_token(client):
    await client.post("/api/v1/auth/setup", json={"username": "admin", "password": "pw123"})
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "pw123"})
    return r.json()["access_token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.mark.asyncio
async def test_create_session_returns_id_and_title(client, headers):
    r = await client.post(
        "/api/v1/chat/sessions",
        json={"title": "What's my portfolio worth?"},
        headers=headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"]
    assert data["title"] == "What's my portfolio worth?"


@pytest.mark.asyncio
async def test_create_session_truncates_long_title(client, headers):
    long_title = "x" * 100
    r = await client.post(
        "/api/v1/chat/sessions",
        json={"title": long_title},
        headers=headers,
    )
    assert r.status_code == 201
    assert len(r.json()["title"]) == 60


@pytest.mark.asyncio
async def test_list_sessions_returns_most_recent_first(client, headers):
    await client.post("/api/v1/chat/sessions", json={"title": "First"}, headers=headers)
    await client.post("/api/v1/chat/sessions", json={"title": "Second"}, headers=headers)
    r = await client.get("/api/v1/chat/sessions", headers=headers)
    assert r.status_code == 200
    titles = [s["title"] for s in r.json()]
    assert titles[0] == "Second"


@pytest.mark.asyncio
async def test_rename_session(client, headers):
    create_r = await client.post(
        "/api/v1/chat/sessions", json={"title": "Old Title"}, headers=headers
    )
    session_id = create_r.json()["id"]
    r = await client.patch(
        f"/api/v1/chat/sessions/{session_id}",
        json={"title": "New Title"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_get_messages_empty_for_new_session(client, headers):
    create_r = await client.post(
        "/api/v1/chat/sessions", json={"title": "Empty"}, headers=headers
    )
    session_id = create_r.json()["id"]
    r = await client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_session_not_found_returns_404(client, headers):
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.get(f"/api/v1/chat/sessions/{fake_id}/messages", headers=headers)
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests**

```bash
cd backend
python -m pytest tests/test_chat_sessions.py -v
```

Expected: All 6 tests PASS.

---

## Task 5: Frontend Service Functions

**Files:**
- Modify: `frontend/lib/services/chat.ts`

- [ ] **Step 1: Replace `frontend/lib/services/chat.ts`**

```typescript
// frontend/lib/services/chat.ts
import { api } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatMessageWithMeta extends ChatMessage {
  id?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  cost_thb?: number;
  model?: string;
  provider?: string;
}

export interface ChatResponse {
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  model: string;
  provider: string;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const r = await api.get("/api/v1/chat/sessions");
  if (!r.ok) return [];
  return r.json();
}

export async function createChatSession(title: string): Promise<{ id: string }> {
  const r = await api.post("/api/v1/chat/sessions", { title: title.slice(0, 60) });
  return r.json();
}

export async function renameChatSession(id: string, title: string): Promise<void> {
  await api.patch(`/api/v1/chat/sessions/${id}`, { title });
}

export async function getChatMessages(sessionId: string): Promise<ChatMessageWithMeta[]> {
  const r = await api.get(`/api/v1/chat/sessions/${sessionId}/messages`);
  if (!r.ok) return [];
  return r.json();
}

export async function sendChatMessage(
  sessionId: string,
  messages: ChatMessage[],
): Promise<ChatResponse> {
  const r = await api.post("/api/v1/chat", { messages, session_id: sessionId });
  return r.json();
}
```

---

## Task 6: Enhanced ChatCostBadge

**Files:**
- Modify: `frontend/components/llm/ChatCostBadge.tsx`

The badge now shows session-level token totals (sum of all assistant messages) in addition to cost.

- [ ] **Step 1: Replace `frontend/components/llm/ChatCostBadge.tsx`**

```tsx
// frontend/components/llm/ChatCostBadge.tsx
"use client";

import { CoinsIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionCost {
  costUsd: number;
  costThb?: number;
  messageCount: number;
  tokensIn?: number;
  tokensOut?: number;
}

interface ChatCostBadgeProps {
  session: SessionCost;
  className?: string;
}

export function ChatCostBadge({ session, className }: ChatCostBadgeProps) {
  if (session.messageCount === 0) return null;

  const formatUsd = (usd: number) =>
    usd < 0.001 ? "< $0.001" : `$${usd.toFixed(3)}`;

  const formatThb = (thb: number) =>
    thb < 0.1 ? "< ฿0.10" : `฿${thb.toFixed(2)}`;

  const formatTokens = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border bg-muted/60 px-2.5 py-1 text-[11px] text-muted-foreground",
        className,
      )}
    >
      <CoinsIcon className="size-3 text-amber-500 shrink-0" />
      {session.tokensIn !== undefined && session.tokensOut !== undefined && (
        <span className="text-muted-foreground/70">
          ↑{formatTokens(session.tokensIn)} ↓{formatTokens(session.tokensOut)} ·
        </span>
      )}
      <span>
        {formatUsd(session.costUsd)}
        {session.costThb !== undefined && session.costThb > 0
          ? ` / ${formatThb(session.costThb)}`
          : ""}
      </span>
      <span className="text-muted-foreground/60">· {session.messageCount} msg</span>
    </div>
  );
}
```

---

## Task 7: SessionStrip Component

**Files:**
- Create: `frontend/components/chat/SessionStrip.tsx`

- [ ] **Step 1: Create `frontend/components/chat/SessionStrip.tsx`**

```tsx
// frontend/components/chat/SessionStrip.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { PlusIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { renameChatSession } from "@/lib/services/chat";
import type { ChatSessionSummary } from "@/lib/services/chat";

interface SessionStripProps {
  sessions: ChatSessionSummary[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onSessionRenamed: (id: string, title: string) => void;
}

function SessionChip({
  session,
  isActive,
  onSelect,
  onRename,
}: {
  session: ChatSessionSummary;
  isActive: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function handleDoubleClick() {
    setDraft(session.title);
    setEditing(true);
  }

  function handleSave() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== session.title) {
      onRename(trimmed);
    }
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") setEditing(false);
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className="h-7 max-w-[160px] rounded-full border border-ring bg-background px-3 text-xs outline-none"
      />
    );
  }

  return (
    <button
      onClick={onSelect}
      onDoubleClick={handleDoubleClick}
      title="Double-click to rename"
      className={cn(
        "h-7 max-w-[160px] shrink-0 rounded-full border px-3 text-xs transition-colors truncate",
        isActive
          ? "border-primary bg-primary/10 text-primary font-medium"
          : "border-border bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {session.title}
    </button>
  );
}

export function SessionStrip({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onSessionRenamed,
}: SessionStripProps) {
  async function handleRename(id: string, title: string) {
    await renameChatSession(id, title);
    onSessionRenamed(id, title);
  }

  return (
    <div className="flex items-center gap-2 overflow-x-auto py-2 px-1 scrollbar-none border-b">
      <button
        onClick={onNewChat}
        className="flex h-7 shrink-0 items-center gap-1 rounded-full border border-border bg-muted/40 px-3 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
      >
        <PlusIcon className="size-3" />
        New
      </button>
      {sessions.map((s) => (
        <SessionChip
          key={s.id}
          session={s}
          isActive={s.id === activeSessionId}
          onSelect={() => onSelectSession(s.id)}
          onRename={(title) => handleRename(s.id, title)}
        />
      ))}
    </div>
  );
}
```

---

## Task 8: Chat Page Integration

**Files:**
- Modify: `frontend/app/(auth)/chat/page.tsx`

This is the largest change — rewires the page to use sessions, adds the `SessionStrip`, `MessageMetaRow`, and updated footer.

- [ ] **Step 1: Replace `frontend/app/(auth)/chat/page.tsx`**

```tsx
// frontend/app/(auth)/chat/page.tsx
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { SendIcon, BotIcon, UserIcon, AlertCircleIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ChatMessageWithMeta,
  sendChatMessage,
  listChatSessions,
  createChatSession,
  getChatMessages,
  ChatSessionSummary,
} from "@/lib/services/chat";
import { ChatCostBadge } from "@/components/llm/ChatCostBadge";
import { SessionStrip } from "@/components/chat/SessionStrip";

const OUT_OF_SCOPE_TYPE = "out_of_scope";

function isOutOfScope(content: string): boolean {
  try {
    const obj = JSON.parse(content);
    return obj?.type === OUT_OF_SCOPE_TYPE;
  } catch {
    return false;
  }
}

function MessageMetaRow({ msg }: { msg: ChatMessageWithMeta }) {
  if (msg.role !== "assistant" || msg.tokens_in == null) return null;
  if (isOutOfScope(msg.content)) return null;

  const formatTokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
  const formatCost = (usd?: number, thb?: number) => {
    if (usd == null) return "";
    const usdStr = usd < 0.001 ? "< $0.001" : `$${usd.toFixed(3)}`;
    const thbStr = thb && thb > 0 ? ` / ฿${thb.toFixed(2)}` : "";
    return `${usdStr}${thbStr}`;
  };

  return (
    <div className="ml-10 mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground/60">
      <span>
        ↑{formatTokens(msg.tokens_in!)} ↓{formatTokens(msg.tokens_out ?? 0)}
      </span>
      <span>·</span>
      <span>{formatCost(msg.cost_usd, msg.cost_thb)}</span>
      {msg.model && (
        <>
          <span>·</span>
          <span>{msg.model}</span>
        </>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessageWithMeta }) {
  const isUser = message.role === "user";
  const outOfScope = !isUser && isOutOfScope(message.content);
  const displayContent = outOfScope
    ? "That's outside my scope. I can only help with finance and investment questions — try asking about your portfolio, a stock, or market trends."
    : message.content;

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full mt-0.5",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
      >
        {isUser ? <UserIcon className="size-3.5" /> : <BotIcon className="size-3.5" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-primary text-primary-foreground rounded-tr-sm"
            : outOfScope
              ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 rounded-tl-sm"
              : "bg-muted text-foreground rounded-tl-sm",
        )}
      >
        {displayContent}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageWithMeta[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const sessionCost = {
    costUsd: messages.reduce((s, m) => s + (m.cost_usd ?? 0), 0),
    costThb: messages.reduce((s, m) => s + (m.cost_thb ?? 0), 0),
    messageCount: messages.filter((m) => m.role === "assistant").length,
    tokensIn: messages.reduce((s, m) => s + (m.tokens_in ?? 0), 0),
    tokensOut: messages.reduce((s, m) => s + (m.tokens_out ?? 0), 0),
  };

  useEffect(() => {
    listChatSessions().then((s) => {
      setSessions(s);
      if (s.length > 0) loadSession(s[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function loadSession(id: string) {
    setActiveSessionId(id);
    setMessages([]);
    setError(null);
    const msgs = await getChatMessages(id);
    setMessages(msgs);
  }

  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setError(null);
  }

  function handleSessionRenamed(id: string, title: string) {
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title } : s)));
  }

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    let sessionId = activeSessionId;

    if (!sessionId) {
      const created = await createChatSession(text);
      sessionId = created.id;
      setActiveSessionId(sessionId);
      const newSession: ChatSessionSummary = {
        id: sessionId,
        title: text.slice(0, 60),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setSessions((prev) => [newSession, ...prev]);
    }

    const userMessage: ChatMessageWithMeta = { role: "user", content: text };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const result = await sendChatMessage(sessionId, updatedMessages);
      const assistantMessage: ChatMessageWithMeta = {
        role: "assistant",
        content: result.content,
        tokens_in: result.tokens_in,
        tokens_out: result.tokens_out,
        cost_usd: result.cost_usd,
        cost_thb: result.cost_thb,
        model: result.model,
        provider: result.provider,
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId ? { ...s, updated_at: new Date().toISOString() } : s,
        ),
      );
    } catch (e) {
      setError((e as Error).message ?? "Something went wrong. Try again.");
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }, [input, loading, messages, activeSessionId]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-3xl mx-auto">
      <PageHeader title="Chat" />

      <SessionStrip
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={loadSession}
        onNewChat={handleNewChat}
        onSessionRenamed={handleSessionRenamed}
      />

      <div className="flex-1 overflow-y-auto py-4 space-y-1 px-1">
        {messages.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center text-muted-foreground pb-16">
            <BotIcon className="size-10 opacity-30" />
            <div>
              <p className="font-medium text-foreground">Finance Assistant</p>
              <p className="text-sm mt-1">
                Ask about your portfolio, holdings, market performance, or specific stocks.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 text-sm">
              {[
                "What's my portfolio worth?",
                "Which holdings have the best returns?",
                "How much cash do I have?",
                "What's on my watchlist?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="rounded-xl border border-border px-3 py-2 text-left text-sm hover:bg-muted transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className="space-y-0.5">
            <MessageBubble message={msg} />
            <MessageMetaRow msg={msg} />
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted mt-0.5">
              <BotIcon className="size-3.5 text-muted-foreground" />
            </div>
            <div className="bg-muted rounded-2xl rounded-tl-sm px-4 py-3">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 rounded-xl px-4 py-2.5">
            <AlertCircleIcon className="size-4 shrink-0" />
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="border-t bg-background py-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 max-h-40 overflow-y-auto"
            placeholder="Ask about your portfolio..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <Button
            size="sm"
            disabled={!input.trim() || loading}
            onClick={handleSend}
            className="h-9 w-9 p-0 rounded-xl shrink-0"
          >
            <SendIcon className="size-4" />
          </Button>
        </div>
        <div className="flex items-center justify-between mt-1.5 px-1">
          <p className="text-[11px] text-muted-foreground">
            Finance topics only — portfolio, investments, markets. Press Enter to send.
          </p>
          <ChatCostBadge session={sessionCost} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the page compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: No errors.

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - Persistent sessions stored in DB ✓ (Tasks 1–3)
  - Session strip with auto-title + inline rename ✓ (Task 7, 8)
  - Per-message token/cost metadata ✓ (`MessageMetaRow` in Task 8)
  - Session total in footer ✓ (`ChatCostBadge` in Task 6, derived from `messages` in Task 8)
  - AI Usage page unchanged ✓ (not touched)
  - `sendChatMessage` signature updated to include `session_id` ✓ (Task 5)
- [x] **Type consistency:** `ChatMessageWithMeta` defined in Task 5, used in Tasks 6–8. `ChatSessionSummary` defined in Task 5, used in Tasks 7–8. `SessionResponse`/`MessageResponse` defined in Task 3 backend Pydantic models, matched by frontend types.
- [x] **No placeholders:** All code is complete.
