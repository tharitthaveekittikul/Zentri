from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.dividend_event import DividendEvent
from app.models.holding import Holding
from app.models.user import User
from app.services.exchange_rate import get_rate
from app.services.telegram import send_message

logger = get_logger(__name__)


async def _fetch_pending_rows(db: AsyncSession) -> list:
    stmt = (
        select(DividendEvent, Asset, Holding, User)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .join(Holding, Holding.asset_id == DividendEvent.asset_id)
        .join(User, User.id == Holding.user_id)
        .where(
            DividendEvent.ex_date == date.today(),
            DividendEvent.dividend_notified_at.is_(None),
            Holding.quantity > 0,
        )
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return result.all()


def _format_message(
    event: DividendEvent,
    asset: Asset,
    holding: Holding,
    rate: Decimal | None,
    secondary_currency: str,
) -> str:
    total = holding.quantity * event.amount_per_share
    secondary = f"~{total * rate:.2f} {secondary_currency}" if rate is not None else ""
    secondary_part = f" ({secondary})" if secondary else ""
    return (
        f"💰 <b>Dividend Day — {asset.symbol}</b>\n\n"
        f"Ex-dividend date: {event.ex_date}\n"
        f"Amount/share: {float(event.amount_per_share):.4f} {event.currency}\n"
        f"Shares held: {float(holding.quantity):.4f}\n"
        f"Projected income: <b>{float(total):.2f} {event.currency}{secondary_part}</b>"
    )


async def check_and_notify(db: AsyncSession) -> int:
    rows = await _fetch_pending_rows(db)
    count = 0
    for event, asset, holding, user in rows:
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping", user.id)
            continue
        try:
            rate = await get_rate(db, event.currency, user.currency_secondary)
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_message(event, asset, holding, rate, user.currency_secondary)
            await send_message(bot_token, user.telegram_chat_id, text)
            event.dividend_notified_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("Dividend alert sent for %s to user %s", asset.symbol, user.id)
        except Exception:
            logger.exception("Failed to send dividend alert for %s (user %s)", asset.symbol, user.id)
    return count
