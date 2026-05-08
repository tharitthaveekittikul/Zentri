"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ZapIcon, CoinsIcon } from "lucide-react";

interface ConfirmLLMDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title?: string;
  description?: string;
  estimatedCost: string;
  model?: string;
  loading?: boolean;
}

export function ConfirmLLMDialog({
  open,
  onConfirm,
  onCancel,
  title = "Run AI Analysis",
  description,
  estimatedCost,
  model,
  loading = false,
}: ConfirmLLMDialogProps) {
  return (
    <Dialog open={open} onOpenChange={(o: boolean) => { if (!o) onCancel(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ZapIcon className="size-4 text-primary" />
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription>{description}</DialogDescription>
          )}
        </DialogHeader>

        <div className="flex items-center gap-3 rounded-lg border bg-muted/40 px-4 py-3">
          <CoinsIcon className="size-4 text-amber-500 shrink-0" />
          <div>
            <p className="text-xs text-muted-foreground">Estimated cost</p>
            <p className="text-sm font-semibold">{estimatedCost}</p>
          </div>
          {model && (
            <code className="ml-auto text-[11px] text-muted-foreground font-mono truncate max-w-32">
              {model}
            </code>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button size="sm" onClick={onConfirm} disabled={loading} className="gap-1.5">
            <ZapIcon className="size-3.5" />
            {loading ? "Running..." : "Confirm & Run"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
