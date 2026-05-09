"use client";

import { Suspense, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { useDualCurrency } from "@/hooks/useDualCurrency";
import { DualCurrencyAmount } from "@/components/ui/DualCurrencyAmount";

interface Summary {
  total_cost_usd: number;
  monthly_cost_usd: number;
  total_analyses: number;
  by_provider: { provider: string; cost_usd: number }[];
}

interface CallLog {
  id: string;
  feature_key: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  cost_thb: number;
  created_at: string;
}

interface CallLogDetail extends CallLog {
  prompt_in: string;
  response_out: string;
}

function AIUsageContent() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);

  const [callLogs, setCallLogs] = useState<CallLog[]>([]);
  const [callLogDetail, setCallLogDetail] = useState<CallLogDetail | null>(null);
  const [payloadOpen, setPayloadOpen] = useState(false);
  const [loadingPayload, setLoadingPayload] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedResponse, setCopiedResponse] = useState(false);

  function copyToClipboard(text: string, type: "prompt" | "response") {
    navigator.clipboard.writeText(text).then(() => {
      if (type === "prompt") {
        setCopiedPrompt(true);
        setTimeout(() => setCopiedPrompt(false), 2000);
      } else {
        setCopiedResponse(true);
        setTimeout(() => setCopiedResponse(false), 2000);
      }
    });
  }

  async function load() {
    setLoading(true);
    try {
      const summaryRes = await api.get("/api/v1/analysis/usage/summary");
      if (summaryRes.ok) setSummary(await summaryRes.json());
    } finally {
      setLoading(false);
    }
  }

  async function loadCallLogs() {
    const r = await api.get("/api/v1/llm/call-logs?limit=100");
    if (r.ok) {
      const data = await r.json();
      setCallLogs(data.logs ?? []);
    }
  }

  useEffect(() => {
    load();
    loadCallLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function viewPayload(logId: string) {
    setPayloadOpen(true);
    setLoadingPayload(true);
    setCallLogDetail(null);
    const r = await api.get(`/api/v1/llm/call-logs/${logId}`);
    if (r.ok) setCallLogDetail(await r.json());
    else toast.error("Failed to load payload");
    setLoadingPayload(false);
  }

  const { formatNative } = useDualCurrency();

  return (
    <div className="space-y-6">
      <PageHeader title="AI Usage" />

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-1">
                <Skeleton className="h-4 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">Total Spend</CardTitle>
              </CardHeader>
              <CardContent>
                <DualCurrencyAmount
                  value={formatNative(summary.total_cost_usd, "USD", 4)}
                  primaryClassName="text-2xl font-bold"
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">This Month</CardTitle>
              </CardHeader>
              <CardContent>
                <DualCurrencyAmount
                  value={formatNative(summary.monthly_cost_usd, "USD", 4)}
                  primaryClassName="text-2xl font-bold"
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">Total Analyses</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{summary.total_analyses}</p>
              </CardContent>
            </Card>
          </div>

          {summary.by_provider.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Cost by Provider</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={summary.by_provider}>
                    <XAxis dataKey="provider" />
                    <YAxis tickFormatter={(v) => formatNative(v, "USD", 6).primary} />
                    <Tooltip
                      formatter={(v) => [formatNative(Number(v), "USD", 6).primary, "Cost"]}
                    />
                    <Bar dataKey="cost_usd" fill="#6366f1" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      <div className="bg-card card-surface rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold">LLM Call Logs</h2>
          <Button variant="outline" size="sm" onClick={loadCallLogs}>
            Refresh
          </Button>
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Feature</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Tokens In</TableHead>
                <TableHead>Tokens Out</TableHead>
                <TableHead>Cost</TableHead>
                <TableHead>Date</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {callLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-sm">{log.feature_key}</TableCell>
                  <TableCell className="text-sm">{log.provider}</TableCell>
                  <TableCell className="text-sm">{log.model}</TableCell>
                  <TableCell>{log.tokens_in.toLocaleString()}</TableCell>
                  <TableCell>{log.tokens_out.toLocaleString()}</TableCell>
                  <TableCell>
                    <DualCurrencyAmount value={formatNative(log.cost_usd, "USD", 6)} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(log.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <button
                      className="text-xs text-muted-foreground underline"
                      onClick={() => viewPayload(log.id)}
                    >
                      View log
                    </button>
                  </TableCell>
                </TableRow>
              ))}
              {callLogs.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground py-8"
                  >
                    No LLM calls yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <Dialog open={payloadOpen} onOpenChange={setPayloadOpen}>
        <DialogContent className="max-w-5xl w-[90vw] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>LLM Payload</DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto pr-1">
            {loadingPayload && (
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
            {callLogDetail && (
              <div className="space-y-4 text-sm">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-semibold">Input Prompt</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => copyToClipboard(callLogDetail.prompt_in, "prompt")}
                    >
                      {copiedPrompt ? "✓ Copied" : "Copy"}
                    </Button>
                  </div>
                  <pre className="bg-muted rounded p-3 whitespace-pre-wrap text-xs overflow-x-auto max-h-[35vh]">
                    {callLogDetail.prompt_in}
                  </pre>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-semibold">Output Response</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs px-2"
                      onClick={() => copyToClipboard(callLogDetail.response_out, "response")}
                    >
                      {copiedResponse ? "✓ Copied" : "Copy"}
                    </Button>
                  </div>
                  <pre className="bg-muted rounded p-3 whitespace-pre-wrap text-xs overflow-x-auto max-h-[35vh]">
                    {callLogDetail.response_out}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function AIUsagePage() {
  return (
    <Suspense fallback={null}>
      <AIUsageContent />
    </Suspense>
  );
}
