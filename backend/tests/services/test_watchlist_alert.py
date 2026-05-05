import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.encryption import encrypt
from app.services.watchlist_alert import check_and_notify


def _item(target_price=Decimal("100"), alerted_at=None, alert_enabled=True):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.target_price = target_price
    m.alerted_at = alerted_at
    m.alert_enabled = alert_enabled
    return m


def _asset(symbol="AAPL", name="Apple Inc.", currency="USD"):
    m = MagicMock()
    m.symbol = symbol
    m.name = name
    m.currency = currency
    return m


def _price(close=Decimal("99")):
    m = MagicMock()
    m.close = close
    return m


def _user(has_telegram=True):
    m = MagicMock()
    if has_telegram:
        m.telegram_bot_token = encrypt("fake_token_abc")
        m.telegram_chat_id = "987654321"
    else:
        m.telegram_bot_token = None
        m.telegram_chat_id = None
    return m


@pytest.mark.asyncio
async def test_alert_sent_when_price_hits_target():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("99")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 1
    assert item.alerted_at is not None
    mock_send.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_no_alert_when_price_above_target():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("110")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    assert item.alerted_at is None
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_when_no_telegram_config():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), _price(close=Decimal("95")), _user(has_telegram=False))]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_no_alert_when_price_is_none():
    item = _item(target_price=Decimal("100"))
    rows = [(item, _asset(), None, _user())]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.watchlist_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_continues_after_send_failure():
    item1 = _item(target_price=Decimal("100"))
    item2 = _item(target_price=Decimal("50"))
    rows = [
        (item1, _asset("AAPL"), _price(Decimal("90")), _user()),
        (item2, _asset("BTC"), _price(Decimal("45")), _user()),
    ]
    mock_db = AsyncMock()

    with patch("app.services.watchlist_alert._fetch_pending_rows", return_value=rows):
        with patch(
            "app.services.watchlist_alert.send_message",
            new_callable=AsyncMock,
            side_effect=[RuntimeError("network error"), None],
        ):
            count = await check_and_notify(mock_db)

    assert count == 1
    assert item1.alerted_at is None
    assert item2.alerted_at is not None
