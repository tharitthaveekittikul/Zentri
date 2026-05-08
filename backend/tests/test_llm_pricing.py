import pytest
from app.core.llm_pricing import PRICING, calc_cost


def test_calc_cost_known_model():
    cost = calc_cost("claude-sonnet-4-6", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost == pytest.approx(18.0)  # 3.0 in + 15.0 out


def test_calc_cost_unknown_model_returns_zero():
    assert calc_cost("unknown-model-xyz", 100, 100) == 0.0


def test_pricing_covers_all_major_providers():
    providers = {m.split("-")[0] for m in PRICING}
    assert "claude" in providers
    assert "gpt" in providers
    assert "gemini" in providers


def test_all_models_have_positive_rates():
    for model, (inp, out) in PRICING.items():
        assert inp > 0, f"{model} input rate must be > 0"
        assert out > 0, f"{model} output rate must be > 0"
