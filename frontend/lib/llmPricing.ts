// frontend/lib/llmPricing.ts
export interface ModelPricing {
  inputPerMToken: number;
  outputPerMToken: number;
}

// Bundled fallback — used synchronously before fetch completes or on fetch failure.
// Keep in sync with backend/app/core/llm_pricing.py whenever models change.
const BUNDLED_PRICING: Record<string, ModelPricing> = {
  // Anthropic
  "claude-opus-4-7":           { inputPerMToken: 5.0,   outputPerMToken: 25.0  },
  "claude-sonnet-4-6":         { inputPerMToken: 3.0,   outputPerMToken: 15.0  },
  "claude-haiku-4-5-20251001": { inputPerMToken: 1.0,   outputPerMToken: 5.0   },
  // OpenAI GPT-5 series
  "gpt-5":                     { inputPerMToken: 5.0,   outputPerMToken: 20.0  },
  "gpt-5.5":                   { inputPerMToken: 5.0,   outputPerMToken: 30.0  },
  "gpt-5.4":                   { inputPerMToken: 2.5,   outputPerMToken: 15.0  },
  "gpt-5.4-pro":               { inputPerMToken: 30.0,  outputPerMToken: 180.0 },
  "gpt-5.4-mini":              { inputPerMToken: 0.75,  outputPerMToken: 4.5   },
  "gpt-5.4-nano":              { inputPerMToken: 0.2,   outputPerMToken: 1.25  },
  // OpenAI GPT-4o series
  "gpt-4o":                    { inputPerMToken: 2.5,   outputPerMToken: 10.0  },
  "gpt-4o-mini":               { inputPerMToken: 0.15,  outputPerMToken: 0.6   },
  // OpenAI reasoning
  "o3-mini":                   { inputPerMToken: 1.1,   outputPerMToken: 4.4   },
  // Google Gemini 3.x series
  "gemini-3-pro":              { inputPerMToken: 2.0,   outputPerMToken: 12.0  },
  "gemini-3-flash":            { inputPerMToken: 0.5,   outputPerMToken: 3.0   },
  "gemini-3.1-pro":            { inputPerMToken: 2.0,   outputPerMToken: 12.0  },
  "gemini-3.1-flash-lite":     { inputPerMToken: 0.25,  outputPerMToken: 1.5   },
  // Google Gemini 2.5 series
  "gemini-2.5-pro":            { inputPerMToken: 1.25,  outputPerMToken: 10.0  },
  "gemini-2.5-flash":          { inputPerMToken: 0.3,   outputPerMToken: 2.5   },
  "gemini-2.5-flash-lite":     { inputPerMToken: 0.1,   outputPerMToken: 0.4   },
  // Google Gemini legacy
  "gemini-1.5-pro":            { inputPerMToken: 1.25,  outputPerMToken: 5.0   },
  "gemini-1.5-flash":          { inputPerMToken: 0.075, outputPerMToken: 0.3   },
  "gemini-2.0-flash":          { inputPerMToken: 0.1,   outputPerMToken: 0.4   },
};

let _cache: Record<string, ModelPricing> = { ...BUNDLED_PRICING };
let _loading = false;
let _loaded = false;

export async function loadPricing(): Promise<void> {
  if (_loaded || _loading) return;
  _loading = true;
  try {
    const res = await fetch("/api/v1/llm/pricing");
    if (!res.ok) return;
    const data: Record<string, { input_per_mtoken: number; output_per_mtoken: number }> =
      await res.json();
    _cache = {
      ...BUNDLED_PRICING,
      ...Object.fromEntries(
        Object.entries(data).map(([model, p]) => [
          model,
          { inputPerMToken: p.input_per_mtoken, outputPerMToken: p.output_per_mtoken },
        ])
      ),
    };
    _loaded = true;
  } catch {
    // silently keep bundled fallback
  } finally {
    _loading = false;
  }
}

const CHARS_PER_TOKEN = 4;

export function estimateTokens(text: string): number {
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

export function getPricingForModel(model: string): ModelPricing | null {
  if (_cache[model]) return _cache[model];
  const lower = model.toLowerCase();
  for (const [key, pricing] of Object.entries(_cache)) {
    if (lower.includes(key.toLowerCase()) || key.toLowerCase().includes(lower)) {
      return pricing;
    }
  }
  return null;
}

export function estimateCostUsd(
  model: string,
  inputTokens: number,
  outputTokens: number,
): number {
  const pricing = getPricingForModel(model);
  if (!pricing) return 0;
  return (
    (inputTokens / 1_000_000) * pricing.inputPerMToken +
    (outputTokens / 1_000_000) * pricing.outputPerMToken
  );
}
