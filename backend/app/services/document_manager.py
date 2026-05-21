from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import Document

logger = get_logger(__name__)

EDGAR_HEADERS = {"User-Agent": "Zentri contact@zentri.app"}


def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


class DocumentManager:
    async def _download(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url, headers=EDGAR_HEADERS)
            resp.raise_for_status()
            return resp.content

    def _save_file(self, content: bytes, ticker: str, doc_type: str, doc_id: uuid.UUID, filename: str) -> str:
        dest_dir = _upload_dir() / ticker.upper() / doc_type.replace("/", "_")
        dest_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name
        dest = dest_dir / f"{doc_id}_{safe_filename}"
        dest.write_bytes(content)
        return str(dest)

    async def _enqueue_ingest(self, doc_id: uuid.UUID) -> None:
        try:
            from arq.connections import ArqRedis, RedisSettings, create_pool
            from app.core.config import settings
            redis: ArqRedis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
            await redis.enqueue_job("job_ingest_document", str(doc_id))
            await redis.aclose()
        except Exception as e:
            logger.warning("document_manager: failed to enqueue ingest doc_id=%s: %s", doc_id, e)

    async def check_exists(self, source_url: str, db: AsyncSession) -> Document | None:
        result = await db.execute(
            select(Document).where(Document.source_url == source_url)
        )
        return result.scalar_one_or_none()

    async def _check_hash_exists(self, content_hash: str, db: AsyncSession) -> Document | None:
        result = await db.execute(
            select(Document).where(Document.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def pre_fetch(
        self,
        ticker: str,
        asset_id: uuid.UUID | None,
        doc_items: list[dict],
        db: AsyncSession,
    ) -> dict:
        fetched = 0
        skipped = 0
        failed = 0

        for item in doc_items:
            url = item["url"]
            doc_type = item["doc_type"]
            filename = item["filename"]

            existing = await self.check_exists(url, db)
            if existing:
                logger.info("document_manager: skip existing source_url=%s", url)
                skipped += 1
                continue

            try:
                content = await self._download(url)
                content_hash = hashlib.sha256(content).hexdigest()

                hash_existing = await self._check_hash_exists(content_hash, db)
                if hash_existing:
                    logger.info("document_manager: skip duplicate content hash=%s url=%s", content_hash[:8], url)
                    skipped += 1
                    continue

                doc_id = uuid.uuid4()
                file_path = self._save_file(content, ticker, doc_type, doc_id, filename)

                doc = Document(
                    id=doc_id,
                    filename=filename,
                    file_path=file_path,
                    asset_id=asset_id,
                    source_url=url,
                    doc_type=doc_type,
                    content_hash=content_hash,
                    status="pending",
                )
                try:
                    async with db.begin_nested():
                        db.add(doc)
                        await db.flush()
                except IntegrityError:
                    logger.info("document_manager: concurrent duplicate content_hash=%s, skipping", content_hash[:8])
                    skipped += 1
                    continue
                await self._enqueue_ingest(doc_id)
                fetched += 1
                logger.info("document_manager: fetched doc_id=%s url=%s", doc_id, url)
            except Exception as e:
                failed += 1
                logger.warning("document_manager: failed url=%s: %s", url, e)

        if fetched > 0:
            await db.commit()

        return {"fetched": fetched, "skipped": skipped, "failed": failed}
