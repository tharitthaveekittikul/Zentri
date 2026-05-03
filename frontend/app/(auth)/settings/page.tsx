"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PlatformsManager } from "@/components/settings/PlatformsManager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AISettings } from "@/components/settings/AISettings";

interface HardwareRecommendation {
  can_run_local_llm: boolean;
  recommended_model: string;
  setup_command: string;
  note: string;
}

interface HardwareInfo {
  cpu_brand: string;
  ram_gb: number;
  is_apple_silicon: boolean;
  recommendation: HardwareRecommendation;
}

export default function SettingsPage() {
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const CURRENCIES = ["THB", "USD", "EUR", "GBP", "JPY", "SGD"];
  const [currencyPrimary, setCurrencyPrimary] = useState("THB");
  const [currencySecondary, setCurrencySecondary] = useState("USD");

  useEffect(() => {
    api
      .get("/api/v1/settings/hardware")
      .then((r) => r.json())
      .then(setHardware)
      .catch(() => null);
  }, []);

  useEffect(() => {
    api
      .get("/api/v1/settings/display")
      .then((r) => r.json())
      .then((d) => {
        setCurrencyPrimary(d.currency_primary);
        setCurrencySecondary(d.currency_secondary);
      })
      .catch(() => null);
  }, []);

  async function saveCurrencyPrefs() {
    await api.patch("/api/v1/settings/display", {
      currency_primary: currencyPrimary,
      currency_secondary: currencySecondary,
    });
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="ai">AI & LLM</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Hardware</CardTitle>
            </CardHeader>
            <CardContent>
              {hardware ? (
                <div className="space-y-2 text-sm">
                  <p>
                    <strong>CPU:</strong> {hardware.cpu_brand}
                  </p>
                  <p>
                    <strong>RAM:</strong> {hardware.ram_gb} GB
                  </p>
                  <p>
                    <strong>Apple Silicon:</strong>{" "}
                    {hardware.is_apple_silicon ? "Yes" : "No"}
                  </p>
                  <div className="border rounded p-3 mt-2 space-y-1">
                    <p>
                      <strong>Recommended model:</strong>{" "}
                      {hardware.recommendation.recommended_model}
                    </p>
                    <p className="text-muted-foreground">
                      {hardware.recommendation.note}
                    </p>
                    {hardware.recommendation.can_run_local_llm && (
                      <code className="block bg-muted p-2 rounded text-xs mt-1">
                        {hardware.recommendation.setup_command}
                      </code>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Loading hardware info...
                </p>
              )}
            </CardContent>
          </Card>

          <PlatformsManager />

          <Card>
            <CardHeader>
              <CardTitle>Display</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-4 items-end">
                <div className="flex-1">
                  <label className="text-sm font-medium mb-1 block">Primary Currency</label>
                  <select
                    className="w-full border rounded px-3 py-2 text-sm bg-background"
                    value={currencyPrimary}
                    onChange={(e) => setCurrencyPrimary(e.target.value)}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div className="flex-1">
                  <label className="text-sm font-medium mb-1 block">Secondary Currency</label>
                  <select
                    className="w-full border rounded px-3 py-2 text-sm bg-background"
                    value={currencySecondary}
                    onChange={(e) => setCurrencySecondary(e.target.value)}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={saveCurrencyPrefs}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm"
                >
                  Save
                </button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="mt-4">
          <AISettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
