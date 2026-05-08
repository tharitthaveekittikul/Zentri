from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.cash_balance import CashBalance
from app.models.holding import Holding
from app.models.price import Price
from app.models.watchlist_item import WatchlistItem
from app.services import exchange_rate as fx_service

logger = get_logger(__name__)

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "get_portfolio_summary",
        "description": "Get a summary of the user's portfolio including total value, unrealized P&L, and allocation by asset type. Call this when the user asks about their overall portfolio.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_holdings",
        "description": "Get detailed list of the user's current holdings with quantity, average cost, current price, and P&L per holding.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_cash_balance",
        "description": "Get the user's cash balances across currencies.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_watchlist",
        "description": "Get the user's watchlist — assets they are monitoring but do not yet hold.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_asset_price",
        "description": "Get the latest price and basic info for a specific asset by its ticker symbol.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "The ticker symbol of the asset, e.g. AAPL, BTC, SCB.",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "search_news",
        "description": "Search recent financial news relevant to a query or specific stock symbol. Use this when the user asks about news, recent events, or market developments.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g. 'AAPL earnings' or 'US interest rates'.",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional ticker symbol to scope news to a specific asset.",
                },
            },
            "required": ["query"],
        },
    },
]


async def _latest_price(db: AsyncSession, asset_id: uuid.UUID) -> Price | None:
    result = await db.execute(
        select(Price).where(Price.asset_id == asset_id).order_by(desc(Price.timestamp)).limit(1)
    )
    return result.scalar_one_or_none()


async def execute_tool(
    name: str,
    arguments: dict,
    db: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
) -> str:
    try:
        if name == "get_portfolio_summary":
            return await _get_portfolio_summary(db, user_id, currency)
        if name == "get_holdings":
            return await _get_holdings(db, user_id, currency)
        if name == "get_cash_balance":
            return await _get_cash_balance(db, user_id, currency)
        if name == "get_watchlist":
            return await _get_watchlist(db, user_id)
        if name == "get_asset_price":
            return await _get_asset_price(db, arguments.get("symbol", ""), currency)
        if name == "search_news":
            return await _search_news(db, arguments.get("query", ""), arguments.get("symbol"))
        return f"Unknown tool: {name}"
    except Exception as exc:
        logger.warning("Tool %s failed: %s", name, exc)
        return f"Error executing {name}: {exc}"


async def _get_portfolio_summary(db: AsyncSession, user_id: uuid.UUID, currency: str) -> str:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    total_value = Decimal("0")
    total_cost = Decimal("0")
    by_type: dict[str, Decimal] = {}

    for h in holdings:
        asset = (await db.execute(select(Asset).where(Asset.id == h.asset_id))).scalar_one_or_none()
        if not asset:
            continue
        rate = await fx_service.get_rate(db, asset.currency, currency) or Decimal("1")
        latest = await _latest_price(db, h.asset_id)
        price = latest.close if latest else h.avg_cost_price
        value = h.quantity * price * rate
        cost = h.quantity * h.avg_cost_price * rate
        total_value += value
        total_cost += cost
        by_type[asset.asset_type] = by_type.get(asset.asset_type, Decimal("0")) + value

    cash_assets = list(
        (await db.execute(
            select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
        )).scalars().all()
    )
    cash_total = Decimal("0")
    for ca in cash_assets:
        snap = (await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.desc()).limit(1)
        )).scalar_one_or_none()
        if snap:
            rate = await fx_service.get_rate(db, ca.currency, currency) or Decimal("1")
            cash_total += Decimal(str(snap.balance)) * rate

    total_value += cash_total
    total_cost += cash_total
    pnl = total_value - total_cost
    pnl_pct = float(pnl / total_cost * 100) if total_cost else 0.0

    lines = [f"Total portfolio value: {float(total_value):.2f} {currency}"]
    lines.append(f"Unrealized P&L: {float(pnl):.2f} {currency} ({pnl_pct:+.1f}%)")
    lines.append(f"Cash: {float(cash_total):.2f} {currency}")
    if by_type:
        lines.append("Allocation by type:")
        for t, v in sorted(by_type.items(), key=lambda x: -x[1]):
            pct = float(v / total_value * 100) if total_value else 0
            lines.append(f"  {t}: {float(v):.2f} {currency} ({pct:.1f}%)")
    return "\n".join(lines)


async def _get_holdings(db: AsyncSession, user_id: uuid.UUID, currency: str) -> str:
    holdings = list(
        (await db.execute(select(Holding).where(Holding.user_id == user_id))).scalars().all()
    )
    if not holdings:
        return "No holdings found."
    lines = [f"{'Symbol':<10} {'Qty':>10} {'Avg Cost':>10} {'Price':>10} {'Value':>12} {'P&L%':>8}"]
    for h in holdings:
        asset = (await db.execute(select(Asset).where(Asset.id == h.asset_id))).scalar_one_or_none()
        if not asset:
            continue
        rate = await fx_service.get_rate(db, asset.currency, currency) or Decimal("1")
        latest = await _latest_price(db, h.asset_id)
        price = latest.close if latest else h.avg_cost_price
        value = float(h.quantity * price * rate)
        cost = float(h.quantity * h.avg_cost_price * rate)
        pnl_pct = (value - cost) / cost * 100 if cost else 0
        lines.append(
            f"{asset.symbol:<10} {float(h.quantity):>10.4f} {float(h.avg_cost_price):>10.2f} "
            f"{float(price):>10.2f} {value:>12.2f} {pnl_pct:>+7.1f}%"
        )
    return "\n".join(lines)


async def _get_cash_balance(db: AsyncSession, user_id: uuid.UUID, currency: str) -> str:
    cash_assets = list(
        (await db.execute(
            select(Asset).where(Asset.user_id == user_id, Asset.asset_type == "cash")
        )).scalars().all()
    )
    if not cash_assets:
        return "No cash balances recorded."
    lines = []
    for ca in cash_assets:
        snap = (await db.execute(
            select(CashBalance)
            .where(CashBalance.asset_id == ca.id, CashBalance.user_id == user_id)
            .order_by(CashBalance.snapshot_date.desc()).limit(1)
        )).scalar_one_or_none()
        if snap:
            rate = await fx_service.get_rate(db, ca.currency, currency) or Decimal("1")
            converted = float(Decimal(str(snap.balance)) * rate)
            lines.append(f"{ca.currency}: {float(snap.balance):.2f} (≈ {converted:.2f} {currency})")
    return "\n".join(lines) if lines else "No cash balances recorded."


async def _get_watchlist(db: AsyncSession, user_id: uuid.UUID) -> str:
    items = list(
        (await db.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == user_id)
        )).scalars().all()
    )
    if not items:
        return "Watchlist is empty."
    lines = []
    for item in items:
        asset = (await db.execute(select(Asset).where(Asset.id == item.asset_id))).scalar_one_or_none()
        symbol = asset.symbol if asset else "?"
        verdict = f" [{item.verdict}]" if getattr(item, "verdict", None) else ""
        lines.append(f"{symbol}{verdict}")
    return "\n".join(lines)


async def _search_news(db: AsyncSession, query: str, symbol: str | None) -> str:
    from app.services.news_rag import search_news_for_context
    sym = symbol.upper() if symbol else None
    return await search_news_for_context(db, query, symbol=sym, n_results=4)


async def _get_asset_price(db: AsyncSession, symbol: str, currency: str) -> str:
    if not symbol:
        return "Symbol is required."
    asset = (await db.execute(
        select(Asset).where(Asset.symbol == symbol.upper(), Asset.user_id == user_id)
    )).scalar_one_or_none()
    if not asset:
        return f"Asset '{symbol.upper()}' not found in your portfolio."
    latest = await _latest_price(db, asset.id)
    if not latest:
        return f"{symbol.upper()}: No price data available."
    rate = await fx_service.get_rate(db, asset.currency, currency) or Decimal("1")
    price_local = float(latest.close)
    price_converted = float(latest.close * rate)
    return (
        f"{asset.symbol} ({asset.asset_type})\n"
        f"Price: {price_local:.4f} {asset.currency}"
        + (f" (≈ {price_converted:.2f} {currency})" if asset.currency != currency else "")
        + f"\nAs of: {latest.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"
    )
