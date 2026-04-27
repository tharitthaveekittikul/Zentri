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
  pending: "bg-gray-400 text-white",
  processing: "bg-blue-500 text-white animate-pulse",
  done: "bg-green-500 text-white",
  failed: "bg-red-500 text-white",
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
  const [filter, setFilter] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [assetSymbol, setAssetSymbol] = useState("");
  const [docType, setDocType] = useState("research");
  const fileRef = useRef<HTMLInputElement>(null);

  async function load() {
    const url = filter
      ? `/api/v1/documents?asset=${filter.toUpperCase()}`
      : "/api/v1/documents";
    const res = await api.get(url);
    if (res.ok) setDocs(await res.json());
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);
    if (assetSymbol) form.append("asset_symbol", assetSymbol.toUpperCase());
    await uploadWithAuth("/api/v1/documents/upload", form);
    setUploading(false);
    setUploadOpen(false);
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
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Document Library</h1>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger>
            <Button>Upload PDF</Button>
          </DialogTrigger>
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
                onClick={handleUpload}
                disabled={uploading}
                className="w-full"
              >
                {uploading ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Input
        placeholder="Filter by asset symbol…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="max-w-xs"
      />

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
                  <p className="text-xs text-red-500 mt-1">{doc.error_msg}</p>
                )}
              </TableCell>
              <TableCell>{doc.chunk_count ?? "—"}</TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {new Date(doc.created_at).toLocaleDateString()}
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
  );
}
