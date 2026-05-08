from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.news_rag import list_recent_articles

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/news")
async def get_news_library(
    symbol: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    articles = await list_recent_articles(db, symbol=symbol, limit=min(limit, 100))
    return [
        {
            "id": str(a.id),
            "symbol": a.symbol,
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "summary": a.summary,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "fetched_at": a.fetched_at.isoformat(),
        }
        for a in articles
    ]
