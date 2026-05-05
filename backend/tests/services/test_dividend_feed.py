import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.services.dividend_feed import _build_rows_for_asset, _compute_status


def _make_asset(symbol: str = "AAPL", currency: str = "USD"):
    a = MagicMock()
    a.id = uuid.uuid4()
    a.symbol = symbol
    a.currency = currency
    return a


def test_compute_status_upcoming():
    future = date(2099, 1, 1)
    assert _compute_status(future, date.today()) == "upcoming"


def test_compute_status_payable():
    past = date(2020, 1, 1)
    assert _compute_status(past, date.today()) == "payable"


def test_build_rows_for_asset_extracts_historical():
    asset = _make_asset()
    ts = pd.Timestamp("2025-01-15")
    divs = pd.Series([0.25], index=[ts])
    cal = {}
    rows = _build_rows_for_asset(asset, divs, cal, date(2026, 1, 1))
    assert len(rows) == 1
    assert rows[0]["asset_id"] == asset.id
    assert rows[0]["amount_per_share"] == Decimal("0.25")
    assert rows[0]["status"] == "payable"


def test_build_rows_for_asset_skips_zero_dividends():
    asset = _make_asset()
    ts = pd.Timestamp("2025-01-15")
    divs = pd.Series([0.0], index=[ts])
    rows = _build_rows_for_asset(asset, divs, {}, date(2026, 1, 1))
    assert len(rows) == 0


def test_build_rows_for_asset_adds_upcoming_from_calendar():
    asset = _make_asset()
    divs = pd.Series([0.25], index=[pd.Timestamp("2025-01-15")])
    cal = {
        "Ex-Dividend Date": pd.Timestamp("2099-06-01"),
        "Dividend Date": pd.Timestamp("2099-06-15"),
    }
    rows = _build_rows_for_asset(asset, divs, cal, date(2026, 1, 1))
    upcoming = [r for r in rows if r["ex_date"] == date(2099, 6, 1)]
    assert len(upcoming) == 1
    assert upcoming[0]["status"] == "upcoming"
    assert upcoming[0]["pay_date"] == date(2099, 6, 15)
