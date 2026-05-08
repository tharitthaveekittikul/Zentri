PRICING: dict[str, tuple[float, float]] = {
    # (input_per_mtoken_usd, output_per_mtoken_usd)
    # Anthropic
    "claude-sonnet-4-6":         (3.0,   15.0),
    "claude-opus-4-7":           (5.0,   25.0),
    "claude-haiku-4-5-20251001": (1.0,    5.0),
    # OpenAI GPT-5 series
    "gpt-5.5":                   (5.0,   30.0),
    "gpt-5.4":                   (2.5,   15.0),
    "gpt-5.4-mini":              (0.75,   4.5),
    "gpt-5.4-nano":              (0.2,    1.25),
    # OpenAI GPT-4o series (legacy)
    "gpt-4o":                    (2.5,   10.0),
    "gpt-4o-mini":               (0.15,   0.6),
    # Google Gemini 2.5 series
    "gemini-2.5-pro":            (1.25,  10.0),
    "gemini-2.5-flash":          (0.3,    2.5),
    "gemini-2.5-flash-lite":     (0.1,    0.4),
    # Google Gemini 3 series
    "gemini-3.1-flash-lite":     (0.25,   1.5),
    # Google Gemini 1.5 / 2.0 series (legacy / deprecated)
    "gemini-1.5-pro":            (1.25,   5.0),
    "gemini-1.5-flash":          (0.075,  0.3),
    "gemini-2.0-flash":          (0.1,    0.4),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    in_rate, out_rate = PRICING[model]
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
