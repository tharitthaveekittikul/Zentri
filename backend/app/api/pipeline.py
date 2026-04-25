import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.schemas.pipeline import JobType, PipelineLogResponse
from app.services import auth as auth_service
from app.services.pipeline import get_log, list_logs

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_bearer = HTTPBearer(auto_error=False)


async def _get_user_for_sse(
    token: str | None = Query(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Accept JWT from Bearer header OR ?token= query param (for SSE/EventSource)."""
    raw = token or (credentials.credentials if credentials else None)
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    import uuid as _uuid
    user = await auth_service.get_user_by_id(db, _uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/jobs", response_model=list[PipelineLogResponse])
async def list_pipeline_jobs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return recent pipeline job logs, newest first."""
    return await list_logs(db, limit=limit)


@router.get("/jobs/{log_id}", response_model=PipelineLogResponse)
async def get_pipeline_job(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    log = await get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Job not found")
    return log


@router.post("/trigger/{job_type}", status_code=202)
async def trigger_job(
    job_type: JobType,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Enqueue a job via ARQ for immediate execution."""
    from arq.connections import ArqRedis, create_pool, RedisSettings
    from app.core.config import settings

    redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    job_fn_map = {
        "price_fetch_us": "job_fetch_prices_us",
        "price_fetch_crypto": "job_fetch_prices_crypto",
        "price_fetch_gold": "job_fetch_price_gold",
        "price_fetch_benchmark": "job_fetch_benchmark_prices",
    }
    fn_name = job_fn_map[job_type]
    job = await redis.enqueue_job(fn_name)
    await redis.aclose()
    return {"enqueued": True, "job_id": job.job_id if job else None}


@router.get("/stream")
async def pipeline_stream(
    _: User = Depends(_get_user_for_sse),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream — pushes latest 20 job statuses every 3 seconds."""

    async def event_generator():
        while True:
            logs = await list_logs(db, limit=20)
            data = [
                {
                    "id": str(log.id),
                    "job_type": log.job_type,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                    "error_message": log.error_message,
                }
                for log in logs
            ]
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
