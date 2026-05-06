from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from sqlalchemy import select
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
    """Flatten nested JSON using json_path returned by LLM (e.g. 'transactions').

    When each outer object groups transactions for a date/account, scalar fields
    from the outer object (e.g. trading_date, account_no) are merged into every
    inner row so the field_map can reference them.
    """
    if not json_path:
        return data if isinstance(data, list) else []
    if isinstance(data, list):
        rows: list[dict] = []
        for item in data:
            if isinstance(item, dict):
                nested = item.get(json_path)
                if isinstance(nested, list):
                    outer: dict = {}
                    for k, v in item.items():
                        if k == json_path:
                            continue
                        if isinstance(v, dict):
                            # Flatten one level of sibling dicts (e.g. summary.exchange_rate)
                            for sk, sv in v.items():
                                if not isinstance(sv, (list, dict)):
                                    outer[sk] = sv
                        elif not isinstance(v, list):
                            outer[k] = v  # direct scalars override flattened dict fields
                    for inner in nested:
                        if isinstance(inner, dict):
                            rows.append({**outer, **inner})
                        else:
                            rows.append(inner)
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
    file_format: str,
    headers: list[str],
    sample_rows: list[dict],
) -> dict:
    from app.models.llm_call_log import LLMCallLog

    # Check for a cached mapping from a previous successful LLM call for the same headers
    headers_marker = f"Headers/keys: {headers!s}"
    cached = (await db.execute(
        select(LLMCallLog)
        .where(
            LLMCallLog.user_id == user_id,
            LLMCallLog.feature_key == "import_translator",
            LLMCallLog.prompt_in.contains(headers_marker),
            LLMCallLog.response_out.isnot(None),
        )
        .order_by(LLMCallLog.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if cached:
        try:
            raw = cached.response_out.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            mapping = json.loads(raw)
            logger.info("LLM cache hit: reusing previous import_translator mapping (log id=%s)", cached.id)
            return mapping
        except Exception:
            logger.warning("LLM cache hit but response_out was invalid JSON — falling through to LLM call")

    gw = LLMGateway(db)
    result = await gw.complete(
        feature_key="import_translator",
        user_id=user_id,
        variables={
            "file_format": file_format,
            "headers": str(headers),
            "sample_rows": json.dumps(sample_rows[:5], ensure_ascii=False),
        },
    )
    raw = result.content.strip()

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
    mapping = await translate_via_llm(db, user_id, file_format, headers, top_rows)

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


