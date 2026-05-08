from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.services.llm_gateway import LLMGateway

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cost_thb: float
    model: str
    provider: str


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    gateway = LLMGateway(db)
    result = await gateway.complete_chat(current_user.id, messages)
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
