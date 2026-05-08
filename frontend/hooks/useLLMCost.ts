"use client";

import { useMemo } from "react";
import { estimateCostUsd, estimateTokens, getPricingForModel } from "@/lib/llmPricing";

interface UseLLMCostOptions {
  model: string;
  estimatedInputText?: string;
  estimatedOutputTokens?: number;
  primaryCurrency?: string;
  primaryExchangeRate?: number;
  secondaryCurrency?: string;
  secondaryExchangeRate?: number;
}

interface LLMCostEstimate {
  inputTokens: number;
  outputTokens: number;
  costUsd: number;
  costPrimary: number | null;
  costSecondary: number | null;
  primaryCurrency: string;
  secondaryCurrency: string | null;
  hasPricing: boolean;
  formatted: string;
}

export function useLLMCost({
  model,
  estimatedInputText = "",
  estimatedOutputTokens = 500,
  primaryCurrency = "USD",
  primaryExchangeRate = 1,
  secondaryCurrency,
  secondaryExchangeRate,
}: UseLLMCostOptions): LLMCostEstimate {
  return useMemo(() => {
    const inputTokens = estimateTokens(estimatedInputText);
    const outputTokens = estimatedOutputTokens;
    const pricing = getPricingForModel(model);
    const hasPricing = !!pricing;
    const costUsd = hasPricing ? estimateCostUsd(model, inputTokens, outputTokens) : 0;

    const costPrimary =
      primaryCurrency === "USD" ? costUsd : costUsd * (primaryExchangeRate || 1);

    const costSecondary =
      secondaryCurrency && secondaryExchangeRate
        ? costUsd * secondaryExchangeRate
        : null;

    const formatCost = (cost: number, currency: string) => {
      if (cost < 0.01) return `< 0.01 ${currency}`;
      return `${cost.toFixed(2)} ${currency}`;
    };

    let formatted = hasPricing ? formatCost(costPrimary, primaryCurrency) : "Cost unknown";
    if (costSecondary !== null && secondaryCurrency && primaryCurrency !== secondaryCurrency) {
      formatted += ` / ${formatCost(costSecondary, secondaryCurrency)}`;
    }

    return {
      inputTokens,
      outputTokens,
      costUsd,
      costPrimary: hasPricing ? costPrimary : null,
      costSecondary,
      primaryCurrency,
      secondaryCurrency: secondaryCurrency ?? null,
      hasPricing,
      formatted,
    };
  }, [
    model, estimatedInputText, estimatedOutputTokens,
    primaryCurrency, primaryExchangeRate, secondaryCurrency, secondaryExchangeRate,
  ]);
}
