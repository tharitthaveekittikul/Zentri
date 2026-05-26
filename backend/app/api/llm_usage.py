import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.llm_call_log import LLMCallLog
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter(prefix="/llm", tags=["llm-usage"])


@router.get("/call-logs")
async def get_call_logs(
    feature_key: Optional[str] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(LLMCallLog).where(LLMCallLog.user_id == current_user.id)
    if feature_key:
        q = q.where(LLMCallLog.feature_key == feature_key)
    if from_date:
        q = q.where(LLMCallLog.created_at >= from_date)
    if to_date:
        q = q.where(LLMCallLog.created_at <= to_date)

    agg_q = select(
        func.sum(LLMCallLog.cost_usd).label("total_cost_usd"),
        func.sum(LLMCallLog.cost_thb).label("total_cost_thb"),
        func.sum(LLMCallLog.tokens_in).label("total_tokens_in"),
        func.sum(LLMCallLog.tokens_out).label("total_tokens_out"),
        func.count(LLMCallLog.id).label("total_calls"),
    ).where(LLMCallLog.user_id == current_user.id)
    if feature_key:
        agg_q = agg_q.where(LLMCallLog.feature_key == feature_key)
    if from_date:
        agg_q = agg_q.where(LLMCallLog.created_at >= from_date)
    if to_date:
        agg_q = agg_q.where(LLMCallLog.created_at <= to_date)

    logs_result = await db.execute(q.order_by(LLMCallLog.created_at.desc()).limit(limit).offset(offset))
    agg_result = await db.execute(agg_q)
    logs = logs_result.scalars().all()
    agg = agg_result.one()

    return {
        "total_cost_usd": float(agg.total_cost_usd or 0),
        "total_cost_thb": float(agg.total_cost_thb or 0),
        "total_tokens_in": int(agg.total_tokens_in or 0),
        "total_tokens_out": int(agg.total_tokens_out or 0),
        "total_calls": int(agg.total_calls or 0),
        "logs": [
            {
                "id": str(log.id),
                "feature_key": log.feature_key,
                "provider": log.provider,
                "model": log.model,
                "tokens_in": log.tokens_in,
                "tokens_out": log.tokens_out,
                "cost_usd": float(log.cost_usd),
                "cost_thb": float(log.cost_thb),
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/call-logs/{log_id}")
async def get_call_log_detail(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LLMCallLog).where(
            LLMCallLog.id == log_id,
            LLMCallLog.user_id == current_user.id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Log not found")
    return {
        "id": str(log.id),
        "feature_key": log.feature_key,
        "provider": log.provider,
        "model": log.model,
        "tokens_in": log.tokens_in,
        "tokens_out": log.tokens_out,
        "cost_usd": float(log.cost_usd),
        "cost_thb": float(log.cost_thb),
        "created_at": log.created_at.isoformat(),
        "prompt_in": log.prompt_in,
        "response_out": log.response_out,
        "tool_rounds": log.tool_rounds,
    }
