from __future__ import annotations

import operator as _op
import re
from decimal import Decimal, InvalidOperation
from typing import Any

CANONICAL_FIELDS = [
    "trade_date", "type", "symbol", "unit", "price", "currency",
    "exchange", "gross_amount", "fee", "gross_thb", "fee_thb",
    "exchange_rate", "asset_type", "platform", "notes",
]

CANONICAL_TYPES = frozenset(["BUY", "SELL", "DIVIDEND", "REWARD", "FEE", "TRANSFER"])
CANONICAL_ASSET_TYPES = frozenset(
    ["us_stock", "thai_stock", "th_fund", "etf", "crypto", "gold", "cash"]
)

_OPERATORS = {"/": _op.truediv, "*": _op.mul, "+": _op.add, "-": _op.sub}

_ASSET_TYPE_ALIASES: dict[str, str] = {
    "stock": "thai_stock",
    "us stock": "us_stock",
    "thai stock": "thai_stock",
    "fund": "th_fund",
    "mutual fund": "th_fund",
    "bond": "th_fund",
}


def _eval_expression(expr: str, row: dict[str, Any]) -> Decimal | None:
    expr = expr.strip()
    for op_char, op_fn in _OPERATORS.items():
        if op_char in expr:
            left_key, right_key = expr.split(op_char, 1)
            left_val = row.get(left_key.strip())
            right_val = row.get(right_key.strip())
            if left_val is None or right_val is None:
                return None
            try:
                l, r = Decimal(str(left_val)), Decimal(str(right_val))
                if op_char == "/" and r == 0:
                    return None
                return op_fn(l, r)
            except (InvalidOperation, ZeroDivisionError):
                return None
    val = row.get(expr)
    return Decimal(str(val)) if val is not None else None


def _normalize_asset_type(value: str, fallback: str) -> str:
    if value in CANONICAL_ASSET_TYPES:
        return value
    aliased = _ASSET_TYPE_ALIASES.get(value.lower().strip())
    return aliased if aliased in CANONICAL_ASSET_TYPES else fallback


def _classify_row_asset_type(row: dict, rules: list[dict], fallback: str) -> str:
    safe_fallback = _normalize_asset_type(fallback, "thai_stock")
    for rule in rules:
        field = rule.get("field", "")
        value = str(row.get(field, ""))
        if "values" in rule:
            if value in rule["values"]:
                return _normalize_asset_type(rule["asset_type"], safe_fallback)
        elif "pattern" in rule:
            # Strip embedded inline flags (e.g. (?i)) — Python 3.11+ forbids
            # them at non-zero position when flags are also passed as arguments.
            safe_pattern = re.sub(r"^\(\?[aiLmsux]+\)", "", rule["pattern"])
            if re.match(safe_pattern, value, re.IGNORECASE):
                return _normalize_asset_type(rule["asset_type"], safe_fallback)
    return safe_fallback


def apply_template(rows: list[dict], template: dict) -> list[dict]:
    field_map: dict[str, str] = template.get("field_map", {})
    
    # Support for alternative LLM outputs where it returns "mapping": {"canonical_field": "source_field"}
    if not field_map and "mapping" in template:
        mapping = template["mapping"]
        # Invert from {canonical: source} to {source: canonical}
        field_map = {v: k for k, v in mapping.items() if v}
        
    # Normalize old/hallucinated canonical field names to current CANONICAL_FIELDS
    canonical_alias_map = {
        "date": "trade_date",
        "units": "unit",
        "total_thb": "gross_thb",
        "net_amount": "gross_thb",
    }
    field_map = {k: canonical_alias_map.get(v, v) for k, v in field_map.items()}

    value_transforms: dict[str, dict] = template.get("value_transforms", {})
    derived_fields: dict[str, str] = template.get("derived_fields", {})
    defaults: dict[str, Any] = template.get("defaults", {})
    asset_type_rules: list[dict] = template.get("asset_type_rules", [])
    fallback: str = template.get("asset_type_fallback", "us_stock")

    result = []
    for raw in rows:
        normalized: dict[str, Any] = {}

        for k in CANONICAL_FIELDS:
            if k in raw:
                normalized[k] = raw[k]

        for src, dst in field_map.items():
            if src in raw:
                normalized[dst] = raw[src]

        for canonical_key, transform_map in value_transforms.items():
            if canonical_key in normalized:
                val = str(normalized[canonical_key])
                normalized[canonical_key] = transform_map.get(val, normalized[canonical_key])

        for dst_key, expr in derived_fields.items():
            if normalized.get(dst_key) is None:
                normalized[dst_key] = _eval_expression(expr, normalized)

        for k, v in defaults.items():
            if normalized.get(k) is None:
                normalized[k] = v

        normalized["asset_type"] = _classify_row_asset_type(raw, asset_type_rules, fallback)

        # THB transactions: exchange_rate is 1 by definition
        if normalized.get("exchange_rate") is None and str(normalized.get("currency", "")).upper() == "THB":
            normalized["exchange_rate"] = Decimal("1")

        # Guarantee every canonical field is present (null if not mapped/derived)
        for k in CANONICAL_FIELDS:
            if k not in normalized:
                normalized[k] = None

        result.append(normalized)
    return result
