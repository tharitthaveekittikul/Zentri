import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import sqlalchemy as sa
import yfinance as yf
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.dividend_event import DividendEvent
from app.models.holding import Holding
from app.services.exchange_rate import get_rate

logger = get_logger(__name__)

FETCHABLE_ASSET_TYPES = {"us_stock", "etf"}


def _compute_status(ex_date: date, today: date) -> str:
    return "upcoming" if ex_date > today else "payable"


def _build_rows_for_asset(asset, divs, cal: dict, today: date) -> list[dict]:
    rows = []

    for ts, amount in divs.items():
        if not amount or float(amount) <= 0:
            continue
        ex_dt = ts.date() if hasattr(ts, "date") else ts
        rows.append({
            "asset_id": asset.id,
            "ex_date": ex_dt,
            "pay_date": None,
            "record_date": None,
            "amount_per_share": Decimal(str(float(amount))),
            "currency": asset.currency,
            "frequency": None,
            "status": _compute_status(ex_dt, today),
            "source": "yfinance",
        })

    if cal and isinstance(cal, dict):
        cal_ex = cal.get("Ex-Dividend Date")
        cal_pay = cal.get("Dividend Date")
        if cal_ex is not None:
            cal_ex_date = cal_ex.date() if hasattr(cal_ex, "date") else cal_ex
            if cal_ex_date > today:
                last_amount = Decimal(str(float(divs.iloc[-1]))) if len(divs) > 0 else None
                if last_amount and last_amount > 0:
                    pay_date = cal_pay.date() if cal_pay and hasattr(cal_pay, "date") else None
                    rows.append({
                        "asset_id": asset.id,
                        "ex_date": cal_ex_date,
                        "pay_date": pay_date,
                        "record_date": None,
                        "amount_per_share": last_amount,
                        "currency": asset.currency,
                        "frequency": None,
                        "status": "upcoming",
                        "source": "yfinance",
                    })

    return rows


async def fetch_all_dividends(db: AsyncSession) -> int:
    result = await db.execute(
        select(Asset).where(Asset.asset_type.in_(FETCHABLE_ASSET_TYPES))
    )
    assets = list(result.scalars().all())
    if not assets:
        logger.info("fetch_all_dividends: no fetchable assets found")
        return 0

    today = date.today()
    all_rows: list[dict] = []

    def _fetch(symbol: str):
        ticker = yf.Ticker(symbol)
        return ticker.dividends, ticker.calendar

    for asset in assets:
        try:
            divs, cal = await asyncio.get_event_loop().run_in_executor(None, _fetch, asset.symbol)
            rows = _build_rows_for_asset(asset, divs, cal or {}, today)
            all_rows.extend(rows)
        except Exception as e:
            logger.warning("fetch_all_dividends: failed for %s: %s", asset.symbol, e)

    # Deduplicate: prefer calendar row (has pay_date) over historical row for same (asset_id, ex_date)
    seen: dict[tuple, dict] = {}
    for row in all_rows:
        key = (row["asset_id"], row["ex_date"])
        if key not in seen or row["pay_date"] is not None:
            seen[key] = row
    all_rows = list(seen.values())

    if not all_rows:
        logger.info("fetch_all_dividends: no rows to upsert")
        return 0

    stmt = pg_insert(DividendEvent).values(all_rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_dividend_events_asset_ex_date",
        set_={
            "amount_per_share": stmt.excluded.amount_per_share,
            "pay_date": stmt.excluded.pay_date,
            "updated_at": datetime.now(timezone.utc),
        },
    )
    await db.execute(stmt)

    await db.execute(
        update(DividendEvent)
        .where(
            DividendEvent.ex_date <= today,
            DividendEvent.status == "upcoming",
            DividendEvent.confirmed_transaction_id.is_(None),
        )
        .values(status="payable", updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    logger.info("fetch_all_dividends: upserted %d rows", len(all_rows))
    return len(all_rows)


async def get_event(db: AsyncSession, event_id: uuid.UUID) -> DividendEvent | None:
    result = await db.execute(select(DividendEvent).where(DividendEvent.id == event_id))
    return result.scalar_one_or_none()


async def get_calendar(
    db: AsyncSession,
    user_id: uuid.UUID,
    months: int,
    secondary_currency: str,
) -> dict:
    today = date.today()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=months * 31)

    result = await db.execute(
        select(DividendEvent, Asset, Holding)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .outerjoin(
            Holding,
            sa.and_(Holding.asset_id == DividendEvent.asset_id, Holding.user_id == user_id),
        )
        .where(DividendEvent.ex_date >= start_date, DividendEvent.ex_date <= end_date)
        .order_by(DividendEvent.ex_date)
    )
    rows = result.all()

    rate = await get_rate(db, "USD", secondary_currency)
    months_dict: dict[tuple, dict] = {}

    for event, asset, holding in rows:
        qty = holding.quantity if holding else Decimal("0")
        projected_usd = qty * event.amount_per_share
        projected_secondary = projected_usd * rate if rate else None

        key = (event.ex_date.year, event.ex_date.month)
        if key not in months_dict:
            months_dict[key] = {
                "year": key[0],
                "month": key[1],
                "total_projected_usd": Decimal("0"),
                "events": [],
            }

        months_dict[key]["events"].append({
            "id": event.id,
            "asset_id": event.asset_id,
            "symbol": asset.symbol,
            "ex_date": event.ex_date,
            "pay_date": event.pay_date,
            "record_date": event.record_date,
            "amount_per_share": event.amount_per_share,
            "currency": event.currency,
            "frequency": event.frequency,
            "status": event.status,
            "source": event.source,
            "quantity_held": qty,
            "projected_total_usd": projected_usd,
            "projected_total_secondary": projected_secondary,
            "asset_type": asset.asset_type,
            "metadata_": asset.metadata_ or {},
        })
        months_dict[key]["total_projected_usd"] += projected_usd

    return {"months": list(months_dict.values())}


async def get_upcoming(
    db: AsyncSession,
    user_id: uuid.UUID,
    secondary_currency: str,
) -> list[dict]:
    result = await db.execute(
        select(DividendEvent, Asset, Holding)
        .join(Asset, DividendEvent.asset_id == Asset.id)
        .outerjoin(
            Holding,
            sa.and_(Holding.asset_id == DividendEvent.asset_id, Holding.user_id == user_id),
        )
        .where(DividendEvent.status.in_(["upcoming", "payable"]))
        .order_by(DividendEvent.ex_date)
    )
    rows = result.all()

    rate = await get_rate(db, "USD", secondary_currency)
    events = []
    for event, asset, holding in rows:
        qty = holding.quantity if holding else Decimal("0")
        projected_usd = qty * event.amount_per_share
        events.append({
            "id": event.id,
            "asset_id": event.asset_id,
            "symbol": asset.symbol,
            "ex_date": event.ex_date,
            "pay_date": event.pay_date,
            "record_date": event.record_date,
            "amount_per_share": event.amount_per_share,
            "currency": event.currency,
            "frequency": event.frequency,
            "status": event.status,
            "source": event.source,
            "quantity_held": qty,
            "projected_total_usd": projected_usd,
            "projected_total_secondary": projected_usd * rate if rate else None,
        })
    return events
