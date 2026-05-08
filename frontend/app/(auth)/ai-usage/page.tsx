"use client";

import React, { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

interface Analysis {
  id: string;
  verdict: string;
  model: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  created_at: string;
  asset_id: string;
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
  const searchParams = useSearchParams();
  const router = useRouter();
  const tab = searchParams.get("tab") ?? "analyses";

  const [importLogs, setImportLogs] = useState<CallLog[]>([]);
  const [importLoading, setImportLoading] = useState(false);

  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [logs, setLogs] = useState<Analysis[]>([]);
  const [filterProvider, setFilterProvider] = useState("all");
  const [conversations, setConversations] = useState<
    Record<string, { role: string; content: string }[]>
  >({});
  const [openRows, setOpenRows] = useState<Set<string>>(new Set());

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
      const logsUrl =
        filterProvider === "all"
          ? "/api/v1/analysis/usage/logs"
          : `/api/v1/analysis/usage/logs?provider=${filterProvider}`;
      const logsRes = await api.get(logsUrl);
      if (summaryRes.ok) setSummary(await summaryRes.json());
      if (logsRes.ok) setLogs(await logsRes.json());
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
  }, [filterProvider]);

  useEffect(() => {
    if (tab !== "import-mapping" || importLogs.length > 0) return;
    setImportLoading(true);
    api
      .get("/api/v1/llm/call-logs?feature_key=import_mapping")
      .then((r) => (r.ok ? r.json() : { logs: [] }))
      .then((d) => setImportLogs(d.logs ?? []))
      .catch(() => setImportLogs([]))
      .finally(() => setImportLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function toggleConversation(id: string) {
    const next = new Set(openRows);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
      if (!conversations[id]) {
        const res = await api.get(`/api/v1/analysis/conversation/${id}`);
        if (res.ok) {
          const data = await res.json();
          setConversations((prev) => ({ ...prev, [id]: data }));
        }
      }
    }
    setOpenRows(new Set(next));
  }

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

  const providers = summary
    ? ["all", ...summary.by_provider.map((p) => p.provider)]
    : ["all"];

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

      <Tabs value={tab} onValueChange={(v) => router.replace(`/ai-usage?tab=${v}`)}>
        <TabsList>
          <TabsTrigger value="analyses">Analyses</TabsTrigger>
          <TabsTrigger value="call-logs">LLM Call Logs</TabsTrigger>
          <TabsTrigger value="import-mapping">Import Mapping</TabsTrigger>
        </TabsList>

        <TabsContent value="analyses" className="space-y-4 pt-2">
          <div className="flex items-center gap-3">
            <Select
              value={filterProvider}
              onValueChange={(v) => setFilterProvider(v ?? "all")}
            >
              <SelectTrigger className="w-40">
                <span className="truncate">{filterProvider === "all" ? "All Providers" : filterProvider}</span>
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p === "all" ? "All Providers" : p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {loading ? (
            <div className="space-y-3">
              <div className="flex gap-4 pb-2 border-b">
                {Array.from({ length: 7 }).map((_, i) => (
                  <Skeleton key={i} className="h-4 flex-1" />
                ))}
              </div>
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex gap-4">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <Skeleton key={j} className="h-4 flex-1" />
                  ))}
                </div>
              ))}
            </div>
          ) : (
          <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Verdict</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Tokens In</TableHead>
                <TableHead>Tokens Out</TableHead>
                <TableHead>Cost</TableHead>
                <TableHead>Date</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((a) => (
                <React.Fragment key={a.id}>
                  <TableRow>
                    <TableCell>
                      <span
                        className={
                          a.verdict === "BUY"
                            ? "text-green-500"
                            : a.verdict === "SELL"
                              ? "text-red-500"
                              : "text-yellow-500"
                        }
                      >
                        {a.verdict}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">{a.model}</TableCell>
                    <TableCell>{a.tokens_in.toLocaleString()}</TableCell>
                    <TableCell>{a.tokens_out.toLocaleString()}</TableCell>
                    <TableCell>
                      <DualCurrencyAmount value={formatNative(a.cost_usd, "USD", 6)} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(a.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <button
                        className="text-xs text-muted-foreground underline"
                        onClick={() => toggleConversation(a.id)}
                      >
                        {openRows.has(a.id) ? "Hide" : "View"} log
                      </button>
                    </TableCell>
                  </TableRow>
                  {openRows.has(a.id) && (
                    <TableRow key={`${a.id}-conv`}>
                      <TableCell colSpan={7}>
                        <div className="space-y-1 max-h-48 overflow-y-auto py-1">
                          {(conversations[a.id] ?? []).map((m, i) => (
                            <div key={i} className="text-xs bg-muted rounded p-2">
                              <span className="font-semibold capitalize">
                                {m.role}:{" "}
                              </span>
                              {m.content}
                            </div>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
              {logs.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="text-center text-muted-foreground py-8"
                  >
                    No analyses yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          </div>
          )}
        </TabsContent>

        <TabsContent value="call-logs" className="pt-2">
          <div className="flex justify-end mb-2">
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
                <TableHead>Cost (USD)</TableHead>
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
                      View payload
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
        </TabsContent>

        <TabsContent value="import-mapping" className="pt-2">
          {importLoading ? (
            <div className="space-y-3 mt-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex gap-4">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <div key={j} className="h-4 flex-1 bg-muted animate-pulse rounded" />
                  ))}
                </div>
              ))}
            </div>
          ) : importLogs.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center text-sm">
              No import mapping calls yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm mt-4">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Date</th>
                    <th className="text-left py-2">Feature</th>
                    <th className="text-left py-2">Provider / Model</th>
                    <th className="text-right py-2">Tokens In</th>
                    <th className="text-right py-2">Tokens Out</th>
                    <th className="text-right py-2">Cost (THB)</th>
                  </tr>
                </thead>
                <tbody>
                  {importLogs.map((log) => (
                    <tr key={log.id} className="border-b hover:bg-muted/50">
                      <td className="py-2">
                        {new Date(log.created_at).toLocaleDateString("en-GB")}
                      </td>
                      <td className="py-2">{log.feature_key.replace(/_/g, " ")}</td>
                      <td className="py-2">
                        {log.provider} / {log.model}
                      </td>
                      <td className="py-2 text-right">{log.tokens_in.toLocaleString()}</td>
                      <td className="py-2 text-right">{log.tokens_out.toLocaleString()}</td>
                      <td className="py-2 text-right">฿{log.cost_thb.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>

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
