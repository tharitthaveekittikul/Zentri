from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.canonical import apply_template, _classify_row_asset_type
from app.models.import_template import ImportTemplate
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)


def detect_file_format(filename: str, content: bytes) -> str:
    if filename.endswith(".csv"):
        return "csv"
    if filename.endswith(".json"):
        return "json"
    try:
        json.loads(content)
        return "json"
    except Exception:
        return "csv"


def _resolve_json_path(data: Any, path: str) -> list[dict]:
    """Resolve a dotted path like '[].transactions[]' into a flat list of dicts."""
    items = data if isinstance(data, list) else [data]
    for part in path.split("."):
        part = part.strip("[]")
        if not part:
            continue
        next_items: list[dict] = []
        for item in items:
            val = item.get(part, [])
            if isinstance(val, list):
                next_items.extend(val)
            elif isinstance(val, dict):
                next_items.append(val)
        items = next_items
    return items


def extract_structure(file_format: str, content: bytes, json_path: str | None) -> dict:
    if file_format == "csv":
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = [dict(r) for r in reader]
        headers = list(rows[0].keys()) if rows else []
        sample_rows = rows[:3]
    else:
        data = json.loads(content)
        if json_path:
            rows = _resolve_json_path(data, json_path)
        else:
            rows = data if isinstance(data, list) else [data]
        headers = list(rows[0].keys()) if rows else []
        sample_rows = rows[:3]
    return {"headers": headers, "sample_rows": sample_rows, "total_rows": len(rows), "all_rows": rows}


def compute_signature(headers: list[str]) -> str:
    return hashlib.sha256(",".join(sorted(headers)).encode()).hexdigest()



async def get_template(db: AsyncSession, user_id: uuid.UUID, platform_id: uuid.UUID) -> ImportTemplate | None:
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.platform_id == platform_id,
            ImportTemplate.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_template_by_signature(
    db: AsyncSession, user_id: uuid.UUID, signature: str
) -> ImportTemplate | None:
    logger.debug("get_template_by_signature user=%s signature=%s", user_id, signature)
    result = await db.execute(
        select(ImportTemplate).where(
            ImportTemplate.user_id == user_id,
            ImportTemplate.column_signature == signature,
        )
    )
    return result.scalar_one_or_none()


async def save_template(
    db: AsyncSession,
    user_id: uuid.UUID,
    platform_id: uuid.UUID,
    template_data: dict,
    file_format: str,
    json_path: str | None,
    signature: str,
) -> ImportTemplate:
    now = datetime.now(timezone.utc)
    existing = await get_template(db, user_id, platform_id)
    if existing:
        existing.field_map = template_data.get("field_map", {})
        existing.asset_type_rules = template_data.get("asset_type_rules", [])
        existing.asset_type_fallback = template_data.get("asset_type_fallback", "us_stock")
        existing.currency_default = template_data.get("currency_default", "THB")
        existing.value_transforms = template_data.get("value_transforms", {})
        existing.derived_fields = template_data.get("derived_fields", {})
        existing.defaults = template_data.get("defaults", {})
        existing.json_path = template_data.get("json_path", json_path)
        existing.column_signature = signature
        existing.file_format = file_format
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        logger.info("ImportTemplate updated: platform=%s user=%s", platform_id, user_id)
        return existing
    tmpl = ImportTemplate(
        platform_id=platform_id,
        user_id=user_id,
        file_format=file_format,
        json_path=json_path,
        column_signature=signature,
        field_map=template_data.get("field_map", {}),
        asset_type_rules=template_data.get("asset_type_rules", []),
        asset_type_fallback=template_data.get("asset_type_fallback", "us_stock"),
        currency_default=template_data.get("currency_default", "THB"),
        value_transforms=template_data.get("value_transforms", {}),
        derived_fields=template_data.get("derived_fields", {}),
        defaults=template_data.get("defaults", {}),
        created_at=now,
        updated_at=now,
    )
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    logger.info("ImportTemplate saved: platform=%s user=%s", platform_id, user_id)
    return tmpl


async def generate_template_via_llm(
    db: AsyncSession,
    user_id: uuid.UUID,
    file_format: str,
    structure: dict,
) -> dict:
    gateway = LLMGateway(db)
    raw = await gateway.complete(
        "import_template_generator",
        user_id,
        {
            "file_format": file_format,
            "headers": json.dumps(structure["headers"]),
            "sample_rows": json.dumps(structure["sample_rows"], ensure_ascii=False, indent=2),
        },
    )
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    template_data = json.loads(raw)
    template_data.setdefault("value_transforms", {})
    template_data.setdefault("derived_fields", {})
    template_data.setdefault("defaults", {})
    template_data.setdefault("asset_type_rules", [])
    template_data.setdefault("asset_type_fallback", "us_stock")
    logger.info("LLM template generated for user=%s format=%s", user_id, file_format)
    return template_data


async def enrich_exchange_rates(
    db: AsyncSession,
    rows: list[dict],
) -> list[dict]:
    from app.services.exchange_rate import get_historical_usd_thb
    import dateutil.parser as dp

    for row in rows:
        if row.get("exchange_rate") is not None:
            continue
        currency = row.get("currency", "THB")
        if currency == "THB":
            row["exchange_rate"] = 1.0
            continue
        trade_date_raw = row.get("trade_date")
        if not trade_date_raw:
            continue
        try:
            trade_dt = dp.parse(str(trade_date_raw)).date()
            rate = await get_historical_usd_thb(db, trade_dt)
            if rate is not None:
                row["exchange_rate"] = float(rate)
                if row.get("gross_amount") and not row.get("gross_thb"):
                    row["gross_thb"] = float(row["gross_amount"]) * float(rate)
        except Exception:
            pass
    return rows
