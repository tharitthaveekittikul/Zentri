export interface ModelPricing {
  inputPerMToken: number;
  outputPerMToken: number;
}

export const MODEL_PRICING: Record<string, ModelPricing> = {
  // Anthropic (4.x Frontier)
  "claude-opus-4-7": { inputPerMToken: 5.0, outputPerMToken: 25.0 }, // Slashed from $15/$75
  "claude-sonnet-4-6": { inputPerMToken: 3.0, outputPerMToken: 15.0 },
  "claude-haiku-4-5-20251001": { inputPerMToken: 1.0, outputPerMToken: 5.0 },

  // OpenAI (GPT-5 & 4o Series)
  "gpt-5": { inputPerMToken: 5.0, outputPerMToken: 20.0 }, // New flagship
  "gpt-5.4": { inputPerMToken: 2.5, outputPerMToken: 15.0 },
  "gpt-5.4-pro": { inputPerMToken: 30.0, outputPerMToken: 180.0 },
  "gpt-4o": { inputPerMToken: 2.5, outputPerMToken: 10.0 },
  "gpt-4o-mini": { inputPerMToken: 0.15, outputPerMToken: 0.6 },
  "o3-mini": { inputPerMToken: 1.1, outputPerMToken: 4.4 }, // Reasoning-focused mini

  // Google Gemini (3.0 & 2.5)
  "gemini-3-pro": { inputPerMToken: 2.0, outputPerMToken: 12.0 }, // ≤200k context
  "gemini-3-flash": { inputPerMToken: 0.5, outputPerMToken: 3.0 },
  "gemini-3.1-pro": { inputPerMToken: 2.0, outputPerMToken: 12.0 },
  "gemini-3.1-flash-lite": { inputPerMToken: 0.1, outputPerMToken: 0.4 },
  "gemini-2.5-pro": { inputPerMToken: 1.25, outputPerMToken: 10.0 },
  "gemini-2.5-flash": { inputPerMToken: 0.3, outputPerMToken: 2.5 },
  "gemini-2.5-flash-lite": { inputPerMToken: 0.1, outputPerMToken: 0.4 },
};

const CHARS_PER_TOKEN = 4;

export function estimateTokens(text: string): number {
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

export function estimateCostUsd(
  model: string,
  inputTokens: number,
  outputTokens: number,
): number {
  const pricing = MODEL_PRICING[model];
  if (!pricing) return 0;
  return (
    (inputTokens / 1_000_000) * pricing.inputPerMToken +
    (outputTokens / 1_000_000) * pricing.outputPerMToken
  );
}

export function getPricingForModel(model: string): ModelPricing | null {
  if (MODEL_PRICING[model]) return MODEL_PRICING[model];
  const lower = model.toLowerCase();
  for (const [key, pricing] of Object.entries(MODEL_PRICING)) {
    if (
      lower.includes(key.toLowerCase()) ||
      key.toLowerCase().includes(lower)
    ) {
      return pricing;
    }
  }
  return null;
}
