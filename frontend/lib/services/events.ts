import { api } from "@/lib/api";

export type DividendCalendarEvent = {
  event_type: "dividend";
  id: string;
  symbol: string;
  asset_id: string;
  event_date: string;
  pay_date: string | null;
  amount_per_share: string;
  currency: string;
  status: "upcoming" | "payable" | "paid";
  projected_total_usd: string;
  quantity_held: string;
  is_in_watchlist: boolean;
};

export type IpoCalendarEvent = {
  event_type: "ipo";
  id: string;
  symbol: string;
  event_date: string;
  company_name: string | null;
  price_low: string | null;
  price_high: string | null;
  sector: string | null;
  status: "upcoming" | "priced" | "listed";
  is_in_watchlist: boolean;
};

export type CalendarEvent = DividendCalendarEvent | IpoCalendarEvent;

export type EventsMonthGroup = {
  year: number;
  month: number;
  events: CalendarEvent[];
};

export type EventsCalendarResponse = {
  months: EventsMonthGroup[];
};

export type IpoAnalysisResult = {
  verdict: "BUY" | "WATCH" | "SKIP";
  suggested_price: string | null;
  reasoning: string;
  provider: string;
  model: string;
  cached: boolean;
};

export async function fetchEventsCalendar(months = 3): Promise<EventsCalendarResponse> {
  const res = await api.get(`/api/v1/events/calendar?months=${months}`);
  if (!res.ok) throw new Error("Failed to fetch events calendar");
  return res.json();
}

export async function analyzeIpo(
  eventId: string,
  force = false
): Promise<IpoAnalysisResult> {
  const res = await api.post(
    `/api/v1/ipos/${eventId}/analyze${force ? "?force=true" : ""}`,
    {}
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}
