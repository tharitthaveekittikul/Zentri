PRICING: dict[str, tuple[float, float]] = {
    # Format: (input_per_mtoken_usd, output_per_mtoken_usd)

    # --- Anthropic Claude 4 Series ---
    "claude-opus-4-7":               (5.0,   25.0),
    "claude-opus-4-6":               (5.0,   25.0),
    "claude-sonnet-4-6":             (3.0,   15.0),
    "claude-haiku-4-5-20251001":     (1.0,    5.0),

    # --- OpenAI GPT-5 & Reasoning Series ---
    "gpt-5.5":                       (5.0,   30.0),
    "gpt-5.4":                       (2.5,   15.0),
    "gpt-5.4-mini":                  (0.75,   4.5),
    "gpt-5.4-nano":                  (0.2,    1.25),
    "o3-deep-research":              (10.0,  40.0),
    "o3":                            (2.0,    8.0),
    "o3-mini":                       (1.1,    4.4),
    "o1":                            (15.0,  60.0),

    # --- Google Gemini 3 Series ---
    "gemini-3.1-pro-preview":        (2.0,   12.0),
    "gemini-3.1-flash-lite-preview": (0.25,   1.5),
    "gemini-3-flash-preview":        (0.5,    3.0),

    # --- Google Gemini 2.5 Series ---
    "gemini-2.5-pro":                (1.25,  10.0),
    "gemini-2.5-flash":              (0.3,    2.5),
    "gemini-2.5-flash-lite":         (0.1,    0.4),

    # --- OpenAI Legacy / Special Series ---
    "gpt-4.1":                       (2.0,    8.0),
    "gpt-4.1-mini":                  (0.4,    1.6),
    "gpt-4.1-nano":                  (0.1,    0.4),
    "gpt-4o":                        (2.5,   10.0),
    "gpt-4o-mini":                   (0.15,   0.6),
    "gpt-3.5-turbo":                 (0.5,    1.5),
}


def calc_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    if model not in PRICING:
        return 0.0
    in_rate, out_rate = PRICING[model]
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
