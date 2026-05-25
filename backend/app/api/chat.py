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
    tool_calls: list[dict]


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
    tool_calls: Optional[list[dict]] = None
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
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=str(session.id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
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
    await db.delete(session)
    await db.commit()


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
            tool_calls=m.tool_calls,
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
        tool_calls=result.tool_calls or None,
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
        tool_calls=result.tool_calls,
    )
