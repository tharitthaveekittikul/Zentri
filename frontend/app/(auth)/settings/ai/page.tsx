"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/layout/PageHeader";

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

interface CallLogsData {
  total_cost_usd: number;
  total_cost_thb: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_calls: number;
  logs: CallLog[];
}

async function fetchCallLogs(featureKey?: string): Promise<CallLogsData> {
  const params = featureKey ? `?feature_key=${featureKey}` : "";
  const res = await api.get(`/api/v1/llm/call-logs${params}`);
  if (!res.ok) throw new Error("Failed to fetch call logs");
  return res.json();
}

export default function AIUsagePage() {
  const [activeTab, setActiveTab] = useState("all");
  const [data, setData] = useState<CallLogsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const featureKey =
      activeTab === "import"
        ? "import_template_generator"
        : activeTab === "analysis"
          ? "portfolio_analysis"
          : undefined;
    setLoading(true);
    fetchCallLogs(featureKey)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [activeTab]);

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader title="AI & LLM" />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Spend</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              ฿{data?.total_cost_thb.toFixed(2) ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              ${data?.total_cost_usd.toFixed(4) ?? "—"} USD
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Calls</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.total_calls ?? "—"}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tokens In</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {data?.total_tokens_in.toLocaleString() ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tokens Out</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {data?.total_tokens_out.toLocaleString() ?? "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="all">All Calls</TabsTrigger>
          <TabsTrigger value="import">Import Mapping</TabsTrigger>
          <TabsTrigger value="analysis">Analysis</TabsTrigger>
        </TabsList>
        <TabsContent value={activeTab}>
          {loading ? (
            <p className="text-muted-foreground py-8 text-center">Loading...</p>
          ) : !data?.logs.length ? (
            <p className="text-muted-foreground py-8 text-center">No calls yet.</p>
          ) : (
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
                {data.logs.map((log) => (
                  <tr key={log.id} className="border-b hover:bg-muted/50">
                    <td className="py-2">
                      {new Date(log.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2">{log.feature_key.replace(/_/g, " ")}</td>
                    <td className="py-2">
                      {log.provider} / {log.model}
                    </td>
                    <td className="py-2 text-right">
                      {log.tokens_in.toLocaleString()}
                    </td>
                    <td className="py-2 text-right">
                      {log.tokens_out.toLocaleString()}
                    </td>
                    <td className="py-2 text-right">฿{log.cost_thb.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
