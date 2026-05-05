import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from app.services.net_worth_snapshot import compute_snapshot


def _holding(asset_id_hex: str, quantity: str, avg_cost: str):
    h = MagicMock()
    h.asset_id = uuid.UUID(asset_id_hex)
    h.quantity = Decimal(quantity)
    h.avg_cost_price = Decimal(avg_cost)
    return h


AID1 = "aaaaaaaa-0000-0000-0000-000000000001"
AID2 = "aaaaaaaa-0000-0000-0000-000000000002"


def test_compute_snapshot_sums_value_and_cost():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {uuid.UUID(AID1): Decimal("120"), uuid.UUID(AID2): Decimal("60")}
    result = compute_snapshot(holdings, price_map)
    assert result["total_value_usd"] == Decimal("1320")  # 10*120 + 2*60
    assert result["total_cost_usd"] == Decimal("1100")   # 10*100 + 2*50


def test_compute_snapshot_skips_holdings_without_price():
    holdings = [_holding(AID1, "10", "100"), _holding(AID2, "2", "50")]
    price_map = {uuid.UUID(AID1): Decimal("120")}  # AID2 has no price
    result = compute_snapshot(holdings, price_map)
    assert result["total_value_usd"] == Decimal("1200")
    assert result["total_cost_usd"] == Decimal("1000")


def test_compute_snapshot_returns_none_when_no_prices():
    holdings = [_holding(AID1, "10", "100")]
    result = compute_snapshot(holdings, {})
    assert result is None


def test_compute_snapshot_returns_none_for_empty_holdings():
    result = compute_snapshot([], {})
    assert result is None
