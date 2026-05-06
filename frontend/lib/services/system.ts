import { api } from "@/lib/api";

export async function exportSystem(): Promise<void> {
  const res = await api.get("/api/v1/system/export");
  if (!res.ok) throw new Error(`Export failed (${res.status})`);

  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "zentri-backup.json";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function importSystem(file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);

  const res = await api.postForm("/api/v1/system/import", form);

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? "Import failed");
  }
}
