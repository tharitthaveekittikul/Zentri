import math
from worker.jobs.watchlist_scan import _parse_scan_response


def test_valid_buy_response():
    raw = '{"verdict": "BUY", "suggested_price": 150.5, "reasoning": "strong momentum"}'
    result = _parse_scan_response(raw)
    assert result == {"verdict": "BUY", "suggested_price": 150.5, "reasoning": "strong momentum"}


def test_valid_hold_response_with_price():
    raw = '{"verdict": "HOLD", "suggested_price": 200.0, "reasoning": "wait for pullback"}'
    result = _parse_scan_response(raw)
    assert result["verdict"] == "HOLD"
    assert result["suggested_price"] == 200.0


def test_missing_suggested_price_accepted():
    raw = '{"verdict": "BUY", "reasoning": "good stock"}'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result.get("suggested_price") is None


def test_null_suggested_price_accepted():
    raw = '{"verdict": "HOLD", "suggested_price": null, "reasoning": "no price"}'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result["suggested_price"] is None


def test_string_suggested_price_returns_none():
    raw = '{"verdict": "BUY", "suggested_price": "150.5", "reasoning": "ok"}'
    assert _parse_scan_response(raw) is None


def test_nan_suggested_price_returns_none():
    import json
    data = {"verdict": "BUY", "suggested_price": float("inf"), "reasoning": "x"}
    raw = json.dumps(data)
    assert _parse_scan_response(raw) is None


def test_code_block_wrapping_still_works():
    raw = '```json\n{"verdict": "HOLD", "suggested_price": 99.99, "reasoning": "fair value"}\n```'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result["suggested_price"] == 99.99


def test_avoid_verdict_with_price():
    raw = '{"verdict": "AVOID", "suggested_price": 50.0, "reasoning": "overvalued"}'
    result = _parse_scan_response(raw)
    assert result is not None
    assert result["verdict"] == "AVOID"


def test_invalid_verdict_returns_none():
    raw = '{"verdict": "MAYBE", "suggested_price": 100.0, "reasoning": "dunno"}'
    assert _parse_scan_response(raw) is None


def test_malformed_json_returns_none():
    assert _parse_scan_response("not json at all") is None


def test_bool_suggested_price_returns_none():
    raw = '{"verdict": "BUY", "suggested_price": true, "reasoning": "ok"}'
    assert _parse_scan_response(raw) is None


def test_missing_reasoning_returns_none():
    raw = '{"verdict": "BUY", "suggested_price": 150.0}'
    assert _parse_scan_response(raw) is None
