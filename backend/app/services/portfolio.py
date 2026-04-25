import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.holding import Holding
from app.models.transaction import Transaction


async def add_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    quantity: Decimal,
    avg_cost_price: Decimal,
    currency: str,
) -> Holding:
    holding = Holding(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset_id,
        quantity=quantity,
        avg_cost_price=avg_cost_price,
        currency=currency,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(holding)
    await db.commit()
    await db.refresh(holding)
    return holding


async def list_holdings(db: AsyncSession, user_id: uuid.UUID) -> list[Holding]:
    result = await db.execute(select(Holding).where(Holding.user_id == user_id))
    return list(result.scalars().all())


async def get_holding(db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID) -> Holding | None:
    result = await db.execute(
        select(Holding).where(Holding.id == holding_id, Holding.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_holding(db: AsyncSession, holding: Holding) -> None:
    await db.delete(holding)
    await db.commit()


async def add_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    type_: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    executed_at: datetime,
    platform_id: uuid.UUID | None = None,
    source: str = "manual",
) -> Transaction:
    tx = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        asset_id=asset_id,
        platform_id=platform_id,
        type=type_,
        quantity=quantity,
        price=price,
        fee=fee,
        source=source,
        executed_at=executed_at,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
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
    holdings = await list_holdings(db, user_id)
    total_cost = sum(h.quantity * h.avg_cost_price for h in holdings)
    return {
        "holdings_count": len(holdings),
        "total_cost_usd": total_cost,
    }
