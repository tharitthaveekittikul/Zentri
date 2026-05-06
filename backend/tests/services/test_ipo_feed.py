import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ipo_feed import extract_ipo_info


def test_extract_ipo_info_with_valid_data():
    info = {
        "ipoDate": "2026-06-15",
        "longName": "Acme Corp",
        "sector": "Technology",
        "fiftyTwoWeekLow": 10.0,
        "fiftyTwoWeekHigh": 15.0,
    }
    result = extract_ipo_info("ACME", info)
    assert result is not None
    assert result["symbol"] == "ACME"
    assert result["company_name"] == "Acme Corp"
    assert result["ipo_date"] == date(2026, 6, 15)
    assert result["sector"] == "Technology"


def test_extract_ipo_info_with_no_ipo_date():
    info = {"longName": "No Date Corp"}
    result = extract_ipo_info("NDC", info)
    assert result is None


def test_extract_ipo_info_with_past_ipo_date():
    info = {"ipoDate": "2020-01-01", "longName": "Old Corp"}
    result = extract_ipo_info("OLD", info)
    assert result is None
