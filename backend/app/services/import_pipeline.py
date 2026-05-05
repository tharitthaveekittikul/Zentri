from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.canonical import CANONICAL_FIELDS, apply_template
from app.core.logging import get_logger
from app.services.llm_gateway import LLMGateway

logger = get_logger(__name__)

CANONICAL_SET = set(CANONICAL_FIELDS)


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


def parse_all_rows(file_format: str, content: bytes) -> list[dict]:
    if file_format == "csv":
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        return [dict(r) for r in reader]
    data = json.loads(content)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def _extract_rows_by_path(data: Any, json_path: str | None) -> list[dict]:
    """Flatten nested JSON using json_path returned by LLM (e.g. 'transactions')."""
    if not json_path:
        return data if isinstance(data, list) else []
    if isinstance(data, list):
        rows: list[dict] = []
        for item in data:
            if isinstance(item, dict):
                nested = item.get(json_path)
                if isinstance(nested, list):
                    rows.extend(nested)
        return rows
    if isinstance(data, dict):
        nested = data.get(json_path)
        if isinstance(nested, list):
            return nested
    return []


def is_canonical(headers: list[str]) -> bool:
    return all(h in CANONICAL_SET for h in headers)


async def translate_via_llm(
    db: AsyncSession,
    user_id: Any,
    headers: list[str],
    sample_rows: list[dict],
) -> dict:
    gw = LLMGateway(db)
    raw = await gw.complete(
        feature_key="import_translator",
        user_id=user_id,
        variables={"headers": str(headers), "sample_rows": json.dumps(sample_rows[:5])},
    )
    if isinstance(raw, str):
        raw = raw.strip()
    else:
        raw = str(raw).strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    mapping = json.loads(raw)
    logger.info("LLM translation mapping produced: %s", mapping)
    return mapping


async def process_file(
    db: AsyncSession,
    user_id: Any,
    file_format: str,
    content: bytes,
) -> tuple[list[dict], str]:
    top_rows = parse_all_rows(file_format, content)
    if not top_rows:
        return [], "direct"
    headers = list(top_rows[0].keys())
    if is_canonical(headers):
        logger.info("File is canonical — direct import, %d rows", len(top_rows))
        return top_rows, "direct"
    logger.info("Non-canonical headers %s — calling LLM translator", headers)
    mapping = await translate_via_llm(db, user_id, headers, top_rows)

    # Extract transaction rows using json_path (handles nested JSON like Dime offshore)
    json_path = mapping.get("json_path")
    if file_format == "json" and json_path:
        raw_data = json.loads(content)
        rows = _extract_rows_by_path(raw_data, json_path)
        if not rows:
            rows = top_rows
    else:
        rows = top_rows

    logger.info("Applying template to %d rows (json_path=%s)", len(rows), json_path)
    canonical_rows = apply_template(rows, mapping)
    return canonical_rows, "llm_translated"


