import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.import_profile import ImportProfile
from app.services import asset as asset_service
from app.services import portfolio as portfolio_service

logger = get_logger(__name__)


def parse_csv_preview(content: bytes) -> dict:
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        rows.append(dict(row))
    columns = list(rows[0].keys()) if rows else []
    return {"columns": columns, "rows": rows[:5]}


async def confirm_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    rows: list[dict],
    asset_type: str,
    save_profile: bool = False,
    broker_name: str | None = None,
) -> dict:
    logger.info("CSV import started: rows=%d asset_type=%s broker=%s user=%s", len(rows), asset_type, broker_name, user_id)
    imported = 0
    skipped = 0
    errors = []

    for row in rows:
        symbol = row["symbol"].strip().upper()
        try:
            quantity = Decimal(row["quantity"])
            price = Decimal(row["price"])
            fee = Decimal(row.get("fee", "0") or "0")
            executed_at = datetime.fromisoformat(row["date"]).replace(tzinfo=timezone.utc)
            tx_type = row["type"].lower()
        except (InvalidOperation, ValueError) as e:
            logger.warning("CSV row skipped: symbol=%s error=%s", row.get("symbol", "?"), e)
            errors.append(f"Row {symbol}: {e}")
            skipped += 1
            continue

        # Find or create asset
        assets = await asset_service.search_assets(db, user_id, symbol)
        matching = [a for a in assets if a.symbol == symbol]
        if matching:
            asset = matching[0]
        else:
            asset = await asset_service.create_asset(
                db, user_id, symbol, asset_type, symbol, "USD"
            )

        await portfolio_service.add_transaction(
            db, user_id, asset.id, tx_type, quantity, price, fee, executed_at, source="csv_import"
        )

        # Upsert holding for buy transactions
        if tx_type == "buy":
            holdings = await portfolio_service.list_holdings(db, user_id)
            existing = next((h for h in holdings if h.asset_id == asset.id), None)
            if existing is None:
                await portfolio_service.add_holding(db, user_id, asset.id, quantity, price, "USD")

        imported += 1

    if save_profile and broker_name:
        profile = ImportProfile(
            id=uuid.uuid4(),
            user_id=user_id,
            broker_name=broker_name,
            column_mapping={"date": "date", "symbol": "symbol", "type": "type", "quantity": "quantity", "price": "price", "fee": "fee"},
        )
        db.add(profile)
        await db.commit()

    logger.info("CSV import done: imported=%d skipped=%d errors=%d user=%s", imported, skipped, len(errors), user_id)
    return {"imported": imported, "skipped": skipped, "errors": errors}
