import { api } from "@/lib/api";

export interface DisplaySettings {
  currency_primary: string;
  currency_secondary: string;
}

export interface ExchangeRate {
  from: string;
  to: string;
  rate: string;
}

export async function fetchDisplaySettings(): Promise<DisplaySettings> {
  const res = await api.get("/api/v1/settings/display");
  if (!res.ok) throw new Error("Failed to fetch display settings");
  return res.json();
}

export async function fetchExchangeRate(
  fromCurrency: string,
  toCurrency: string
): Promise<ExchangeRate> {
  const res = await api.get(
    `/api/v1/settings/exchange-rate?from_currency=${fromCurrency}&to_currency=${toCurrency}`
  );
  if (!res.ok) throw new Error("Exchange rate unavailable");
  return res.json();
}
