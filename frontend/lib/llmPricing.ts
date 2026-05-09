// frontend/lib/llmPricing.ts
export interface ModelPricing {
  inputPerMToken: number;
  outputPerMToken: number;
}

// Bundled fallback — used synchronously before fetch completes or on fetch failure.
// Keep in sync with backend/app/core/llm_pricing.py whenever models change.
const BUNDLED_PRICING: Record<string, ModelPricing> = {
  // Anthropic Claude 4 Series
  "claude-opus-4-7":               { inputPerMToken: 5.0,   outputPerMToken: 25.0 },
  "claude-opus-4-6":               { inputPerMToken: 5.0,   outputPerMToken: 25.0 },
  "claude-sonnet-4-6":             { inputPerMToken: 3.0,   outputPerMToken: 15.0 },
  "claude-haiku-4-5-20251001":     { inputPerMToken: 1.0,   outputPerMToken: 5.0  },
  // OpenAI GPT-5 & Reasoning Series
  "gpt-5.5":                       { inputPerMToken: 5.0,   outputPerMToken: 30.0 },
  "gpt-5.4":                       { inputPerMToken: 2.5,   outputPerMToken: 15.0 },
  "gpt-5.4-mini":                  { inputPerMToken: 0.75,  outputPerMToken: 4.5  },
  "gpt-5.4-nano":                  { inputPerMToken: 0.2,   outputPerMToken: 1.25 },
  "o3-deep-research":              { inputPerMToken: 10.0,  outputPerMToken: 40.0 },
  "o3":                            { inputPerMToken: 2.0,   outputPerMToken: 8.0  },
  "o3-mini":                       { inputPerMToken: 1.1,   outputPerMToken: 4.4  },
  "o1":                            { inputPerMToken: 15.0,  outputPerMToken: 60.0 },
  // Google Gemini 3 Series
  "gemini-3.1-pro-preview":        { inputPerMToken: 2.0,   outputPerMToken: 12.0 },
  "gemini-3.1-flash-lite-preview": { inputPerMToken: 0.25,  outputPerMToken: 1.5  },
  "gemini-3-flash-preview":        { inputPerMToken: 0.5,   outputPerMToken: 3.0  },
  // Google Gemini 2.5 Series
  "gemini-2.5-pro":                { inputPerMToken: 1.25,  outputPerMToken: 10.0 },
  "gemini-2.5-flash":              { inputPerMToken: 0.3,   outputPerMToken: 2.5  },
  "gemini-2.5-flash-lite":         { inputPerMToken: 0.1,   outputPerMToken: 0.4  },
  // OpenAI Legacy / Special Series
  "gpt-4.1":                       { inputPerMToken: 2.0,   outputPerMToken: 8.0  },
  "gpt-4.1-mini":                  { inputPerMToken: 0.4,   outputPerMToken: 1.6  },
  "gpt-4.1-nano":                  { inputPerMToken: 0.1,   outputPerMToken: 0.4  },
  "gpt-4o":                        { inputPerMToken: 2.5,   outputPerMToken: 10.0 },
  "gpt-4o-mini":                   { inputPerMToken: 0.15,  outputPerMToken: 0.6  },
  "gpt-3.5-turbo":                 { inputPerMToken: 0.5,   outputPerMToken: 1.5  },
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
