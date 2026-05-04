import uuid
from datetime import datetime, timezone
from decimal import Decimal
from dateutil import parser as dateutil_parser

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.asset import Asset
from app.models.holding import Holding
from app.models.platform import Platform
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.import_template import AnalyzeResponse, ConfirmImportRequest, ImportTemplateOut, TemplateSaveRequest
from app.services import import_pipeline as pipeline_svc
from app.services import asset as asset_service
from app.services import portfolio as portfolio_service

logger = get_logger(__name__)
router = APIRouter(prefix="/import", tags=["import"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_file(
    platform_id: uuid.UUID | None = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    # Extract outer structure (no json_path) so headers match the stored column_signature
    structure = pipeline_svc.extract_structure(file_format, content, None)
    signature = pipeline_svc.compute_signature(structure["headers"])

    matched_platform_id: uuid.UUID | None = None

    if platform_id is not None:
        existing_template = await pipeline_svc.get_template(db, current_user.id, platform_id)
        if not existing_template:
            status = "new"
            preview = None
        elif existing_template.column_signature != signature:
            status = "mismatch"
            preview = None
        else:
            status = "match"
            matched_platform_id = platform_id
            tmpl_dict = {
                "field_map": existing_template.field_map,
                "asset_type_rules": existing_template.asset_type_rules,
                "asset_type_fallback": existing_template.asset_type_fallback,
                "currency_default": existing_template.currency_default,
                "value_transforms": existing_template.value_transforms,
                "derived_fields": existing_template.derived_fields,
                "defaults": existing_template.defaults,
            }
            # Use saved json_path to get flat rows for preview
            flat = pipeline_svc.extract_structure(file_format, content, existing_template.json_path)
            preview = pipeline_svc.apply_template(flat["all_rows"], tmpl_dict)
    else:
        existing_template = await pipeline_svc.get_template_by_signature(db, current_user.id, signature)
        if existing_template:
            status = "match"
            matched_platform_id = existing_template.platform_id
            tmpl_dict = {
                "field_map": existing_template.field_map,
                "asset_type_rules": existing_template.asset_type_rules,
                "asset_type_fallback": existing_template.asset_type_fallback,
                "currency_default": existing_template.currency_default,
                "value_transforms": existing_template.value_transforms,
                "derived_fields": existing_template.derived_fields,
                "defaults": existing_template.defaults,
            }
            # Use saved json_path to get flat rows for preview
            flat = pipeline_svc.extract_structure(file_format, content, existing_template.json_path)
            preview = pipeline_svc.apply_template(flat["all_rows"], tmpl_dict)
        else:
            status = "new"
            preview = None
            existing_template = None

    logger.info(
        "Import analyze: platform=%s format=%s status=%s user=%s",
        platform_id, file_format, status, current_user.id,
    )
    return AnalyzeResponse(
        signature=signature,
        structure={"headers": structure["headers"], "sample_rows": structure["sample_rows"], "total_rows": structure["total_rows"]},
        template_status=status,
        template=ImportTemplateOut.model_validate(existing_template) if existing_template else None,
        preview_rows=preview,
        matched_platform_id=matched_platform_id,
    )


@router.post("/generate-template")
async def generate_template(
    platform_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    file_format = pipeline_svc.detect_file_format(file.filename or "", content)
    existing = await pipeline_svc.get_template(db, current_user.id, platform_id)
    json_path = existing.json_path if existing else None

    # Always pass outer structure (json_path=None) so LLM can detect the correct json_path
    outer_structure = pipeline_svc.extract_structure(file_format, content, None)

    # If json_path is already known (re-generate), also resolve flat rows so LLM sees propagated fields
    if json_path:
        flat_for_llm = pipeline_svc.extract_structure(file_format, content, json_path)
        llm_structure = flat_for_llm
    else:
        llm_structure = outer_structure

    try:
        template_data = await pipeline_svc.generate_template_via_llm(db, current_user.id, file_format, llm_structure)
    except Exception as exc:
        from app.services.llm_service import LLMQuotaExceededError
        if isinstance(exc, LLMQuotaExceededError):
            raise HTTPException(
                status_code=402,
                detail={"message": str(exc), "provider": exc.provider, "billing_url": exc.billing_url},
            )
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=424, detail=str(exc))
        raise

    # Signature always from outer headers (stable key regardless of json_path)
    signature = pipeline_svc.compute_signature(outer_structure["headers"])
    effective_json_path = template_data.get("json_path") or json_path
    tmpl = await pipeline_svc.save_template(
        db, current_user.id, platform_id, template_data, file_format, effective_json_path, signature
    )
    # Extract flat rows using the resolved json_path for the preview
    flat_structure = pipeline_svc.extract_structure(file_format, content, effective_json_path)
    preview = pipeline_svc.apply_template(flat_structure["all_rows"], template_data)
    preview = await pipeline_svc.enrich_exchange_rates(db, preview)
    logger.info("Template generated via LLM: platform=%s user=%s effective_json_path=%s", platform_id, current_user.id, effective_json_path)
    return {"template": ImportTemplateOut.model_validate(tmpl), "preview_rows": preview}


@router.post("/save-template", response_model=ImportTemplateOut)
async def save_template_manual(
    body: TemplateSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = await pipeline_svc.save_template(
        db, current_user.id, body.platform_id, body.template_data,
        body.file_format, body.json_path, body.signature,
    )
    logger.info("Template saved manually: platform=%s user=%s", body.platform_id, current_user.id)
    return ImportTemplateOut.model_validate(tmpl)


@router.post("/confirm")
async def confirm_import(
    body: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.platform_id is not None:
        result = await db.execute(
            select(Platform).where(Platform.id == body.platform_id, Platform.user_id == current_user.id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Platform not found")

    imported = 0
    errors = []

    for row in body.rows:
        try:
            symbol = row.get("symbol", "").strip().upper()
            asset_type = row.get("asset_type", "us_stock")
            name = row.get("name", symbol) or symbol
            currency = row.get("currency", "THB")

            tx_type = row.get("type", "buy").lower()
            quantity = Decimal(str(row.get("unit", row.get("units", row.get("quantity", 0)))))
            price = Decimal(str(row.get("price", 0)))
            fee = Decimal(str(row.get("fee_thb", row.get("fee", 0)) or 0))
            raw_date = row.get("trade_date", row.get("date", ""))
            if raw_date:
                try:
                    executed_at = datetime.fromisoformat(raw_date).replace(tzinfo=timezone.utc)
                except ValueError:
                    # Fallback: handle formats like DD/MM/YYYY or MM/DD/YYYY
                    executed_at = dateutil_parser.parse(raw_date, dayfirst=True).replace(tzinfo=timezone.utc)
            else:
                executed_at = datetime.now(timezone.utc)

        except Exception as exc:
            errors.append({"row": row, "error": f"Parse error: {exc}"})
            continue

        # Use savepoint so a per-row failure doesn't corrupt the session
        try:
            async with db.begin_nested():
                # Find or create asset (exact match by symbol + user)
                result = await db.execute(
                    select(Asset).where(Asset.symbol == symbol, Asset.user_id == current_user.id)
                )
                asset = result.scalar_one_or_none()
                if asset is None:
                    asset = Asset(
                        id=uuid.uuid4(),
                        user_id=current_user.id,
                        symbol=symbol,
                        asset_type=asset_type,
                        name=name,
                        currency=currency,
                        metadata_={},
                    )
                    db.add(asset)
                    await db.flush()

                tx = Transaction(
                    id=uuid.uuid4(),
                    user_id=current_user.id,
                    asset_id=asset.id,
                    platform_id=body.platform_id,
                    type=tx_type,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    source="csv_import",
                    executed_at=executed_at,
                )
                db.add(tx)
                await db.flush()

                # Upsert holding so portfolio reflects the import
                holding_result = await db.execute(
                    select(Holding).where(
                        Holding.asset_id == asset.id,
                        Holding.user_id == current_user.id,
                    )
                )
                holding = holding_result.scalar_one_or_none()

                if tx_type == "buy":
                    if holding is None:
                        holding = Holding(
                            id=uuid.uuid4(),
                            user_id=current_user.id,
                            asset_id=asset.id,
                            quantity=quantity,
                            avg_cost_price=price,
                            currency=currency,
                            updated_at=datetime.now(timezone.utc),
                        )
                        db.add(holding)
                    else:
                        # Weighted average cost
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
                    # Bonus shares / staking rewards — add units at zero cost basis
                    if holding is None:
                        holding = Holding(
                            id=uuid.uuid4(),
                            user_id=current_user.id,
                            asset_id=asset.id,
                            quantity=quantity,
                            avg_cost_price=Decimal("0"),
                            currency=currency,
                            updated_at=datetime.now(timezone.utc),
                        )
                        db.add(holding)
                    else:
                        # Keep existing avg cost, just add the free units
                        holding.quantity += quantity
                        holding.updated_at = datetime.now(timezone.utc)

                # dividend, fee, transfer — transaction recorded but no holding adjustment
                # dividend: cash payout doesn't change unit count
                # fee:      cost recorded on transaction only
                # transfer: movement between platforms, net position unchanged

                await db.flush()

            imported += 1
        except Exception as exc:
            errors.append({"row": row, "error": str(exc)})

    await db.commit()
    logger.info("Import confirm: imported=%d errors=%d user=%s", imported, len(errors), current_user.id)
    return {"imported": imported, "errors": errors}


@router.delete("/template/{platform_id}", status_code=204)
async def delete_template(
    platform_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.import_template import ImportTemplate
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.platform_id == platform_id,
            ImportTemplate.user_id == current_user.id,
        )
    )
    tmpl = result.scalar_one_or_none()
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(tmpl)
    await db.commit()
    logger.info("ImportTemplate deleted (re-map): platform=%s user=%s", platform_id, current_user.id)
