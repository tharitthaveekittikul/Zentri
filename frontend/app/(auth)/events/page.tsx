"use client";

import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import {
  fetchEventsCalendar,
  analyzeIpo,
  CalendarEvent,
  DividendCalendarEvent,
  IpoCalendarEvent,
  IpoAnalysisResult,
} from "@/lib/services/events";
import { PageHeader } from "@/components/layout/PageHeader";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

type FilterType = "all" | "dividend" | "ipo" | "watchlist";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "bg-green-100 text-green-800",
  WATCH: "bg-yellow-100 text-yellow-800",
  SKIP: "bg-red-100 text-red-800",
};

const STATUS_BADGE: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-800",
  payable: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  priced: "bg-purple-100 text-purple-800",
  listed: "bg-gray-100 text-gray-800",
};

function filterEvents(events: CalendarEvent[], filter: FilterType): CalendarEvent[] {
  if (filter === "all") return events;
  if (filter === "dividend") return events.filter((e) => e.event_type === "dividend");
  if (filter === "ipo") return events.filter((e) => e.event_type === "ipo");
  if (filter === "watchlist") return events.filter((e) => e.is_in_watchlist);
  return events;
}

function CalendarGrid({
  events,
  onSelectDividend,
  onSelectIpo,
}: {
  events: CalendarEvent[];
  onSelectDividend: (e: DividendCalendarEvent) => void;
  onSelectIpo: (e: IpoCalendarEvent) => void;
}) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstDay = new Date(viewYear, viewMonth, 1).getDay();
  const isCurrentMonth = viewYear === today.getFullYear() && viewMonth === today.getMonth();

  const prev = () => {
    if (viewMonth === 0) { setViewYear((y) => y - 1); setViewMonth(11); }
    else setViewMonth((m) => m - 1);
  };
  const next = () => {
    if (viewMonth === 11) { setViewYear((y) => y + 1); setViewMonth(0); }
    else setViewMonth((m) => m + 1);
  };

  const byDay: Record<number, CalendarEvent[]> = {};
  for (const ev of events) {
    const d = new Date(ev.event_date);
    if (d.getFullYear() === viewYear && d.getMonth() === viewMonth) {
      const day = d.getDate();
      if (!byDay[day]) byDay[day] = [];
      byDay[day].push(ev);
    }
  }

  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <Button variant="ghost" size="icon" onClick={prev}><ChevronLeft className="h-4 w-4" /></Button>
        <span className="font-semibold text-sm">
          {MONTH_NAMES[viewMonth]} {viewYear}
          {isCurrentMonth && <span className="ml-2 text-xs text-muted-foreground">(current)</span>}
        </span>
        <Button variant="ghost" size="icon" onClick={next}><ChevronRight className="h-4 w-4" /></Button>
      </div>
      <div className="grid grid-cols-7 text-xs text-center text-muted-foreground border-b">
        {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
          <div key={d} className="py-1">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {cells.map((day, i) => (
          <div
            key={i}
            className={`min-h-[72px] border-b border-r p-1 text-xs ${!day ? "bg-muted/10" : ""} ${
              day === today.getDate() && isCurrentMonth ? "bg-blue-50" : ""
            }`}
          >
            {day && (
              <>
                <div className="text-muted-foreground mb-1">{day}</div>
                {(byDay[day] || []).map((ev) => (
                  <div
                    key={ev.id}
                    onClick={() =>
                      ev.event_type === "dividend"
                        ? onSelectDividend(ev as DividendCalendarEvent)
                        : onSelectIpo(ev as IpoCalendarEvent)
                    }
                    className={`truncate rounded px-1 py-0.5 mb-0.5 cursor-pointer text-[10px] font-medium flex items-center gap-0.5 ${
                      ev.event_type === "dividend"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-orange-100 text-orange-800"
                    }`}
                  >
                    {ev.is_in_watchlist && <span>★</span>}
                    {ev.symbol}
                  </div>
                ))}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function IpoPanel({
  event,
  onClose,
}: {
  event: IpoCalendarEvent;
  onClose: () => void;
}) {
  const [analysis, setAnalysis] = useState<IpoAnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const runAnalysis = async (force = false) => {
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeIpo(event.id, force);
      setAnalysis(result);
    } catch (err: unknown) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="px-1.5 py-0.5 rounded text-xs bg-orange-100 text-orange-800 font-medium">IPO</span>
            {event.symbol}
            {event.company_name && <span className="text-sm font-normal text-muted-foreground">— {event.company_name}</span>}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">IPO Date</span>
            <span>{event.event_date}</span>
          </div>
          {event.sector && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Sector</span>
              <span>{event.sector}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">Price Range</span>
            <span>
              {event.price_low && event.price_high
                ? `${event.price_low} – ${event.price_high} USD`
                : "N/A"}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Status</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[event.status] || ""}`}>
              {event.status}
            </span>
          </div>
          {event.is_in_watchlist && (
            <div className="text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded px-2 py-1">
              ★ In your watchlist
            </div>
          )}
        </div>

        <div className="border-t pt-3 space-y-3">
          {!analysis && !analyzing && (
            <Button onClick={() => runAnalysis(false)} className="w-full" disabled={analyzing}>
              Analyze with AI
            </Button>
          )}
          {analyzing && (
            <div className="text-center text-sm text-muted-foreground">Analyzing…</div>
          )}
          {analyzeError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {analyzeError.includes("Settings") ? (
                <>LLM not configured. <a href="/settings" className="underline">Set up in Settings →</a></>
              ) : analyzeError}
            </div>
          )}
          {analysis && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${VERDICT_STYLE[analysis.verdict] || ""}`}>
                  {analysis.verdict}
                </span>
                {analysis.suggested_price && (
                  <span className="text-sm font-medium">Target: ${analysis.suggested_price}</span>
                )}
                {analysis.cached && <span className="text-xs text-muted-foreground">cached</span>}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{analysis.reasoning}</p>
              <Button variant="ghost" size="sm" onClick={() => runAnalysis(true)} disabled={analyzing}>
                Re-analyze
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function EventsPage() {
  const { formatNative } = useDualCurrency();
  const [allEvents, setAllEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedDividend, setSelectedDividend] = useState<DividendCalendarEvent | null>(null);
  const [selectedIpo, setSelectedIpo] = useState<IpoCalendarEvent | null>(null);
  const [confirmQty, setConfirmQty] = useState("");
  const [confirmDate, setConfirmDate] = useState("");
  const [confirming, setConfirming] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await fetchEventsCalendar(3);
      setAllEvents(data.months.flatMap((m) => m.events));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await api.post("/api/v1/dividends/refresh", {});
    setRefreshing(false);
    setTimeout(fetchData, 2000);
  };

  const openDividend = (ev: DividendCalendarEvent) => {
    if (ev.status !== "payable") return;
    setSelectedDividend(ev);
    setConfirmQty(parseFloat(ev.quantity_held).toString());
    setConfirmDate(ev.pay_date ?? new Date().toISOString().slice(0, 10));
  };

  const submitConfirm = async () => {
    if (!selectedDividend) return;
    setConfirming(true);
    const res = await api.post(`/api/v1/dividends/${selectedDividend.id}/confirm`, {
      quantity: parseFloat(confirmQty),
      executed_at: confirmDate,
    });
    setConfirming(false);
    if (res.ok) { setSelectedDividend(null); fetchData(); }
  };

  const filtered = filterEvents(allEvents, filter);

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: "all", label: "All" },
    { key: "dividend", label: "Dividends" },
    { key: "ipo", label: "IPOs" },
    { key: "watchlist", label: "Watchlist only" },
  ];

  return (
    <div className="space-y-4 p-4 md:p-6">
      <PageHeader title="Events" />
      <div className="flex items-center justify-end">
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-1 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1 rounded-full text-sm font-medium border transition-colors ${
              filter === key
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background border-border text-muted-foreground hover:border-primary"
            }`}
          >
            {label}
          </button>
        ))}
        <div className="flex items-center gap-3 ml-auto text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-200 inline-block" /> Dividend</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-200 inline-block" /> IPO</span>
          <span>★ Watchlist</span>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Loading…</div>
      ) : (
        <CalendarGrid
          events={filtered}
          onSelectDividend={openDividend}
          onSelectIpo={setSelectedIpo}
        />
      )}

      <div>
        <h2 className="text-lg font-semibold mb-2">Upcoming Events</h2>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Symbol</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Details</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered
              .filter((e) => e.status !== "paid" && e.status !== "listed")
              .sort((a, b) => a.event_date.localeCompare(b.event_date))
              .map((ev) => (
                <TableRow key={ev.id}>
                  <TableCell className="font-medium">
                    {ev.is_in_watchlist && <span className="text-yellow-500 mr-1">★</span>}
                    {ev.symbol}
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      ev.event_type === "dividend" ? "bg-blue-100 text-blue-800" : "bg-orange-100 text-orange-800"
                    }`}>
                      {ev.event_type === "dividend" ? "Dividend" : "IPO"}
                    </span>
                  </TableCell>
                  <TableCell>{ev.event_date}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {ev.event_type === "dividend" ? (
                      <span className="flex items-center gap-1">
                        <DualCurrencyAmount
                          value={formatNative(
                            (ev as DividendCalendarEvent).amount_per_share,
                            (ev as DividendCalendarEvent).currency
                          )}
                        />
                        <span className="text-muted-foreground">/sh</span>
                      </span>
                    ) : (ev as IpoCalendarEvent).price_low
                      ? `${(ev as IpoCalendarEvent).price_low}–${(ev as IpoCalendarEvent).price_high} USD`
                      : "N/A"}
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[ev.status] || ""}`}>
                      {ev.status}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      {selectedIpo && (
        <IpoPanel event={selectedIpo} onClose={() => setSelectedIpo(null)} />
      )}

      <Dialog open={!!selectedDividend} onOpenChange={(open) => !open && setSelectedDividend(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Dividend — {selectedDividend?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount per share</span>
              <span className="font-medium">
                {selectedDividend ? (
                  <DualCurrencyAmount
                    value={formatNative(selectedDividend.amount_per_share, selectedDividend.currency)}
                  />
                ) : "—"}
              </span>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Quantity received</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={confirmQty} onChange={(e) => setConfirmQty(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Date received</label>
              <input type="date" className="w-full border rounded px-3 py-2 text-sm" value={confirmDate} onChange={(e) => setConfirmDate(e.target.value)} />
            </div>
            {confirmQty && selectedDividend && (
              <div className="flex justify-between font-semibold border-t pt-2">
                <span>Total income</span>
                <DualCurrencyAmount
                  value={formatNative(
                    parseFloat(confirmQty) * parseFloat(selectedDividend.amount_per_share),
                    selectedDividend.currency
                  )}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedDividend(null)}>Cancel</Button>
            <Button onClick={submitConfirm} disabled={confirming || !confirmQty || !confirmDate}>
              {confirming ? "Saving…" : "Confirm & Record"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
