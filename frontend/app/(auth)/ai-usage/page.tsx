"use client";

import React, { useEffect, useState } from "react";
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
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";

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

export default function AIUsagePage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [logs, setLogs] = useState<Analysis[]>([]);
  const [filterProvider, setFilterProvider] = useState("all");
  const [conversations, setConversations] = useState<
    Record<string, { role: string; content: string }[]>
  >({});
  const [openRows, setOpenRows] = useState<Set<string>>(new Set());

  async function load() {
    const summaryRes = await api.get("/api/v1/analysis/usage/summary");
    const logsUrl =
      filterProvider === "all"
        ? "/api/v1/analysis/usage/logs"
        : `/api/v1/analysis/usage/logs?provider=${filterProvider}`;
    const logsRes = await api.get(logsUrl);
    if (summaryRes.ok) setSummary(await summaryRes.json());
    if (logsRes.ok) setLogs(await logsRes.json());
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterProvider]);

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

  const providers = summary
    ? ["all", ...summary.by_provider.map((p) => p.provider)]
    : ["all"];

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-xl font-semibold">AI Usage</h1>

      {summary && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">Total Spend</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  ${summary.total_cost_usd.toFixed(4)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm">This Month</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">
                  ${summary.monthly_cost_usd.toFixed(4)}
                </p>
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
                    <YAxis tickFormatter={(v) => `$${v}`} />
                    <Tooltip
                      formatter={(v) => [`$${Number(v).toFixed(6)}`, "Cost"]}
                    />
                    <Bar dataKey="cost_usd" fill="#6366f1" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </>
      )}

      <div className="flex items-center gap-3">
        <Select
          value={filterProvider}
          onValueChange={(v) => setFilterProvider(v ?? "all")}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {providers.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

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
                <TableCell>${a.cost_usd.toFixed(6)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(a.created_at).toLocaleDateString()}
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
  );
}
