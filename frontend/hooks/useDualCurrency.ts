"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDisplaySettings, fetchExchangeRate } from "@/lib/services/settings";

export interface DualValue {
  primary: string;
  secondary: string | null;
  primaryCurrency: string;
  secondaryCurrency: string;
}

export function useDualCurrency() {
  const { data: display } = useQuery({
    queryKey: ["settings", "display"],
    queryFn: fetchDisplaySettings,
    staleTime: Infinity,
  });

  const primaryCurrency = display?.currency_primary ?? "THB";
  const secondaryCurrency = display?.currency_secondary ?? "USD";

  const { data: rateData } = useQuery({
    queryKey: ["settings", "exchange-rate", primaryCurrency, secondaryCurrency],
    queryFn: () => fetchExchangeRate(primaryCurrency, secondaryCurrency),
    enabled: !!display && primaryCurrency !== secondaryCurrency,
    staleTime: 60 * 60 * 1000,
  });

  function fmt(num: number, decimals = 2): string {
    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  // Use when the value is already in primaryCurrency.
  function format(value: string | number): DualValue {
    const num = Number(value);
    const primary = `${fmt(num)} ${primaryCurrency}`;

    let secondary: string | null = null;
    if (rateData) {
      const converted = num * Number(rateData.rate);
      secondary = `≈ ${fmt(converted)} ${secondaryCurrency}`;
    }

    return { primary, secondary, primaryCurrency, secondaryCurrency };
  }

  // Use when the value is in a native asset currency that may differ from primaryCurrency.
  // Converts to primary (and secondary) if the native currency matches one of the two.
  // Falls back to native currency label when no conversion is possible.
  function formatNative(value: string | number, nativeCurrency: string, decimals = 2): DualValue {
    const num = Number(value);
    const native = nativeCurrency.toUpperCase();
    const primary = primaryCurrency.toUpperCase();
    const secondary = secondaryCurrency.toUpperCase();
    const rate = rateData ? Number(rateData.rate) : null;

    if (native === primary) {
      const p = `${fmt(num, decimals)} ${primaryCurrency}`;
      const s = rate ? `≈ ${fmt(num * rate, decimals)} ${secondaryCurrency}` : null;
      return { primary: p, secondary: s, primaryCurrency, secondaryCurrency };
    }

    if (native === secondary && rate !== null && rate > 0) {
      const primaryVal = num / rate;
      return {
        primary: `${fmt(primaryVal, decimals)} ${primaryCurrency}`,
        secondary: `≈ ${fmt(num, decimals)} ${secondaryCurrency}`,
        primaryCurrency,
        secondaryCurrency,
      };
    }

    // Unknown currency pair — show native only.
    return {
      primary: `${fmt(num, decimals)} ${nativeCurrency}`,
      secondary: null,
      primaryCurrency,
      secondaryCurrency,
    };
  }

  function formatPnl(value: string | number): DualValue {
    const num = Number(value);
    const sign = num >= 0 ? "+" : "";
    const primary = `${sign}${fmt(num)} ${primaryCurrency}`;
    let secondary: string | null = null;
    if (rateData) {
      const converted = num * Number(rateData.rate);
      secondary = `≈ ${sign}${fmt(converted)} ${secondaryCurrency}`;
    }
    return { primary, secondary, primaryCurrency, secondaryCurrency };
  }

  function formatPct(value: string | number): string {
    const num = Number(value);
    return `${fmt(Math.abs(num))}%`;
  }

  return { format, formatNative, formatPnl, formatPct, primaryCurrency, secondaryCurrency };
}
