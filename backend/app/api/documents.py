import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger(__name__)

def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="general"),
    asset_symbol: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    UPLOAD_DIR = _upload_dir()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4()
    dest = UPLOAD_DIR / f"{doc_id}_{file.filename}"
    content = await file.read()
    dest.write_bytes(content)

    asset_id = None
    if asset_symbol:
        from app.models.asset import Asset
        result = await db.execute(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        asset = result.scalar_one_or_none()
        if asset:
            asset_id = asset.id

    doc = Document(
        id=doc_id,
        filename=file.filename,
        file_path=str(dest),
        asset_id=asset_id,
        status="pending",
    )
    db.add(doc)
    await db.commit()

    # Enqueue ingest job
    try:
        from arq.connections import ArqRedis, RedisSettings, create_pool
        from app.core.config import settings
        redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_ingest_document", str(doc_id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        job_id = None

    logger.info("document uploaded id=%s filename=%s", doc_id, file.filename)
    return {"document_id": str(doc_id), "status": "pending", "job_id": job_id}


@router.get("")
async def list_documents(
    asset: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = select(Document).order_by(Document.created_at.desc())
    if asset:
        from app.models.asset import Asset
        result = await db.execute(select(Asset).where(Asset.symbol == asset.upper()))
        a = result.scalar_one_or_none()
        if a:
            query = query.where(Document.asset_id == a.id)
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "asset_id": str(d.asset_id) if d.asset_id else None,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "error_msg": d.error_msg,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.chroma_collection_id:
        try:
            from app.services.rag_service import _get_client
            client = _get_client()
            client.delete_collection(doc.chroma_collection_id)
        except Exception:
            pass

    if doc.file_path and Path(doc.file_path).exists():
        Path(doc.file_path).unlink()

    await db.delete(doc)
    await db.commit()
    logger.info("document deleted id=%s", doc_id)
    return {"ok": True}


@router.post("/{doc_id}/reingest", status_code=202)
async def reingest_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "pending"
    doc.error_msg = None
    await db.commit()

    try:
        from arq.connections import ArqRedis, RedisSettings, create_pool
        from app.core.config import settings
        redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        job = await redis.enqueue_job("job_ingest_document", str(doc_id))
        await redis.aclose()
        job_id = job.job_id if job else None
    except Exception:
        job_id = None

    return {"ok": True, "job_id": job_id}
