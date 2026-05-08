import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.services.net_worth_snapshot import compute_snapshot, _replay_transactions


def _holding(asset_id_hex: str, quantity: str, avg_cost: str):
    h = MagicMock()
    h.asset_id = uuid.UUID(asset_id_hex)
    h.quantity = Decimal(quantity)
    h.avg_cost_price = Decimal(avg_cost)
    return h


def _tx(asset_id: uuid.UUID, type_: str, qty: str, day: int):
    tx = MagicMock()
    tx.asset_id = asset_id
    tx.type = type_
    tx.quantity = Decimal(qty)
    tx.executed_at = datetime(2026, 4, day, 12, 0, 0, tzinfo=timezone.utc)
    return tx


AID1 = "aaaaaaaa-0000-0000-0000-000000000001"
AID2 = "aaaaaaaa-0000-0000-0000-000000000002"
UID1 = uuid.UUID(AID1)
UID2 = uuid.UUID(AID2)


# --- compute_snapshot tests ---

def test_compute_snapshot_sums_value_and_cost():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {UID1: Decimal("120"), UID2: Decimal("60")}
    rate_map = {UID1: Decimal("1"), UID2: Decimal("1")}
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("1320")
    assert result["total_cost_usd"] == Decimal("1100")


def test_compute_snapshot_applies_fx_rate():
    holdings = [_holding(AID1, "10", "100")]
    price_map = {UID1: Decimal("100")}
    rate_map = {UID1: Decimal("0.03")}
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("30")
    assert result["total_cost_usd"] == Decimal("30")


def test_compute_snapshot_skips_holdings_without_price():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {UID1: Decimal("120")}
    rate_map = {UID1: Decimal("1"), UID2: Decimal("1")}
    result = compute_snapshot(holdings, price_map, rate_map)
    assert result["total_value_usd"] == Decimal("1200")
    assert result["total_cost_usd"] == Decimal("1000")


def test_compute_snapshot_returns_none_when_no_prices():
    holdings = [_holding(AID1, "10", "100")]
    rate_map = {UID1: Decimal("1")}
    result = compute_snapshot(holdings, {}, rate_map)
    assert result is None


def test_compute_snapshot_returns_none_for_empty_holdings():
    result = compute_snapshot([], {}, {})
    assert result is None


# --- _replay_transactions tests ---

def test_replay_buy_only():
    txs = [_tx(UID1, "buy", "10", 1)]
    result = _replay_transactions(txs, date(2026, 4, 5))
    assert result[UID1] == Decimal("10")


def test_replay_buy_then_sell():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "sell", "3", 5)]
    assert _replay_transactions(txs, date(2026, 4, 3))[UID1] == Decimal("10")
    assert _replay_transactions(txs, date(2026, 4, 5))[UID1] == Decimal("7")


def test_replay_reward_adds_quantity():
    txs = [_tx(UID1, "buy", "5", 1), _tx(UID1, "reward", "2", 3)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("7")


def test_replay_future_txs_excluded():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "buy", "5", 20)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("10")


def test_replay_fully_sold_returns_zero():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID1, "sell", "10", 5)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("0")


def test_replay_multiple_assets():
    txs = [_tx(UID1, "buy", "10", 1), _tx(UID2, "buy", "5", 2)]
    result = _replay_transactions(txs, date(2026, 4, 10))
    assert result[UID1] == Decimal("10")
    assert result[UID2] == Decimal("5")
