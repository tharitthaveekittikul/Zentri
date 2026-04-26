"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PlatformsManager } from "@/components/settings/PlatformsManager";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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

  useEffect(() => {
    api
      .get("/api/v1/settings/hardware")
      .then((r) => r.json())
      .then(setHardware)
      .catch(() => null);
  }, []);

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold">Settings</h1>

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
    </div>
  );
}
