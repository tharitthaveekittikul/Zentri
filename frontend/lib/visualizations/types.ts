export type ViewMode = "table" | "grid" | "swarm" | "bubbles";

export interface PortfolioViewItem {
  symbol: string;
  val: number;
  pnlPct: number;
  portfolioPct: number;
  displayValue: string;
  logoUrl?: string;
}

export interface TreemapCell extends PortfolioViewItem {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface VisDot extends PortfolioViewItem {
  x: number;
  y: number;
  radius: number;
}

export function getHoldingColor(pnlPct: number): { bg: string; accent: string } {
  // matches project brand tokens: --brand-mid / --brand-sage for gain, --brand-danger for loss
  if (pnlPct > 0) return { bg: "#227d53", accent: "#5fbd92" };
  if (pnlPct < 0) return { bg: "#9b2335", accent: "#F43F5E" };
  return { bg: "#4b5563", accent: "#6b7280" };
}

export interface CurrencyOptions {
  primaryCurrency?: string;
  secondaryCurrency?: string;
  // rate = secondary / primary (e.g. USD/THB ≈ 0.028)
  exchangeRate?: number;
}

export function holdingsToViewItems(
  holdings: Array<{
    symbol: string;
    asset_type: string;
    currency: string;
    holding_value: string | null;
    unrealized_pnl: string | null;
    total_cost: string;
    metadata_?: Record<string, unknown>;
  }>,
  options?: CurrencyOptions,
): PortfolioViewItem[] {
  const toPrimary = (value: number, currency: string): number => {
    if (!options?.primaryCurrency) return value;
    const curr = currency.toUpperCase();
    const primary = options.primaryCurrency.toUpperCase();
    const secondary = options.secondaryCurrency?.toUpperCase();
    if (curr === primary) return value;
    if (curr === secondary && options.exchangeRate && options.exchangeRate > 0) {
      return value / options.exchangeRate;
    }
    return value;
  };

  const items = holdings
    .filter(
      (h) =>
        h.asset_type !== "cash" &&
        h.holding_value != null &&
        Number(h.holding_value) > 0,
    )
    .map((h) => {
      const nativeVal = Number(h.holding_value);
      const primaryVal = toPrimary(nativeVal, h.currency);
      return {
        symbol: h.symbol,
        val: primaryVal,
        pnlPct:
          Number(h.total_cost) > 0
            ? (Number(h.unrealized_pnl ?? 0) / Number(h.total_cost)) * 100
            : 0,
        displayValue:
          primaryVal.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          }) + (options?.primaryCurrency ? ` ${options.primaryCurrency}` : ""),
        logoUrl: h.metadata_?.logo_url as string | undefined,
      };
    });

  const total = items.reduce((sum, i) => sum + i.val, 0);
  return items.map((i) => ({
    ...i,
    portfolioPct: total > 0 ? (i.val / total) * 100 : 0,
  }));
}
