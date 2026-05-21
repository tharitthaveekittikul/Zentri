from unittest.mock import MagicMock
import pytest
from worker.jobs.run_top_down_analysis import _parse_top_down


def test_parse_top_down_valid():
    content = """{
        "mega_trend": "AI boom pulling back 25% from ATH",
        "financial_health": "Revenue +18% YoY, strong margins",
        "swot": {
            "strengths": ["Market leader", "Strong brand"],
            "weaknesses": ["High valuation"],
            "opportunities": ["AI services expansion"],
            "threats": ["Regulatory risk"]
        },
        "verdict": "BUY",
        "target_price": 210.0
    }"""
    result = _parse_top_down(content)
    assert result is not None
    assert result["verdict"] == "BUY"
    assert result["swot"]["strengths"] == ["Market leader", "Strong brand"]
    assert result["target_price"] == 210.0


def test_parse_top_down_invalid_verdict():
    content = '{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}, "verdict": "MAYBE", "target_price": null}'
    assert _parse_top_down(content) is None


def test_parse_top_down_missing_swot_key():
    content = '{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": []}, "verdict": "HOLD", "target_price": null}'
    assert _parse_top_down(content) is None


def test_parse_top_down_markdown_wrapped():
    content = '```json\n{"mega_trend": "x", "financial_health": "y", "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}, "verdict": "SELL", "target_price": null}\n```'
    result = _parse_top_down(content)
    assert result is not None
    assert result["verdict"] == "SELL"
