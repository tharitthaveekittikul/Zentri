from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news_article import NewsArticle
from app.services.rag_service import add_chunks, get_or_create_collection, search

logger = get_logger(__name__)

CACHE_TTL_HOURS = 6
NEWS_COLLECTION = "finance_news"
MAX_NEWS_PER_SYMBOL = 10


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


async def _is_cache_fresh(db: AsyncSession, symbol: str | None) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS)
    result = await db.execute(
        select(NewsArticle)
        .where(
            NewsArticle.symbol == symbol,
            NewsArticle.fetched_at >= cutoff,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _fetch_from_yfinance(symbol: str) -> list[dict[str, Any]]:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []
        articles = []
        for item in raw_news[:MAX_NEWS_PER_SYMBOL]:
            content = item.get("content", {})
            title = content.get("title", "")
            summary = content.get("summary") or content.get("description") or ""
            url = content.get("canonicalUrl", {})
            if isinstance(url, dict):
                url = url.get("url", "")
            pub_date = content.get("pubDate")
            published_at = None
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except ValueError:
                    pass
            provider = content.get("provider", {})
            source = provider.get("displayName", "") if isinstance(provider, dict) else str(provider)
            if title and url:
                articles.append({
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "source": source,
                    "published_at": published_at,
                })
        return articles
    except Exception as exc:
        logger.warning("yfinance news fetch failed for %s: %s", symbol, exc)
        return []


async def fetch_and_index_news(db: AsyncSession, symbol: str) -> list[NewsArticle]:
    if await _is_cache_fresh(db, symbol):
        logger.info("News cache fresh for symbol=%s, skipping fetch", symbol)
        return []

    articles = _fetch_from_yfinance(symbol)
    if not articles:
        return []

    collection = get_or_create_collection(f"news_{symbol.lower()}")
    new_records: list[NewsArticle] = []
    chunks: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for art in articles:
        art_id = _article_id(art["url"])
        text = f"{art['title']}\n\n{art['summary']}"
        chunks.append(text)
        metadatas.append({"symbol": symbol, "url": art["url"], "source": art["source"] or ""})
        ids.append(art_id)

        existing = (await db.execute(
            select(NewsArticle).where(NewsArticle.url == art["url"])
        )).scalar_one_or_none()
        if not existing:
            record = NewsArticle(
                id=uuid.uuid4(),
                symbol=symbol,
                title=art["title"],
                url=art["url"],
                source=art["source"],
                summary=art["summary"],
                published_at=art["published_at"],
            )
            db.add(record)
            new_records.append(record)

    if chunks:
        add_chunks(collection, chunks, metadatas, ids)
        logger.info("Indexed %d news chunks for symbol=%s", len(chunks), symbol)

    await db.flush()
    return new_records


async def search_news_for_context(
    db: AsyncSession, query: str, symbol: str | None = None, n_results: int = 5
) -> str:
    if symbol:
        await fetch_and_index_news(db, symbol)
        collection = get_or_create_collection(f"news_{symbol.lower()}")
        chunks = search(collection, query, n_results=n_results)
        if chunks:
            return "\n\n---\n\n".join(chunks)

    global_col = get_or_create_collection(NEWS_COLLECTION)
    chunks = search(global_col, query, n_results=n_results)
    return "\n\n---\n\n".join(chunks) if chunks else "No recent news available."


async def list_recent_articles(
    db: AsyncSession, symbol: str | None = None, limit: int = 50
) -> list[NewsArticle]:
    query = select(NewsArticle).order_by(desc(NewsArticle.fetched_at)).limit(limit)
    if symbol:
        query = query.where(NewsArticle.symbol == symbol.upper())
    result = await db.execute(query)
    return list(result.scalars().all())
