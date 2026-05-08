"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { setupAccount, saveProfile, type HardwareRecommendation } from "@/lib/services/auth";
import { importSystem } from "@/lib/services/system";
import { DatePicker } from "@/components/ui/date-picker";

type Step = "account" | "restore" | "profile" | "hardware" | "llm";

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("account");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [hardware, setHardware] = useState<HardwareRecommendation | null>(null);
  const [birthDate, setBirthDate] = useState("");
  const [planToAge, setPlanToAge] = useState("85");
  const [loading, setLoading] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);

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
      setStep("restore");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveProfile() {
    setLoading(true);
    try {
      if (birthDate) {
        await saveProfile({
          birth_date: birthDate,
          plan_to_age: planToAge ? parseInt(planToAge) : null,
        });
      }
    } catch {
      // non-fatal — user can update in settings
    } finally {
      setLoading(false);
    }
    setStep("hardware");
  }

  if (step === "account") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome to Zentri</CardTitle>
            <p className="text-sm text-muted-foreground">Step 1 of 5 — Create your account</p>
            <Progress value={20} className="mt-2" />
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

  if (step === "restore") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Restore from backup?</CardTitle>
            <p className="text-sm text-muted-foreground">Step 2 of 5 — Optional</p>
            <Progress value={40} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              If you have a Zentri backup file, upload it now to restore all your
              data and skip the remaining setup steps.
            </p>
            {restoreError && (
              <p className="text-sm text-destructive">{restoreError}</p>
            )}
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="w-full">
                  <input
                    type="file"
                    accept=".json"
                    className="hidden"
                    disabled={loading}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setLoading(true);
                      setRestoreError(null);
                      try {
                        await importSystem(file);
                        router.push("/overview");
                      } catch (err) {
                        setRestoreError((err as Error).message || "Restore failed");
                      } finally {
                        setLoading(false);
                        e.target.value = "";
                      }
                    }}
                  />
                  <Button className="w-full" disabled={loading}>
                    {loading ? "Restoring..." : "Upload backup file"}
                  </Button>
                </label>
              </div>
              <Button
                variant="outline"
                className="flex-1"
                disabled={loading}
                onClick={() => { setRestoreError(null); setStep("profile"); }}
              >
                Start fresh
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (step === "profile") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Your Profile</CardTitle>
            <p className="text-sm text-muted-foreground">Step 3 of 5 — Optional</p>
            <Progress value={60} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              Used for age-aware analysis and net worth projections. You can add or change this in Settings later.
            </p>
            <div className="space-y-1">
              <Label>Date of Birth</Label>
              <DatePicker
                value={birthDate}
                onChange={setBirthDate}
                captionLayout="dropdown"
              />
            </div>
            <div className="space-y-1">
              <Label>Plan to Age</Label>
              <Input
                type="number"
                min={1}
                max={120}
                value={planToAge}
                onChange={(e) => setPlanToAge(e.target.value)}
                placeholder="85"
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setStep("hardware")}>
                Skip for now
              </Button>
              <Button className="flex-1" disabled={loading} onClick={handleSaveProfile}>
                {loading ? "Saving..." : "Continue"}
              </Button>
            </div>
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
            <p className="text-sm text-muted-foreground">Step 4 of 5</p>
            <Progress value={80} className="mt-2" />
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
          <p className="text-sm text-muted-foreground">Step 5 of 5</p>
          <Progress value={100} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            You can configure LLM providers and API keys in{" "}
            <strong>Settings → LLM Configuration</strong> after you log in.
          </p>
          <Button onClick={() => router.push("/overview")} className="w-full">
            Go to Dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
