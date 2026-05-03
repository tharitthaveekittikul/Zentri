from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from app.services.exchange_rate import get_historical_usd_thb, get_current_usd_thb


@pytest.mark.asyncio
async def test_get_historical_usd_thb_returns_rate():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"usd": {"thb": 35.9775}}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result == Decimal("35.9775")


@pytest.mark.asyncio
async def test_get_historical_usd_thb_uses_cache():
    mock_db = AsyncMock()
    cached_row = MagicMock()
    cached_row.rate = Decimal("36.0")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = cached_row
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result == Decimal("36.0")
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_historical_usd_thb_returns_none_on_api_failure():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await get_historical_usd_thb(mock_db, date(2022, 11, 28))

    assert result is None
