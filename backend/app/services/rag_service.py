import chromadb
from chromadb import Collection

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)


def get_or_create_collection(asset_symbol: str | None) -> Collection:
    name = (asset_symbol or "global").lower().replace("/", "_").replace("-", "_")
    client = _get_client()
    logger.info("rag get_or_create_collection name=%s", name)
    return client.get_or_create_collection(name=name)


def add_chunks(
    collection: Collection,
    chunks: list[str],
    metadatas: list[dict],
    ids: list[str],
) -> None:
    logger.info("rag add_chunks collection=%s count=%d", collection.name, len(chunks))
    collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)


def search(collection: Collection, query: str, n_results: int = 5) -> list[str]:
    if collection.count() == 0:
        logger.info("rag search collection=%s is empty, skipping", collection.name)
        return []
    n = min(n_results, collection.count())
    results = collection.query(query_texts=[query], n_results=n)
    docs = results.get("documents", [[]])[0]
    logger.info("rag search collection=%s query=%r returned %d chunks", collection.name, query, len(docs))
    return docs
