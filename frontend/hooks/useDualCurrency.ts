"use client";

import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchDisplaySettings, fetchExchangeRate } from "@/lib/services/settings";

export interface DualValue {
  primary: string;
  secondary: string | null;
  primaryCurrency: string;
  secondaryCurrency: string;
}

function fmt(num: number, decimals = 2): string {
  return num.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
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

  // Use when the value is already in primaryCurrency.
  const format = useCallback(
    (value: string | number): DualValue => {
      const num = Number(value);
      const primary = `${fmt(num)} ${primaryCurrency}`;
      let secondary: string | null = null;
      if (rateData) {
        const converted = num * Number(rateData.rate);
        secondary = `≈ ${fmt(converted)} ${secondaryCurrency}`;
      }
      return { primary, secondary, primaryCurrency, secondaryCurrency };
    },
    [rateData, primaryCurrency, secondaryCurrency],
  );

  // Use when the value is in a native asset currency that may differ from primaryCurrency.
  // Converts to primary (and secondary) if the native currency matches one of the two.
  // Falls back to native currency label when no conversion is possible.
  const formatNative = useCallback(
    (value: string | number, nativeCurrency: string, decimals = 2, showSign = false): DualValue => {
      const num = Number(value);
      const native = nativeCurrency.toUpperCase();
      const primary = primaryCurrency.toUpperCase();
      const secondary = secondaryCurrency.toUpperCase();
      const rate = rateData ? Number(rateData.rate) : null;
      const sign = showSign && num >= 0 ? "+" : "";

      if (native === primary) {
        const p = `${sign}${fmt(num, decimals)} ${primaryCurrency}`;
        const s = rate ? `≈ ${sign}${fmt(num * rate, decimals)} ${secondaryCurrency}` : null;
        return { primary: p, secondary: s, primaryCurrency, secondaryCurrency };
      }

      if (native === secondary && rate !== null && rate > 0) {
        const primaryVal = num / rate;
        return {
          primary: `${sign}${fmt(primaryVal, decimals)} ${primaryCurrency}`,
          secondary: `≈ ${sign}${fmt(num, decimals)} ${secondaryCurrency}`,
          primaryCurrency,
          secondaryCurrency,
        };
      }

      // Unknown currency pair — show native only.
      return {
        primary: `${sign}${fmt(num, decimals)} ${nativeCurrency}`,
        secondary: null,
        primaryCurrency,
        secondaryCurrency,
      };
    },
    [rateData, primaryCurrency, secondaryCurrency],
  );

  const formatPnl = useCallback(
    (value: string | number): DualValue => {
      const num = Number(value);
      const sign = num >= 0 ? "+" : "";
      const primary = `${sign}${fmt(num)} ${primaryCurrency}`;
      let secondary: string | null = null;
      if (rateData) {
        const converted = num * Number(rateData.rate);
        secondary = `≈ ${sign}${fmt(converted)} ${secondaryCurrency}`;
      }
      return { primary, secondary, primaryCurrency, secondaryCurrency };
    },
    [rateData, primaryCurrency, secondaryCurrency],
  );

  const formatPct = useCallback((value: string | number): string => {
    const num = Number(value);
    return `${fmt(Math.abs(num))}%`;
  }, []);

  return { format, formatNative, formatPnl, formatPct, primaryCurrency, secondaryCurrency };
}
