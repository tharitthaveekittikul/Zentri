from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ATH_WINDOW_DAYS
from app.core.encryption import decrypt
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.price import Price
from app.models.user import User
from app.models.watchlist_item import WatchlistItem
from app.services.telegram import send_message

logger = get_logger(__name__)


async def _fetch_pending_rows(db: AsyncSession) -> list:
    """Return rows (WatchlistItem, Asset, Price, User) ready for alert check."""
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price, User)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .join(User, WatchlistItem.user_id == User.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(
            WatchlistItem.alert_enabled.is_(True),
            WatchlistItem.alerted_at.is_(None),
            WatchlistItem.target_price.isnot(None),
        )
    )
    result = await db.execute(stmt)
    return result.all()


async def _fetch_ath_alert_rows(db: AsyncSession) -> list:
    """Return rows (WatchlistItem, Asset, Price, User) where ATH alert threshold is set and not yet fired."""
    latest_ts = (
        select(Price.asset_id, func.max(Price.timestamp).label("max_ts"))
        .group_by(Price.asset_id)
        .subquery("latest_ts")
    )
    stmt = (
        select(WatchlistItem, Asset, Price, User)
        .join(Asset, WatchlistItem.asset_id == Asset.id)
        .join(User, WatchlistItem.user_id == User.id)
        .outerjoin(latest_ts, WatchlistItem.asset_id == latest_ts.c.asset_id)
        .outerjoin(
            Price,
            and_(
                Price.asset_id == WatchlistItem.asset_id,
                Price.timestamp == latest_ts.c.max_ts,
            ),
        )
        .where(
            WatchlistItem.alert_enabled.is_(True),
            WatchlistItem.ath_alert_threshold.isnot(None),
            WatchlistItem.ath_alerted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    return result.all()


def _format_alert_message(item: WatchlistItem, asset: Asset, price: Price) -> str:
    direction = "at" if price.close == item.target_price else "below"
    return (
        f"🎯 <b>Price Alert — {asset.symbol}</b>\n"
        f"{asset.name}\n\n"
        f"Current price: <b>{price.close:.4f} {asset.currency}</b>\n"
        f"Your target: {item.target_price:.4f} {item.currency}\n\n"
        f"Price is now {direction} your target! Open Zentri to review."
    )


def _format_ath_alert_message(
    item: WatchlistItem, asset: Asset, price: Price, ath_drop_pct: float
) -> str:
    return (
        f"📉 <b>ATH Drop Alert — {asset.symbol}</b>\n"
        f"{asset.name}\n\n"
        f"Dropped <b>-{ath_drop_pct:.1f}%</b> from ATH "
        f"(your threshold: {float(item.ath_alert_threshold):.0f}%)\n"
        f"Current price: <b>{price.close:.4f} {asset.currency}</b>\n\n"
        f"Open Zentri to review."
    )


async def check_and_notify(db: AsyncSession) -> int:
    """Check pending watchlist alerts and send Telegram messages. Returns alert count."""
    rows = await _fetch_pending_rows(db)
    count = 0
    for item, asset, price, user in rows:
        if price is None:
            continue
        if price.close > item.target_price:
            continue
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping alert", user.id)
            continue
        try:
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_alert_message(item, asset, price)
            await send_message(bot_token, user.telegram_chat_id, text)
            item.alerted_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("Alert sent for %s (item %s)", asset.symbol, item.id)
        except Exception:
            logger.exception("Failed to send alert for item %s (asset %s)", item.id, asset.symbol)

    # ATH drop alert pass
    ath_rows = await _fetch_ath_alert_rows(db)
    since = datetime.now(timezone.utc) - timedelta(days=ATH_WINDOW_DAYS)
    for item, asset, price, user in ath_rows:
        if price is None:
            continue
        if not user.telegram_bot_token or not user.telegram_chat_id:
            logger.info("No Telegram config for user %s — skipping ATH alert", user.id)
            continue
        try:
            ath_result = await db.execute(
                select(func.max(Price.close))
                .where(Price.asset_id == item.asset_id, Price.timestamp >= since)
            )
            ath = ath_result.scalar()
            if not ath:
                continue
            ath_drop_pct = float(
                (Decimal(str(ath)) - Decimal(str(price.close))) / Decimal(str(ath)) * 100
            )
            if ath_drop_pct < float(item.ath_alert_threshold):
                continue
            bot_token = decrypt(user.telegram_bot_token)
            text = _format_ath_alert_message(item, asset, price, ath_drop_pct)
            await send_message(bot_token, user.telegram_chat_id, text)
            item.ath_alerted_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("ATH drop alert sent for %s (item %s) drop=%.1f%%", asset.symbol, item.id, ath_drop_pct)
        except Exception:
            logger.exception("Failed to send ATH alert for item %s (asset %s)", item.id, asset.symbol)

    return count
