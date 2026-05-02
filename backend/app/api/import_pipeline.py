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
    json_path = None
    structure = pipeline_svc.extract_structure(file_format, content, json_path)
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
            }
            preview = pipeline_svc.apply_template(structure["all_rows"], tmpl_dict)
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
            }
            preview = pipeline_svc.apply_template(structure["all_rows"], tmpl_dict)
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
    structure = pipeline_svc.extract_structure(file_format, content, json_path)

    try:
        template_data = await pipeline_svc.generate_template_via_llm(db, current_user.id, file_format, structure)
    except ValueError as exc:
        raise HTTPException(status_code=424, detail=str(exc))

    signature = pipeline_svc.compute_signature(structure["headers"])
    tmpl = await pipeline_svc.save_template(
        db, current_user.id, platform_id, template_data, file_format, template_data.get("json_path", json_path), signature
    )
    preview = pipeline_svc.apply_template(structure["all_rows"], template_data)
    logger.info("Template generated via LLM: platform=%s user=%s", platform_id, current_user.id)
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
            quantity = Decimal(str(row.get("units", row.get("quantity", 0))))
            price = Decimal(str(row.get("price", 0)))
            fee = Decimal(str(row.get("fee_thb", row.get("fee", 0)) or 0))
            raw_date = row.get("date", "")
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
            imported += 1
        except Exception as exc:
            errors.append({"row": row, "error": str(exc)})

    await db.commit()
    logger.info("Import confirm: imported=%d errors=%d user=%s", imported, len(errors), current_user.id)
    return {"imported": imported, "errors": errors}
