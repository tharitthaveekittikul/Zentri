"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchPlatforms,
  createPlatform,
  deletePlatform,
} from "@/lib/services/platforms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

export function PlatformsManager() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [types, setTypes] = useState("us_stock");

  const { data: platforms = [] } = useQuery({
    queryKey: ["platforms"],
    queryFn: fetchPlatforms,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createPlatform({
        name,
        asset_types_supported: types
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platforms"] });
      setName("");
      setTypes("us_stock");
      toast.success("Platform added");
    },
    onError: () => toast.error("Failed to add platform"),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlatform,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platforms"] });
      toast.success("Platform removed");
    },
    onError: () => toast.error("Failed to remove platform"),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Broker Platforms</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2 items-end">
          <div className="flex-1 space-y-1">
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Robinhood"
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label>Asset Types (comma separated)</Label>
            <Input
              value={types}
              onChange={(e) => setTypes(e.target.value)}
              placeholder="us_stock, crypto"
            />
          </div>
          <Button
            onClick={() => createMutation.mutate()}
            disabled={!name || createMutation.isPending}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-2">
          {platforms.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between border rounded p-2"
            >
              <div>
                <span className="font-medium text-sm">{p.name}</span>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {p.asset_types_supported.map((t) => (
                    <Badge key={t} variant="secondary" className="text-xs">
                      {t}
                    </Badge>
                  ))}
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => deleteMutation.mutate(p.id)}
                disabled={deleteMutation.isPending}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
          {platforms.length === 0 && (
            <p className="text-sm text-muted-foreground">No platforms yet.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
