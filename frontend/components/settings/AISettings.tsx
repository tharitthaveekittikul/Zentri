"use client";

import { useEffect, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ChevronDownIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ModelTooltip } from "@/components/settings/ModelTooltip";
import {
  ProviderConfig,
  Provider,
  listProviderConfigs,
  createProviderConfig,
  testConnection,
  fetchModels,
  deleteProviderConfig,
} from "@/lib/services/provider-config";
import {
  FeatureLLMConfig,
  FEATURE_LABELS,
  listFeatureConfigs,
  createFeatureConfig,
  updateFeatureConfig,
  resetPrompt,
} from "@/lib/services/feature-llm-config";

const PROVIDER_OPTIONS: { value: Provider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Gemini" },
  { value: "ollama", label: "Ollama (Local)" },
  { value: "openrouter", label: "OpenRouter" },
];

const FEATURE_KEYS = [
  "import_translator",
  "portfolio_analysis",
  "overview_analysis",
  "chat",
  "watchlist_scan",
  "watchlist_discovery",
  "ipo_analysis",
];

type FeatureEdit = {
  provider_config_id: string;
  model: string;
  system_prompt: string;
};

function ModelCombobox({
  models,
  value,
  onChange,
  disabled,
}: {
  models: string[];
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex w-full items-center justify-between gap-1.5 rounded-lg border border-input bg-transparent h-8 py-2 pr-2 pl-2.5 text-sm whitespace-nowrap transition-colors outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
          !value && "text-muted-foreground",
        )}
      >
        <span className="flex-1 text-left truncate">
          {value || "Select model..."}
        </span>
        <ChevronDownIcon className="size-4 text-muted-foreground shrink-0" />
      </button>
      {open && (
        <div className="absolute z-50 top-full mt-1 w-full rounded-lg border border-foreground/10 bg-popover text-popover-foreground shadow-md overflow-hidden">
          <Command>
            <CommandInput placeholder="Search models..." />
            <CommandList>
              <CommandEmpty>No models found.</CommandEmpty>
              <CommandGroup>
                {models.map((m) => (
                  <CommandItem
                    key={m}
                    value={m}
                    onSelect={(v) => {
                      onChange(v);
                      setOpen(false);
                    }}
                  >
                    {m}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </div>
      )}
    </div>
  );
}

export function AISettings() {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [features, setFeatures] = useState<FeatureLLMConfig[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingFeatures, setLoadingFeatures] = useState(true);

  const [newProvider, setNewProvider] = useState<Provider>("anthropic");
  const [newApiKey, setNewApiKey] = useState("");
  const [newHostUrl, setNewHostUrl] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [addStatus, setAddStatus] = useState<string | null>(null);

  const [actionStates, setActionStates] = useState<
    Record<
      string,
      {
        testing?: boolean;
        refreshing?: boolean;
        removing?: boolean;
        error?: string;
      }
    >
  >({});

  const [featureEdits, setFeatureEdits] = useState<Record<string, FeatureEdit>>(
    {},
  );
  const [featureSaving, setFeatureSaving] = useState<Record<string, boolean>>(
    {},
  );
  const [featureErrors, setFeatureErrors] = useState<Record<string, string>>(
    {},
  );

  useEffect(() => {
    listProviderConfigs()
      .then(setProviders)
      .catch(() => null)
      .finally(() => setLoadingProviders(false));
    listFeatureConfigs()
      .then(setFeatures)
      .catch(() => null)
      .finally(() => setLoadingFeatures(false));
  }, []);

  useEffect(() => {
    const edits: Record<string, FeatureEdit> = {};
    for (const f of features) {
      edits[f.feature_key] = {
        provider_config_id: f.provider_config_id,
        model: f.model,
        system_prompt: f.system_prompt,
      };
    }
    setFeatureEdits(edits);
  }, [features]);

  function setProviderAction(
    id: string,
    patch: {
      testing?: boolean;
      refreshing?: boolean;
      removing?: boolean;
      error?: string;
    },
  ) {
    setActionStates((prev) => ({ ...prev, [id]: { ...prev[id], ...patch } }));
  }

  function updateEdit(featureKey: string, patch: Partial<FeatureEdit>) {
    setFeatureEdits((prev) => ({
      ...prev,
      [featureKey]: {
        ...(prev[featureKey] ?? {
          provider_config_id: "",
          model: "",
          system_prompt: "",
        }),
        ...patch,
      },
    }));
  }

  async function handleTestConnection(id: string) {
    setProviderAction(id, { testing: true, error: undefined });
    try {
      const updated = await testConnection(id);
      setProviders((prev) => prev.map((p) => (p.id === id ? updated : p)));
    } catch (e) {
      setProviderAction(id, { error: (e as Error).message });
    } finally {
      setProviderAction(id, { testing: false });
    }
  }

  async function handleRefreshModels(id: string) {
    setProviderAction(id, { refreshing: true, error: undefined });
    try {
      const updated = await fetchModels(id);
      setProviders((prev) => prev.map((p) => (p.id === id ? updated : p)));
    } catch (e) {
      setProviderAction(id, { error: (e as Error).message });
    } finally {
      setProviderAction(id, { refreshing: false });
    }
  }

  async function handleRemoveProvider(id: string) {
    setProviderAction(id, { removing: true, error: undefined });
    try {
      await deleteProviderConfig(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      setProviderAction(id, { error: (e as Error).message });
    } finally {
      setProviderAction(id, { removing: false });
    }
  }

  async function handleAddAndTest() {
    setAdding(true);
    setAddError(null);
    setAddStatus("Adding provider...");
    try {
      const created = await createProviderConfig(
        newProvider,
        newProvider !== "ollama" ? newApiKey : undefined,
        newProvider === "ollama" ? newHostUrl : undefined,
      );
      setAddStatus("Testing connection...");
      const tested = await testConnection(created.id);
      setAddStatus("Fetching models...");
      const withModels = await fetchModels(tested.id);
      setProviders((prev) => [...prev, withModels]);
      setNewApiKey("");
      setNewHostUrl("");
    } catch (e) {
      setAddError((e as Error).message);
    } finally {
      setAdding(false);
      setAddStatus(null);
    }
  }

  function getModelsForProvider(providerId: string): string[] {
    return providers.find((p) => p.id === providerId)?.models_cache ?? [];
  }

  async function handleSaveFeature(featureKey: string) {
    const edit = featureEdits[featureKey];
    if (!edit) return;
    setFeatureSaving((prev) => ({ ...prev, [featureKey]: true }));
    setFeatureErrors((prev) => ({ ...prev, [featureKey]: "" }));
    try {
      const existing = features.find((f) => f.feature_key === featureKey);
      let updated: FeatureLLMConfig;
      if (existing) {
        updated = await updateFeatureConfig(existing.id, {
          provider_config_id: edit.provider_config_id,
          model: edit.model,
          system_prompt: edit.system_prompt,
        });
      } else {
        updated = await createFeatureConfig(
          featureKey,
          edit.provider_config_id,
          edit.model,
          edit.system_prompt,
        );
      }
      setFeatures((prev) => {
        const exists = prev.find((f) => f.feature_key === featureKey);
        if (exists)
          return prev.map((f) => (f.feature_key === featureKey ? updated : f));
        return [...prev, updated];
      });
    } catch (e) {
      setFeatureErrors((prev) => ({
        ...prev,
        [featureKey]: (e as Error).message,
      }));
    } finally {
      setFeatureSaving((prev) => ({ ...prev, [featureKey]: false }));
    }
  }

  async function handleResetPrompt(featureKey: string) {
    const existing = features.find((f) => f.feature_key === featureKey);
    if (!existing) return;
    try {
      const updated = await resetPrompt(existing.id);
      setFeatures((prev) =>
        prev.map((f) => (f.feature_key === featureKey ? updated : f)),
      );
      updateEdit(featureKey, { system_prompt: updated.system_prompt });
    } catch (e) {
      setFeatureErrors((prev) => ({
        ...prev,
        [featureKey]: (e as Error).message,
      }));
    }
  }

  return (
    <div className="space-y-6">
      {/* AI Providers */}
      <Card>
        <CardHeader>
          <CardTitle>AI Providers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingProviders ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : providers.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No providers configured yet.
            </p>
          ) : (
            providers.map((p) => {
              const state = actionStates[p.id] ?? {};
              return (
                <div key={p.id} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="font-medium capitalize">
                        {p.provider}
                      </span>
                      <Badge variant={p.is_connected ? "default" : "secondary"}>
                        {p.is_connected ? "Connected" : "Not connected"}
                      </Badge>
                      {p.models_cache.length > 0 && (
                        <span className="text-xs text-muted-foreground">
                          {p.models_cache.length} models
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={state.testing}
                        onClick={() => handleTestConnection(p.id)}
                      >
                        {state.testing ? "Testing..." : "Test"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={state.refreshing}
                        onClick={() => handleRefreshModels(p.id)}
                      >
                        {state.refreshing ? "Refreshing..." : "Refresh Models"}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={state.removing}
                        onClick={() => handleRemoveProvider(p.id)}
                      >
                        {state.removing ? "Removing..." : "Remove"}
                      </Button>
                    </div>
                  </div>
                  {p.host_url && (
                    <p className="text-xs text-muted-foreground">
                      Host: {p.host_url}
                    </p>
                  )}
                  {state.error && (
                    <p className="text-xs text-destructive">{state.error}</p>
                  )}
                </div>
              );
            })
          )}

          <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
            <p className="text-sm font-medium">Add Provider</p>
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select
                value={newProvider}
                onValueChange={(v) => {
                  if (v) setNewProvider(v as Provider);
                  setNewApiKey("");
                  setNewHostUrl("");
                  setAddError(null);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDER_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {newProvider !== "ollama" ? (
              <div className="space-y-2">
                <Label>API Key</Label>
                <Input
                  type="password"
                  placeholder="sk-..."
                  value={newApiKey}
                  onChange={(e) => setNewApiKey(e.target.value)}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label>Host URL</Label>
                <Input
                  placeholder="http://localhost:11434"
                  value={newHostUrl}
                  onChange={(e) => setNewHostUrl(e.target.value)}
                />
              </div>
            )}

            {adding && addStatus && (
              <p className="text-xs text-muted-foreground">{addStatus}</p>
            )}
            {addError && <p className="text-xs text-destructive">{addError}</p>}

            <Button
              disabled={
                adding ||
                (newProvider !== "ollama" && !newApiKey.trim()) ||
                (newProvider === "ollama" && !newHostUrl.trim())
              }
              onClick={handleAddAndTest}
            >
              {adding ? (addStatus ?? "Adding...") : "Add & Test"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* LLM Assignment */}
      <Card>
        <CardHeader>
          <CardTitle>LLM Assignment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {providers.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Add and test a provider above to assign models to features.
            </p>
          ) : loadingFeatures ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : (
            FEATURE_KEYS.map((featureKey) => {
              const edit = featureEdits[featureKey] ?? {
                provider_config_id: "",
                model: "",
                system_prompt: "",
              };
              const models = getModelsForProvider(edit.provider_config_id);
              const saving = featureSaving[featureKey] ?? false;
              const error = featureErrors[featureKey];
              const hasExisting = features.some(
                (f) => f.feature_key === featureKey,
              );
              const providerNoModels =
                !!edit.provider_config_id && models.length === 0;

              return (
                <div
                  key={featureKey}
                  className="space-y-3 border rounded-lg p-4"
                >
                  <p className="text-sm font-semibold">
                    {FEATURE_LABELS[featureKey] ?? featureKey}
                  </p>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label>Provider</Label>
                      <Select
                        value={edit.provider_config_id}
                        onValueChange={(v) =>
                          updateEdit(featureKey, {
                            provider_config_id: v ?? "",
                            model: "",
                          })
                        }
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select provider...">
                            {edit.provider_config_id
                              ? (PROVIDER_OPTIONS.find(
                                  (opt) =>
                                    opt.value ===
                                    providers.find((p) => p.id === edit.provider_config_id)?.provider
                                )?.label ??
                                providers.find((p) => p.id === edit.provider_config_id)?.provider)
                              : undefined}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {providers.map((p) => (
                            <SelectItem key={p.id} value={p.id}>
                              {PROVIDER_OPTIONS.find((opt) => opt.value === p.provider)?.label ?? p.provider}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center gap-1.5">
                        <Label>Model</Label>
                        <ModelTooltip featureKey={featureKey} />
                      </div>
                      {providerNoModels ? (
                        <p className="text-xs text-muted-foreground pt-1.5">
                          Test connection first to load models.
                        </p>
                      ) : (
                        <ModelCombobox
                          models={models}
                          value={edit.model}
                          onChange={(v) => updateEdit(featureKey, { model: v })}
                          disabled={
                            !edit.provider_config_id || models.length === 0
                          }
                        />
                      )}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>System Prompt</Label>
                    <Textarea
                      rows={3}
                      value={edit.system_prompt}
                      onChange={(e) =>
                        updateEdit(featureKey, {
                          system_prompt: e.target.value,
                        })
                      }
                    />
                  </div>

                  {error && <p className="text-xs text-destructive">{error}</p>}

                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={
                        saving || !edit.provider_config_id || !edit.model
                      }
                      onClick={() => handleSaveFeature(featureKey)}
                    >
                      {saving ? "Saving..." : "Save"}
                    </Button>
                    {hasExisting && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleResetPrompt(featureKey)}
                      >
                        Reset Prompt
                      </Button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
