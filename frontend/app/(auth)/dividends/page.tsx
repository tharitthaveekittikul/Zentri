"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
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
import { RefreshCw, CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";

type DividendEvent = {
  id: string;
  symbol: string;
  asset_id: string;
  ex_date: string;
  pay_date: string | null;
  record_date: string | null;
  amount_per_share: string;
  currency: string;
  frequency: string | null;
  status: "upcoming" | "payable" | "paid";
  quantity_held: string;
  projected_total_usd: string;
  projected_total_secondary: string | null;
};

type MonthGroup = {
  year: number;
  month: number;
  total_projected_usd: string;
  events: DividendEvent[];
};

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const STATUS_BADGE: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-800",
  payable: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
};

function CalendarGrid({
  events,
  onConfirm,
}: {
  events: DividendEvent[];
  onConfirm: (e: DividendEvent) => void;
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

  const byDay: Record<number, DividendEvent[]> = {};
  for (const ev of events) {
    const d = new Date(ev.ex_date);
    if (d.getFullYear() === viewYear && d.getMonth() === viewMonth) {
      const day = d.getDate();
      if (!byDay[day]) byDay[day] = [];
      byDay[day].push(ev);
    }
  }

  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">{MONTH_NAMES[viewMonth]} {viewYear}</h2>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={prev} className="h-7 w-7 p-0">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {!isCurrentMonth && (
            <Button variant="ghost" size="sm" onClick={() => { setViewYear(today.getFullYear()); setViewMonth(today.getMonth()); }} className="h-7 px-2 text-xs">
              Today
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={next} className="h-7 w-7 p-0">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-xs text-center text-muted-foreground mb-1">
        {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((d) => (
          <div key={d} className="py-1 font-medium">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => (
          <div
            key={i}
            className={`min-h-[56px] rounded p-1 text-xs ${day ? "bg-card border" : ""} ${isCurrentMonth && day === today.getDate() ? "border-primary" : ""}`}
          >
            {day && (
              <>
                <div className="font-medium text-muted-foreground mb-1">{day}</div>
                {(byDay[day] ?? []).map((ev) => (
                  <div
                    key={ev.id}
                    className={`rounded px-1 py-0.5 mb-0.5 cursor-pointer truncate ${STATUS_BADGE[ev.status]}`}
                    title={`${ev.symbol} – $${parseFloat(ev.amount_per_share).toFixed(4)}/share`}
                    onClick={() => ev.status === "payable" && onConfirm(ev)}
                  >
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

export default function DividendsPage() {
  const [calendar, setCalendar] = useState<{ months: MonthGroup[] }>({ months: [] });
  const [upcoming, setUpcoming] = useState<DividendEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<DividendEvent | null>(null);
  const [confirmQty, setConfirmQty] = useState("");
  const [confirmDate, setConfirmDate] = useState("");
  const [confirming, setConfirming] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    const [calRes, upRes] = await Promise.all([
      api.get("/api/v1/dividends/calendar?months=3"),
      api.get("/api/v1/dividends/upcoming"),
    ]);
    if (calRes.ok) setCalendar(await calRes.json());
    if (upRes.ok) setUpcoming(await upRes.json());
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    await api.post("/api/v1/dividends/refresh", {});
    setRefreshing(false);
    setTimeout(fetchData, 2000);
  };

  const openConfirm = (ev: DividendEvent) => {
    setConfirmTarget(ev);
    setConfirmQty(parseFloat(ev.quantity_held).toString());
    setConfirmDate(ev.pay_date ?? new Date().toISOString().slice(0, 10));
  };

  const submitConfirm = async () => {
    if (!confirmTarget) return;
    setConfirming(true);
    const res = await api.post(`/api/v1/dividends/${confirmTarget.id}/confirm`, {
      quantity: parseFloat(confirmQty),
      executed_at: confirmDate,
    });
    setConfirming(false);
    if (res.ok) {
      setConfirmTarget(null);
      fetchData();
    }
  };

  const allEvents = calendar.months.flatMap((m) => m.events);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dividend Calendar</h1>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <>
          <CalendarGrid events={allEvents} onConfirm={openConfirm} />

          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Upcoming Dividends</h2>
            {upcoming.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                No upcoming dividends. Click Refresh to fetch data.
              </p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead>Ex-Date</TableHead>
                      <TableHead>Pay-Date</TableHead>
                      <TableHead className="text-right">Per Share</TableHead>
                      <TableHead className="text-right">Projected (USD)</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {upcoming.map((ev) => (
                      <TableRow key={ev.id}>
                        <TableCell className="font-medium">{ev.symbol}</TableCell>
                        <TableCell>{ev.ex_date}</TableCell>
                        <TableCell>{ev.pay_date ?? "—"}</TableCell>
                        <TableCell className="text-right">
                          {parseFloat(ev.amount_per_share).toFixed(4)} {ev.currency}
                        </TableCell>
                        <TableCell className="text-right">
                          <div>${parseFloat(ev.projected_total_usd).toFixed(2)}</div>
                          {ev.projected_total_secondary && (
                            <div className="text-muted-foreground text-xs">
                              ≈ {parseFloat(ev.projected_total_secondary).toFixed(0)}
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[ev.status]}`}>
                            {ev.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          {ev.status === "payable" && (
                            <Button size="sm" variant="outline" onClick={() => openConfirm(ev)}>
                              <CheckCircle2 className="h-4 w-4 mr-1" />
                              Mark Received
                            </Button>
                          )}
                          {ev.status === "paid" && (
                            <span className="text-xs text-green-600 font-medium">✓ Confirmed</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Mark as Received Dialog */}
      <Dialog open={!!confirmTarget} onOpenChange={(open) => !open && setConfirmTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Dividend — {confirmTarget?.symbol}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount per share</span>
              <span className="font-medium">
                {confirmTarget ? parseFloat(confirmTarget.amount_per_share).toFixed(4) : "—"}{" "}
                {confirmTarget?.currency}
              </span>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Quantity received</label>
              <input
                className="w-full border rounded px-3 py-2 text-sm"
                value={confirmQty}
                onChange={(e) => setConfirmQty(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Date received</label>
              <input
                type="date"
                className="w-full border rounded px-3 py-2 text-sm"
                value={confirmDate}
                onChange={(e) => setConfirmDate(e.target.value)}
              />
            </div>
            {confirmQty && confirmTarget && (
              <div className="flex justify-between font-semibold border-t pt-2">
                <span>Total income</span>
                <span>
                  ${(parseFloat(confirmQty) * parseFloat(confirmTarget.amount_per_share)).toFixed(2)}{" "}
                  {confirmTarget.currency}
                </span>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmTarget(null)}>Cancel</Button>
            <Button
              onClick={submitConfirm}
              disabled={confirming || !confirmQty || !confirmDate}
            >
              {confirming ? "Saving…" : "Confirm & Record"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
