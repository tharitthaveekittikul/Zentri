"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDisplaySettings, fetchExchangeRate } from "@/lib/services/settings";

export interface DualValue {
  primary: string;
  secondary: string | null;
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

  function format(value: string | number): DualValue {
    const num = Number(value);
    const primary = `${fmt(num)} ${primaryCurrency}`;

    let secondary: string | null = null;
    if (rateData) {
      const converted = num * Number(rateData.rate);
      secondary = `≈ ${fmt(converted)} ${secondaryCurrency}`;
    }

    return { primary, secondary };
  }

  function formatPct(value: string | number): string {
    const num = Number(value);
    return `${num >= 0 ? "+" : ""}${fmt(num)}%`;
  }

  return { format, formatPct, primaryCurrency, secondaryCurrency };
}
