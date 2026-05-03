# backend/tests/core/test_canonical.py
from decimal import Decimal
import pytest
from app.core.canonical import apply_template, CANONICAL_FIELDS


def test_canonical_fields_list():
    assert "trade_date" in CANONICAL_FIELDS
    assert "type" in CANONICAL_FIELDS
    assert "symbol" in CANONICAL_FIELDS
    assert "unit" in CANONICAL_FIELDS
    assert "gross_thb" in CANONICAL_FIELDS
    assert "exchange_rate" in CANONICAL_FIELDS


def test_apply_template_direct_mapping(sample_finnomena_rows):
    template = {
        "field_map": {
            "Fund_Code": "symbol",
            "Trade_Date": "trade_date",
            "Number_of_Units": "unit",
            "Total_Amount": "gross_thb",
        },
        "value_transforms": {},
        "derived_fields": {},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    assert result[0]["symbol"] == "SCBSET50"
    assert result[0]["currency"] == "THB"
    assert result[0]["asset_type"] == "th_fund"


def test_apply_template_value_transforms(sample_finnomena_rows):
    template = {
        "field_map": {"Template": "type", "Fund_Code": "symbol",
                      "Total_Amount": "gross_thb", "Number_of_Units": "unit"},
        "value_transforms": {"type": {"Buy Note": "BUY", "Sell Note": "SELL", "Manual": "BUY"}},
        "derived_fields": {},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    assert result[0]["type"] == "BUY"


def test_apply_template_derived_fields(sample_finnomena_rows):
    template = {
        "field_map": {"Total_Amount": "gross_thb", "Number_of_Units": "unit"},
        "value_transforms": {},
        "derived_fields": {"price": "gross_thb / unit"},
        "defaults": {"currency": "THB"},
        "asset_type_rules": [],
        "asset_type_fallback": "th_fund",
    }
    result = apply_template(sample_finnomena_rows, template)
    price = result[0]["price"]
    assert price is not None
    assert abs(float(price) - (500 / 22.5926)) < 0.01


def test_apply_template_derived_null_when_missing():
    rows = [{"gross_thb": "100"}]
    template = {
        "field_map": {},
        "value_transforms": {},
        "derived_fields": {"price": "gross_thb / unit"},
        "defaults": {},
        "asset_type_rules": [],
        "asset_type_fallback": "us_stock",
    }
    result = apply_template(rows, template)
    assert result[0]["price"] is None


def test_apply_template_defaults_fill_nulls():
    rows = [{"symbol": "PTT", "unit": "100"}]
    template = {
        "field_map": {},
        "value_transforms": {},
        "derived_fields": {},
        "defaults": {"currency": "THB", "exchange": "SET"},
        "asset_type_rules": [],
        "asset_type_fallback": "thai_stock",
    }
    result = apply_template(rows, template)
    assert result[0]["currency"] == "THB"
    assert result[0]["exchange"] == "SET"
