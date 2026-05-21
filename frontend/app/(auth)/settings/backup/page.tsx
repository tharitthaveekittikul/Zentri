"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { exportSystem, importSystem } from "@/lib/services/system";
import { refreshAssetNames } from "@/lib/services/portfolio";
import { PageHeader } from "@/components/layout/PageHeader";

export default function BackupPage() {
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function handleRefreshNames() {
    setRefreshing(true);
    try {
      const result = await refreshAssetNames();
      toast.success(`Updated ${result.updated} of ${result.total} asset names`);
    } catch {
      toast.error("Failed to refresh names");
    } finally {
      setRefreshing(false);
    }
  }
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    setExporting(true);
    try {
      await exportSystem();
      toast.success("Backup downloaded");
    } catch {
      toast.error("Export failed. Check logs.");
    } finally {
      setExporting(false);
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setConfirmOpen(true);
    e.target.value = "";
  }

  async function handleConfirmImport() {
    if (!pendingFile) return;
    setImporting(true);
    setConfirmOpen(false);
    try {
      await importSystem(pendingFile);
      toast.success("Restore complete. Refreshing...");
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) {
      toast.error((e as Error).message || "Import failed");
    } finally {
      setImporting(false);
      setPendingFile(null);
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <PageHeader title="Backup" />
      <p className="text-sm text-muted-foreground">
        Export all your data to a JSON file or restore from a previous backup.
      </p>

      {/* Security warning */}
      <div className="rounded-lg border border-amber-400 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
        <strong>Security notice:</strong> Backup files contain your API keys in
        plaintext. Do not share or store them in insecure locations.
      </div>

      {/* Refresh Names */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Refresh Asset Names</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Fetch proper names for all assets from yfinance. Covers US stocks, ETFs, Thai stocks, and Thai DRs. Gold, cash, and TH funds are skipped.
          </p>
          <Button variant="outline" onClick={handleRefreshNames} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh All Names"}
          </Button>
        </CardContent>
      </Card>

      {/* Export */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Export</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Downloads a{" "}
            <code className="text-xs bg-muted px-1 rounded">.json</code> file
            containing your portfolio, settings, AI configurations, watchlist,
            and AI analyses.
          </p>
          <Button onClick={handleExport} disabled={exporting}>
            {exporting ? "Exporting..." : "Download Backup"}
          </Button>
        </CardContent>
      </Card>

      {/* Import */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Restore</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Upload a backup file to restore your data.{" "}
            <strong>This will permanently replace all current data.</strong>
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="sr-only"
            disabled={importing}
            aria-label="Upload backup file"
            onChange={handleFileChange}
          />
          <Button
            variant="destructive"
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
          >
            {importing ? "Restoring..." : "Restore from Backup"}
          </Button>
        </CardContent>
      </Card>

      {/* Confirmation dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Replace all data?</DialogTitle>
            <DialogDescription>
              This will permanently delete all your current portfolio, settings,
              watchlist, and AI data, and replace it with the contents of{" "}
              <strong>{pendingFile?.name}</strong>. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setConfirmOpen(false);
                setPendingFile(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmImport}
            >
              Yes, restore
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
