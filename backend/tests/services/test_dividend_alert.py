import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.encryption import encrypt
from app.services.dividend_alert import check_and_notify


def _event(notified_at=None, amount=Decimal("0.26"), currency="USD"):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.ex_date = "2026-05-11"
    m.amount_per_share = amount
    m.currency = currency
    m.dividend_notified_at = notified_at
    return m


def _asset(symbol="AAPL", name="Apple Inc."):
    m = MagicMock()
    m.symbol = symbol
    m.name = name
    return m


def _holding(quantity=Decimal("50")):
    m = MagicMock()
    m.quantity = quantity
    return m


def _user(has_telegram=True, secondary="THB"):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.currency_secondary = secondary
    if has_telegram:
        m.telegram_bot_token = encrypt("fake_bot_token")
        m.telegram_chat_id = "123456789"
    else:
        m.telegram_bot_token = None
        m.telegram_chat_id = None
    return m


@pytest.mark.asyncio
async def test_notification_sent_for_held_stock():
    event = _event()
    rows = [(event, _asset(), _holding(Decimal("50")), _user())]
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            with patch("app.services.dividend_alert.get_rate", new_callable=AsyncMock, return_value=Decimal("32.3")):
                count = await check_and_notify(mock_db)

    assert count == 1
    assert event.dividend_notified_at is not None
    mock_send.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_no_notification_when_no_telegram():
    event = _event()
    rows = [(event, _asset(), _holding(Decimal("10")), _user(has_telegram=False))]
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    assert event.dividend_notified_at is None
    mock_send.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_notification_message_contains_symbol_and_total():
    event = _event(amount=Decimal("0.26"), currency="USD")
    rows = [(event, _asset(symbol="AAPL"), _holding(Decimal("50")), _user())]
    mock_db = AsyncMock()
    captured = {}

    async def capture_send(token, chat_id, text):
        captured["text"] = text

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", side_effect=capture_send):
            with patch("app.services.dividend_alert.get_rate", new_callable=AsyncMock, return_value=Decimal("32.3")):
                await check_and_notify(mock_db)

    assert "AAPL" in captured["text"]
    assert "13.00" in captured["text"]   # 50 × 0.26


@pytest.mark.asyncio
async def test_no_rows_returns_zero():
    mock_db = AsyncMock()

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=[]):
        with patch("app.services.dividend_alert.send_message", new_callable=AsyncMock) as mock_send:
            count = await check_and_notify(mock_db)

    assert count == 0
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_failed_send_does_not_block_subsequent_rows():
    event1 = _event()
    event2 = _event()
    rows = [
        (event1, _asset(symbol="AAPL"), _holding(Decimal("10")), _user()),
        (event2, _asset(symbol="MSFT"), _holding(Decimal("20")), _user()),
    ]
    mock_db = AsyncMock()
    call_count = 0

    async def fail_first_then_succeed(token, chat_id, text):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Telegram timeout")

    with patch("app.services.dividend_alert._fetch_pending_rows", return_value=rows):
        with patch("app.services.dividend_alert.send_message", side_effect=fail_first_then_succeed):
            with patch("app.services.dividend_alert.get_rate", new_callable=AsyncMock, return_value=Decimal("32.3")):
                count = await check_and_notify(mock_db)

    assert count == 1
    assert event1.dividend_notified_at is None
    assert event2.dividend_notified_at is not None
