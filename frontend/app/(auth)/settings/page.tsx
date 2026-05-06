"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AISettings } from "@/components/settings/AISettings";
import { getProfile, saveProfile, type ProfileSettings } from "@/lib/services/auth";
import { Switch } from "@/components/ui/switch";
import { usePrivacyStore } from "@/store/privacy";
import { PageHeader } from "@/components/layout/PageHeader";

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
  const [profile, setProfile] = useState<ProfileSettings | null>(null);
  const [birthDate, setBirthDate] = useState("");
  const [planToAge, setPlanToAge] = useState("85");
  const { isPrivate: privacyMode, setPrivate } = usePrivacyStore();
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [telegramHasToken, setTelegramHasToken] = useState(false);
  const [telegramTesting, setTelegramTesting] = useState(false);

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

  useEffect(() => {
    getProfile()
      .then((p) => {
        if (!p) return;
        setProfile(p);
        setBirthDate(p.birth_date ?? "");
        setPlanToAge(p.plan_to_age?.toString() ?? "85");
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    api
      .get("/api/v1/settings/privacy")
      .then((r) => r.json())
      .then((d) => setPrivate(d.privacy_mode))
      .catch(() => null);
  }, [setPrivate]);

  useEffect(() => {
    api
      .get("/api/v1/settings/telegram")
      .then((r) => r.json())
      .then((d) => {
        setTelegramChatId(d.chat_id ?? "");
        setTelegramHasToken(d.has_token);
      })
      .catch(() => null);
  }, []);

  async function saveCurrencyPrefs() {
    await api.patch("/api/v1/settings/display", {
      currency_primary: currencyPrimary,
      currency_secondary: currencySecondary,
    });
  }

  async function togglePrivacyMode(value: boolean) {
    setPrivate(value);
    try {
      await api.patch("/api/v1/settings/privacy", { privacy_mode: value });
    } catch {
      setPrivate(!value);
      toast.error("Failed to update privacy mode");
    }
  }

  async function saveTelegramConfig() {
    try {
      const payload: Record<string, string> = { chat_id: telegramChatId };
      if (telegramToken) payload.bot_token = telegramToken;
      await api.put("/api/v1/settings/telegram", payload);
      setTelegramHasToken(true);
      setTelegramToken("");
      toast.success("Telegram config saved");
    } catch {
      toast.error("Failed to save Telegram config");
    }
  }

  async function testTelegram() {
    setTelegramTesting(true);
    try {
      await api.post("/api/v1/settings/telegram/test", {});
      toast.success("Test message sent — check your Telegram");
    } catch {
      toast.error("Telegram delivery failed — check your token and chat ID");
    } finally {
      setTelegramTesting(false);
    }
  }

  async function saveProfileSettings() {
    const result = await saveProfile({
      birth_date: birthDate || null,
      plan_to_age: planToAge ? parseInt(planToAge) : null,
    });
    if (result) {
      setProfile(result);
      setBirthDate(result.birth_date ?? "");
      setPlanToAge(result.plan_to_age?.toString() ?? "85");
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="Settings" />

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="ai">AI & LLM</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
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

          <Card>
            <CardHeader>
              <CardTitle>Display</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-4 sm:items-end">
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
                <Button
                  onClick={async () => {
                    try {
                      await saveCurrencyPrefs();
                      toast.success("Display settings saved");
                    } catch {
                      toast.error("Failed to save settings");
                    }
                  }}
                  className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
                >
                  Save
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-4 sm:items-end">
                <div className="flex-1">
                  <label className="text-sm font-medium mb-1 block">Date of Birth</label>
                  <Input
                    type="date"
                    value={birthDate}
                    onChange={(e) => setBirthDate(e.target.value)}
                  />
                </div>
                <div className="flex-1">
                  <label className="text-sm font-medium mb-1 block">Plan to Age</label>
                  <Input
                    type="number"
                    min={1}
                    max={120}
                    value={planToAge}
                    onChange={(e) => setPlanToAge(e.target.value)}
                    placeholder="85"
                  />
                </div>
                <Button
                  onClick={async () => {
                    try {
                      await saveProfileSettings();
                      toast.success("Profile saved");
                    } catch {
                      toast.error("Failed to save profile");
                    }
                  }}
                  className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
                >
                  Save
                </Button>
              </div>
              {profile?.current_age != null && (
                <div className="text-xs text-muted-foreground space-y-0.5">
                  <p>Current age: {profile.current_age}</p>
                  <p>
                    Planning horizon: Until {profile.target_year} ({profile.years_remaining} years remaining)
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Privacy</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Privacy Mode</p>
                  <p className="text-xs text-muted-foreground">
                    Hide portfolio values across the app
                  </p>
                </div>
                <Switch
                  checked={privacyMode}
                  onCheckedChange={togglePrivacyMode}
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="mt-4">
          <AISettings />
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Telegram Alerts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-md bg-muted px-4 py-3 text-xs text-muted-foreground space-y-1">
                <p className="font-medium text-foreground">How to set up</p>
                <p>1. Open Telegram → search <span className="font-mono">@BotFather</span> → send <span className="font-mono">/newbot</span></p>
                <p>2. Follow the prompts — copy the <strong>Bot Token</strong> it gives you</p>
                <p>3. To get your <strong>Chat ID</strong>: message <span className="font-mono">@userinfobot</span> on Telegram — it replies with your ID</p>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium mb-1 block">Bot Token</label>
                  <Input
                    type="password"
                    placeholder={telegramHasToken ? "••••••••" : "Enter bot token from @BotFather"}
                    value={telegramToken}
                    onChange={(e) => setTelegramToken(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1 block">Chat ID</label>
                  <Input
                    placeholder="e.g. 123456789"
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={saveTelegramConfig}
                    disabled={(!telegramToken && !telegramHasToken) || !telegramChatId}
                    className="hover:bg-primary/90 active:scale-95 transition-all cursor-pointer"
                  >
                    Save
                  </Button>
                  <Button
                    variant="outline"
                    onClick={testTelegram}
                    disabled={telegramTesting || !telegramHasToken}
                    className="active:scale-95 transition-all cursor-pointer"
                  >
                    {telegramTesting ? "Sending…" : "Send Test Message"}
                  </Button>
                </div>
                {telegramHasToken && (
                  <p className="text-xs text-muted-foreground">
                    Bot token saved. Enter a new token to replace it.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
