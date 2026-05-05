import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.transaction import Transaction

logger = get_logger(__name__)


async def add_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    quantity: Decimal,
    avg_cost_price: Decimal,
    currency: str,
    purchased_at: date | None = None,
) -> tuple[Holding, Asset]:
    symbol = symbol.strip().upper()
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_={},
        )
        db.add(asset)
        await db.flush()

    holding = Holding(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
        quantity=quantity, avg_cost_price=avg_cost_price,
        currency=currency, purchased_at=purchased_at,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    logger.info("Holding added: symbol=%s qty=%s user=%s", symbol, quantity, user_id)
    return holding, asset


async def list_holdings_with_assets(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Holding, Asset)
        .join(Asset, Asset.id == Holding.asset_id)
        .where(Holding.user_id == user_id)
    )
    rows = []
    for holding, asset in result.all():
        total_cost = holding.quantity * holding.avg_cost_price
        rows.append({
            "id": holding.id,
            "asset_id": holding.asset_id,
            "symbol": asset.symbol,
            "asset_type": asset.asset_type,
            "currency": holding.currency,
            "purchased_at": holding.purchased_at,
            "outstanding_shares": holding.quantity,
            "cost_per_share": holding.avg_cost_price,
            "total_cost": total_cost,
            "current_price": None,
            "holding_value": None,
            "unrealized_pnl": None,
            "price_1d_change": None,
        })
    return rows


async def get_holding(db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> Holding | None:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_holding(db: AsyncSession, holding: Holding) -> None:
    logger.info("Holding deleted: id=%s user=%s", holding.id, holding.user_id)
    await db.delete(holding)
    await db.commit()


async def add_manual_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    symbol: str,
    asset_type: str,
    type_: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    currency: str,
    executed_at: datetime,
    platform: str | None = None,
) -> Transaction:
    symbol = symbol.strip().upper()
    result = await db.execute(
        select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        asset = Asset(
            id=uuid.uuid4(), user_id=user_id, symbol=symbol,
            asset_type=asset_type, name=symbol, currency=currency,
            metadata_={},
        )
        db.add(asset)
        await db.flush()

    tx = Transaction(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
        platform=platform, type=type_, quantity=quantity,
        price=price, fee=fee, source="manual", executed_at=executed_at,
    )
    db.add(tx)
    await db.flush()

    h_result = await db.execute(
        select(Holding).where(Holding.asset_id == asset.id, Holding.user_id == user_id)
    )
    holding = h_result.scalar_one_or_none()

    if type_ == "buy":
        if holding is None:
            holding = Holding(
                id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
                quantity=quantity, avg_cost_price=price, currency=currency,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)
        else:
            total_qty = holding.quantity + quantity
            if total_qty > 0:
                holding.avg_cost_price = (
                    holding.quantity * holding.avg_cost_price + quantity * price
                ) / total_qty
            holding.quantity = total_qty
            holding.updated_at = datetime.now(timezone.utc)
    elif type_ == "sell" and holding is not None:
        holding.quantity -= quantity
        holding.updated_at = datetime.now(timezone.utc)
        if holding.quantity <= 0:
            await db.delete(holding)
    elif type_ == "reward":
        if holding is None:
            holding = Holding(
                id=uuid.uuid4(), user_id=user_id, asset_id=asset.id,
                quantity=quantity, avg_cost_price=Decimal("0"), currency=currency,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(holding)
        else:
            holding.quantity += quantity
            holding.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(tx)
    logger.info("Manual transaction: type=%s symbol=%s user=%s", type_, symbol, user_id)
    return tx


async def add_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    type_: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    executed_at: datetime,
    platform: str | None = None,
    source: str = "manual",
) -> Transaction:
    tx = Transaction(
        id=uuid.uuid4(), user_id=user_id, asset_id=asset_id,
        platform=platform, type=type_, quantity=quantity,
        price=price, fee=fee, source=source, executed_at=executed_at,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    logger.info("Transaction added: type=%s asset=%s user=%s", type_, asset_id, user_id)
    return tx


async def list_transactions(
    db: AsyncSession, user_id: uuid.UUID, asset_id: uuid.UUID | None = None
) -> list[Transaction]:
    q = select(Transaction).where(Transaction.user_id == user_id)
    if asset_id:
        q = q.where(Transaction.asset_id == asset_id)
    result = await db.execute(q.order_by(Transaction.executed_at.desc()))
    return list(result.scalars().all())


async def get_portfolio_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    rows = await list_holdings_with_assets(db, user_id)
    total_cost = sum(r["total_cost"] for r in rows)
    return {"holdings_count": len(rows), "total_cost": total_cost, "primary_currency": "THB"}
