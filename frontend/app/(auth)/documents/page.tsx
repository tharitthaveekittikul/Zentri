"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";

interface Document {
  id: string;
  filename: string;
  asset_id: string | null;
  status: "pending" | "processing" | "done" | "failed";
  chunk_count: number | null;
  error_msg: string | null;
  created_at: string;
}

const STATUS_BADGE: Record<Document["status"], string> = {
  pending: "bg-muted text-muted-foreground",
  processing: "bg-primary text-primary-foreground animate-pulse",
  done: "bg-brand-accent text-white",
  failed: "bg-destructive text-white",
};

/** For multipart/FormData uploads we cannot use api (it forces JSON content-type). */
function uploadWithAuth(path: string, body: FormData): Promise<Response> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("access_token")
      : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(path, { method: "POST", headers, body });
}

const DOC_TYPES = ["research", "annual_report", "earnings", "news", "general"];

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [assetSymbol, setAssetSymbol] = useState("");
  const [docType, setDocType] = useState("research");
  const fileRef = useRef<HTMLInputElement>(null);
  const [duplicateInfo, setDuplicateInfo] = useState<{ existing_id: string; existing_filename: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const url = filter
        ? `/api/v1/documents?asset=${filter.toUpperCase()}`
        : "/api/v1/documents";
      const res = await api.get(url);
      if (res.ok) {
        setDocs(await res.json());
      } else {
        setError("Failed to load documents. Please try again.");
      }
    } catch {
      setError("Failed to load documents. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function handleUpload(replaceId?: string) {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    if (assetSymbol) form.append("asset_symbol", assetSymbol.toUpperCase());
    const url = replaceId
      ? `/api/v1/documents/upload?replace_id=${replaceId}`
      : "/api/v1/documents/upload";
    const res = await uploadWithAuth(url, form);
    setUploading(false);
    if (res.status === 409) {
      const data = await res.json();
      setDuplicateInfo(data);
      setUploadOpen(false);
      return;
    }
    setUploadOpen(false);
    setDuplicateInfo(null);
    load();
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this document?")) return;
    await api.delete(`/api/v1/documents/${id}`);
    load();
  }

  async function handleReingest(id: string) {
    await api.post(`/api/v1/documents/${id}/reingest`, {});
    load();
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Documents" />
      {error && (
        <div className="rounded-lg bg-[color-mix(in_oklch,var(--color-destructive)_10%,transparent)] dark:bg-[color-mix(in_oklch,var(--color-destructive)_15%,transparent)] border border-[var(--color-brand-danger)] px-4 py-3 text-sm text-[var(--color-brand-danger)]">
          {error}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-end gap-3">
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger render={<Button />}>Upload PDF</DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Research Document</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-2">
              <div>
                <Label>Asset Symbol (optional)</Label>
                <Input
                  placeholder="e.g. AAPL"
                  value={assetSymbol}
                  onChange={(e) => setAssetSymbol(e.target.value)}
                />
              </div>
              <div>
                <Label>Document Type</Label>
                <Select
                  value={docType}
                  onValueChange={(value) => {
                    if (value !== null) setDocType(value);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOC_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>PDF File</Label>
                <Input type="file" accept=".pdf" ref={fileRef} />
              </div>
              <Button
                onClick={() => handleUpload()}
                disabled={uploading}
                className="w-full"
              >
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Dialog open={!!duplicateInfo} onOpenChange={(open) => { if (!open) setDuplicateInfo(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duplicate File Detected</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-[var(--color-ink-muted)] py-2">
            A file with identical content already exists as{" "}
            <span className="font-mono font-medium">{duplicateInfo?.existing_filename}</span>.
            Replace it with the new upload?
          </p>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setDuplicateInfo(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={uploading}
              onClick={() => {
                if (duplicateInfo) handleUpload(duplicateInfo.existing_id);
              }}
            >
              {uploading ? "Replacing…" : "Replace"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <div className="bg-card card-surface rounded-2xl p-5 space-y-4">
        <Input
          placeholder="Filter by asset symbol…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-xs"
        />

        {loading ? (
          <div className="space-y-3">
            <div className="flex gap-4 pb-2 border-b">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-4 flex-1" />
              ))}
            </div>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                {Array.from({ length: 5 }).map((_, j) => (
                  <Skeleton key={j} className="h-4 flex-1" />
                ))}
              </div>
            ))}
          </div>
        ) : (
        <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Chunks</TableHead>
              <TableHead>Uploaded</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {docs.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="font-mono text-sm">{doc.filename}</TableCell>
                <TableCell>
                  <Badge className={STATUS_BADGE[doc.status]}>{doc.status}</Badge>
                  {doc.error_msg && (
                    <p className="text-xs text-destructive mt-1">{doc.error_msg}</p>
                  )}
                </TableCell>
                <TableCell>{doc.chunk_count ?? "—"}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(doc.created_at).toLocaleDateString("en-GB")}
                </TableCell>
                <TableCell className="flex gap-2">
                  {doc.status === "failed" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleReingest(doc.id)}
                    >
                      Re-ingest
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(doc.id)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {docs.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="text-center text-muted-foreground py-8"
                >
                  No documents yet. Upload a PDF to get started.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        </div>
        )}
      </div>
    </div>
  );
}
