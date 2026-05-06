from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.events import EventsCalendarResponse
from app.services import events_calendar

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/calendar", response_model=EventsCalendarResponse)
async def get_calendar(
    months: int = 3,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if months < 1 or months > 12:
        raise HTTPException(status_code=400, detail="months must be between 1 and 12")
    result = await events_calendar.get_calendar(
        db, current_user.id, months, current_user.currency_secondary
    )
    return result
