"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { setupAccount, type HardwareRecommendation } from "@/lib/services/auth";

type Step = "account" | "hardware" | "llm";

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("account");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [hardware, setHardware] = useState<HardwareRecommendation | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await setupAccount(username, password);
      if (!result.ok) {
        toast.error(result.error);
        if (result.conflict) router.push("/login");
        return;
      }
      setHardware(result.hardware);
      setStep("hardware");
    } finally {
      setLoading(false);
    }
  }

  if (step === "account") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome to Zentri</CardTitle>
            <p className="text-sm text-muted-foreground">
              Step 1 of 3 — Create your account
            </p>
            <Progress value={33} className="mt-2" />
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div className="space-y-1">
                <Label>Username</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
              </div>
              <div className="space-y-1">
                <Label>Password</Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating..." : "Create Account"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (step === "hardware") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Hardware Detected</CardTitle>
            <p className="text-sm text-muted-foreground">Step 2 of 3</p>
            <Progress value={66} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            {hardware ? (
              <>
                <div className="rounded-lg border p-3 text-sm space-y-1">
                  <p><strong>Recommended model:</strong> {hardware.recommended_model}</p>
                  <p className="text-muted-foreground">{hardware.note}</p>
                  {hardware.can_run_local_llm && (
                    <code className="block bg-muted p-2 rounded text-xs mt-2">
                      {hardware.setup_command}
                    </code>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  You can always change this in Settings later.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                Hardware detection unavailable. You can configure LLM in Settings.
              </p>
            )}
            <Button onClick={() => setStep("llm")} className="w-full">
              Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Setup Complete</CardTitle>
          <p className="text-sm text-muted-foreground">Step 3 of 3</p>
          <Progress value={100} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            You can configure LLM providers and API keys in{" "}
            <strong>Settings → LLM Configuration</strong> after you log in.
          </p>
          <Button onClick={() => router.push("/")} className="w-full">
            Go to Dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
