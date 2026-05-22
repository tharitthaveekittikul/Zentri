"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { DatePicker } from "@/components/ui/date-picker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { TickerLogo } from "@/components/ui/TickerLogo";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";
import { ConfirmLLMDialog } from "@/components/llm/ConfirmLLMDialog";

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

type FilterType = "all" | "dividend" | "ipo" | "watchlist";

const VERDICT_STYLE: Record<string, string> = {
  BUY: "[background:var(--signal-gain-bg)] [color:var(--signal-gain-text)]",
  WATCH: "bg-muted text-muted-foreground",
  SKIP: "bg-destructive/10 text-destructive",
};

const STATUS_BADGE: Record<string, string> = {
  upcoming: "bg-muted text-muted-foreground",
  payable: "bg-muted text-muted-foreground",
  paid: "[background:var(--signal-gain-bg)] [color:var(--signal-gain-text)]",
  priced: "bg-muted text-muted-foreground",
  listed: "bg-muted text-muted-foreground",
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

  const byDay = useMemo(() => {
    const map: Record<number, CalendarEvent[]> = {};
    for (const ev of events) {
      const d = new Date(ev.event_date);
      if (d.getFullYear() === viewYear && d.getMonth() === viewMonth) {
        const day = d.getDate();
        if (!map[day]) map[day] = [];
        map[day].push(ev);
      }
    }
    return map;
  }, [events, viewYear, viewMonth]);

  const cells = useMemo(() => {
    const arr: (number | null)[] = Array(firstDay).fill(null);
    for (let d = 1; d <= daysInMonth; d++) arr.push(d);
    return arr;
  }, [firstDay, daysInMonth]);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[476px]">
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
                day === today.getDate() && isCurrentMonth ? "bg-brand-accent/10 ring-1 ring-inset ring-brand-accent/30" : ""
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
                          ? "[background:var(--signal-gain-bg)] [color:var(--signal-gain-text)]"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {ev.is_in_watchlist && <span>★</span>}
                      <TickerLogo symbol={ev.symbol} logoUrl={ev.metadata_?.logo_url as string | undefined} size={16} />
                      {ev.symbol}
                    </div>
                  ))}
                </>
              )}
            </div>
          ))}
        </div>
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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingForce, setPendingForce] = useState(false);

  const requestAnalysis = (force = false) => {
    setPendingForce(force);
    setConfirmOpen(true);
  };

  const runAnalysis = async () => {
    setConfirmOpen(false);
    setAnalyzing(true);
    setAnalyzeError(null);
    try {
      const result = await analyzeIpo(event.id, pendingForce);
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
            <div className="text-xs text-muted-foreground bg-muted border border-border rounded px-2 py-1">
              ★ In your watchlist
            </div>
          )}
        </div>

        <div className="border-t pt-3 space-y-3">
          {!analysis && !analyzing && (
            <Button onClick={() => requestAnalysis(false)} className="w-full" disabled={analyzing}>
              Analyze with AI
            </Button>
          )}
          {analyzing && (
            <div className="text-center text-sm text-muted-foreground">Analyzing…</div>
          )}
          {analyzeError && (
            <div className="text-sm text-destructive bg-destructive/5 border border-destructive/20 rounded px-3 py-2">
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
                  <span className="text-sm font-medium">Target: {parseFloat(analysis.suggested_price).toFixed(2)} USD</span>
                )}
                {analysis.cached && <span className="text-xs text-muted-foreground">cached</span>}
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">{analysis.reasoning}</p>
              <Button variant="ghost" size="sm" onClick={() => requestAnalysis(true)} disabled={analyzing}>
                Re-analyze
              </Button>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>

      <ConfirmLLMDialog
        open={confirmOpen}
        title="Analyze IPO"
        description={`Run AI analysis on ${event.symbol} IPO. Uses your configured LLM.`}
        estimatedCost="< $0.01 est."
        loading={analyzing}
        onConfirm={runAnalysis}
        onCancel={() => setConfirmOpen(false)}
      />
    </Dialog>
  );
}

export default function EventsPage() {
  const { formatNative } = useDualCurrency();
  const [allEvents, setAllEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedDividend, setSelectedDividend] = useState<DividendCalendarEvent | null>(null);
  const [selectedIpo, setSelectedIpo] = useState<IpoCalendarEvent | null>(null);
  const [confirmQty, setConfirmQty] = useState("");
  const [confirmDate, setConfirmDate] = useState("");
  const [confirming, setConfirming] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await fetchEventsCalendar(3);
      setAllEvents(data.months.flatMap((m) => m.events));
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : "Failed to load events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([
      api.post("/api/v1/dividends/refresh", {}),
      api.post("/api/v1/ipos/refresh", {}),
    ]);
    // Job is async (~20s). Poll every 5s until data arrives or 60s timeout.
    let attempts = 0;
    const poll = async () => {
      attempts++;
      try {
        const data = await fetchEventsCalendar(3);
        const events = data.months.flatMap((m) => m.events);
        setAllEvents(events);
        if (events.length > 0 || attempts >= 12) {
          setRefreshing(false);
        } else {
          setTimeout(poll, 5000);
        }
      } catch {
        setRefreshing(false);
      }
    };
    setTimeout(poll, 5000);
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

  const filtered = useMemo(() => filterEvents(allEvents, filter), [allEvents, filter]);

  const FILTERS: { key: FilterType; label: string }[] = [
    { key: "all", label: "All Events" },
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
          <Button
            key={key}
            variant="outline"
            onClick={() => setFilter(key)}
            className={`px-3 py-1 rounded-full text-sm font-medium h-auto border transition-colors ${
              filter === key
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background border-border text-muted-foreground hover:border-primary"
            }`}
          >
            {label}
          </Button>
        ))}
        <div className="flex items-center gap-3 ml-auto text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded [background:var(--signal-gain-bg)] inline-block" /> Dividend</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-muted inline-block" /> IPO</span>
          <span>★ Watchlist</span>
        </div>
      </div>

      {fetchError && (
        <div className="rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {fetchError}
        </div>
      )}

      {loading ? (
        <div className="bg-card card-surface rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b">
            <Skeleton className="h-8 w-8 rounded-full" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
          <div className="overflow-x-auto">
            <div className="min-w-[476px]">
              <div className="grid grid-cols-7 text-xs border-b">
                {Array.from({ length: 7 }).map((_, i) => (
                  <div key={i} className="py-1 flex justify-center">
                    <Skeleton className="h-3 w-6" />
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7">
                {Array.from({ length: 35 }).map((_, i) => (
                  <div key={i} className="min-h-[72px] border-b border-r p-1">
                    <Skeleton className="h-3 w-4 mb-1" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-card card-surface rounded-2xl overflow-hidden">
          <CalendarGrid
            events={filtered}
            onSelectDividend={openDividend}
            onSelectIpo={setSelectedIpo}
          />
        </div>
      )}

      <div className="bg-card card-surface rounded-2xl overflow-hidden">
        <div className="p-5">
          <h2 className="text-lg font-semibold mb-2">Upcoming Events</h2>
        </div>
        <div className="overflow-x-auto">
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
            {filtered.filter((e) => e.status !== "paid" && e.status !== "listed").length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No upcoming events. Try clicking Refresh or check back later.
                </TableCell>
              </TableRow>
            )}
            {filtered
              .filter((e) => e.status !== "paid" && e.status !== "listed")
              .sort((a, b) => a.event_date.localeCompare(b.event_date))
              .map((ev) => (
                <TableRow key={ev.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {ev.is_in_watchlist && <span className="text-brand-accent">★</span>}
                      <TickerLogo symbol={ev.symbol} logoUrl={ev.metadata_?.logo_url as string | undefined} />
                      <span>{ev.symbol}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      ev.event_type === "dividend" ? "[background:var(--signal-gain-bg)] [color:var(--signal-gain-text)]" : "bg-muted text-muted-foreground"
                    }`}>
                      {ev.event_type === "dividend" ? "Dividend" : "IPO"}
                    </span>
                  </TableCell>
                  <TableCell>{ev.event_date}</TableCell>
                  <TableCell>
                    {ev.event_type === "dividend" ? (() => {
                      const d = ev as DividendCalendarEvent;
                      const qty = parseFloat(d.quantity_held);
                      return qty > 0 ? (
                        <span className="flex flex-col gap-0.5">
                          <DualCurrencyAmount
                            value={formatNative(d.projected_total_usd, "USD")}
                          />
                          <span className="text-xs text-muted-foreground">
                            {qty} shares × {parseFloat(d.amount_per_share).toFixed(2)} {d.currency}
                          </span>
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-muted-foreground">
                          <DualCurrencyAmount
                            value={formatNative(d.amount_per_share, d.currency)}
                          />
                          <span className="text-muted-foreground">/ share</span>
                        </span>
                      );
                    })() : (ev as IpoCalendarEvent).price_low
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
              <Input className="w-full" value={confirmQty} onChange={(e) => setConfirmQty(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Date received</label>
              <DatePicker value={confirmDate} onChange={setConfirmDate} className="w-full" />
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
