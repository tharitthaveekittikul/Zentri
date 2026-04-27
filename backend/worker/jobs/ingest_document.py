import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.document import Document
from app.services.pipeline import create_log, finish_log
from app.services.rag_service import add_chunks, get_or_create_collection

logger = get_logger(__name__)


def _recursive_chunk(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


async def job_ingest_document(ctx: dict, document_id: str) -> dict:
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "ingest_document")
        doc_uuid = uuid.UUID(document_id)
        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            await finish_log(db, log, success=False, error_message=f"Document {document_id} not found")
            return {"error": "not found"}
        try:
            doc.status = "processing"
            await db.commit()

            import fitz
            pdf = fitz.open(doc.file_path)
            full_text = "\n".join(page.get_text() for page in pdf)
            pdf.close()

            chunks = _recursive_chunk(full_text)

            asset_symbol = None
            if doc.asset_id:
                from app.models.asset import Asset
                a_result = await db.execute(select(Asset).where(Asset.id == doc.asset_id))
                asset = a_result.scalar_one_or_none()
                asset_symbol = asset.symbol if asset else None

            collection = get_or_create_collection(asset_symbol)
            metadatas = [
                {"document_id": document_id, "chunk_index": i, "asset_symbol": asset_symbol or "global"}
                for i in range(len(chunks))
            ]
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            add_chunks(collection, chunks, metadatas, ids)

            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.chroma_collection_id = collection.name
            await db.commit()

            await finish_log(db, log, success=True)
            logger.info("ingest_document done id=%s chunks=%d", document_id, len(chunks))
            return {"chunks": len(chunks)}
        except Exception as e:
            logger.exception("ingest_document failed id=%s: %s", document_id, e)
            doc.status = "failed"
            doc.error_msg = str(e)
            await db.commit()
            await finish_log(db, log, success=False, error_message=str(e))
            raise
