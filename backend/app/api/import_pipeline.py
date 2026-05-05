import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from dateutil import parser as dp
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.import_pipeline import ConfirmRequest, ConfirmResponse, UploadResponse
from app.services import import_pipeline as pipeline_svc

logger = get_logger(__name__)
router = APIRouter(prefix="/import", tags=["import"])


def to_decimal(val: object) -> Decimal:
    if val is None or val == "":
        return Decimal("0")
    try:
        return Decimal(str(val))
    except InvalidOperation:
        return Decimal("0")


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    try:
        rows, method = await pipeline_svc.process_file(db, current_user.id, file_format, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await db.commit()
    logger.info("Upload: method=%s rows=%d user=%s", method, len(rows), current_user.id)
    return UploadResponse(rows=rows, method=method, total=len(rows))


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_import(
    body: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    imported = 0
    errors: list[dict] = []

    for row in body.rows:
        try:
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                raise ValueError("symbol is required")

            asset_type = str(row.get("asset_type") or "us_stock")
            currency = str(row.get("currency") or "THB")
            platform = row.get("platform") or None

            quantity = to_decimal(row.get("unit"))
            price = to_decimal(row.get("price"))
            fee = to_decimal(row.get("fee_thb") or row.get("fee"))

            raw_date = row.get("trade_date") or ""
            try:
                executed_at = dp.parse(str(raw_date)).replace(tzinfo=timezone.utc)
            except Exception:
                executed_at = datetime.now(timezone.utc)

            tx_type = str(row.get("type") or "buy").lower()

            # Upsert asset
            result = await db.execute(
                select(Asset).where(Asset.user_id == current_user.id, Asset.symbol == symbol)
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                asset = Asset(
                    id=uuid.uuid4(), user_id=current_user.id, symbol=symbol,
                    asset_type=asset_type, name=symbol, currency=currency,
                    metadata_={},
                )
                db.add(asset)
                await db.flush()

            # Record transaction
            tx = Transaction(
                id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
                platform=str(platform) if platform else None,
                type=tx_type, quantity=quantity, price=price, fee=fee,
                source="csv_import", executed_at=executed_at,
            )
            db.add(tx)
            await db.flush()

            # Upsert holding
            h_result = await db.execute(
                select(Holding).where(Holding.asset_id == asset.id, Holding.user_id == current_user.id)
            )
            holding = h_result.scalar_one_or_none()

            if tx_type == "buy":
                if holding is None:
                    holding = Holding(
                        id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
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

            elif tx_type == "sell" and holding is not None:
                holding.quantity -= quantity
                holding.updated_at = datetime.now(timezone.utc)
                if holding.quantity <= 0:
                    await db.delete(holding)

            elif tx_type == "reward":
                if holding is None:
                    holding = Holding(
                        id=uuid.uuid4(), user_id=current_user.id, asset_id=asset.id,
                        quantity=quantity, avg_cost_price=Decimal("0"), currency=currency,
                        updated_at=datetime.now(timezone.utc),
                    )
                    db.add(holding)
                else:
                    holding.quantity += quantity
                    holding.updated_at = datetime.now(timezone.utc)

            await db.flush()
            imported += 1

        except Exception as exc:
            errors.append({"row": row, "error": str(exc)})

    await db.commit()
    logger.info("Import confirm: imported=%d errors=%d user=%s", imported, len(errors), current_user.id)
    return ConfirmResponse(imported=imported, errors=errors)
