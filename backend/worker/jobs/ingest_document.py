import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.document import Document
from app.services.pipeline import create_log, finish_log, create_step, finish_step
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

            current_step = None

            # Step 1: load_document
            current_step = await create_step(db, log.id, "load_document")
            import fitz
            import os
            pdf = fitz.open(doc.file_path)
            full_text = "\n".join(page.get_text() for page in pdf)
            pdf.close()
            file_size = os.path.getsize(doc.file_path) if os.path.exists(doc.file_path) else 0
            await finish_step(db, current_step, success=True, metadata={
                "filename": doc.file_path.split("/")[-1],
                "size_bytes": file_size,
            })

            # Step 2: chunk_text
            current_step = await create_step(db, log.id, "chunk_text")
            chunks = _recursive_chunk(full_text)
            await finish_step(db, current_step, success=True, metadata={"chunks": len(chunks)})

            asset_symbol = None
            if doc.asset_id:
                from app.models.asset import Asset
                a_result = await db.execute(select(Asset).where(Asset.id == doc.asset_id))
                asset = a_result.scalar_one_or_none()
                asset_symbol = asset.symbol if asset else None

            # Step 3: embed_store
            current_step = await create_step(db, log.id, "embed_store")
            collection = get_or_create_collection(asset_symbol)
            metadatas = [
                {"document_id": document_id, "chunk_index": i, "asset_symbol": asset_symbol or "global"}
                for i in range(len(chunks))
            ]
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            add_chunks(collection, chunks, metadatas, ids)
            await finish_step(db, current_step, success=True, metadata={"embedded": len(chunks)})

            doc.status = "done"
            doc.chunk_count = len(chunks)
            doc.chroma_collection_id = collection.name
            await db.commit()

            await finish_log(db, log, success=True)
            logger.info("ingest_document done id=%s chunks=%d", document_id, len(chunks))
            return {"chunks": len(chunks)}
        except Exception as e:
            logger.exception("ingest_document failed id=%s: %s", document_id, e)
            if current_step is not None:
                await finish_step(db, current_step, success=False, error=str(e))
            doc.status = "failed"
            doc.error_msg = str(e)
            await db.commit()
            await finish_log(db, log, success=False, error_message=str(e))
            raise
