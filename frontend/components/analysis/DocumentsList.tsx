const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

type DocItem = {
  id: string
  filename: string
  file_path: string
  source_url: string | null
  status: string
}

type DocumentsListProps = {
  documents: DocItem[]
  ticker: string
}

function getDisplayPath(filePath: string, ticker: string): string {
  const idx = filePath.indexOf(`/${ticker.toUpperCase()}/`)
  return idx >= 0 ? filePath.slice(idx) : filePath
}

export function DocumentsList({ documents, ticker }: DocumentsListProps) {
  if (documents.length === 0) {
    return <p className="text-sm text-[var(--color-text-muted)] italic">No documents stored yet.</p>
  }

  return (
    <ul className="space-y-2">
      {documents.map((doc) => {
        const isExternal = doc.source_url && !doc.file_path
        const openUrl = isExternal
          ? doc.source_url!
          : `${API_BASE}/documents/${doc.id}/file`

        return (
          <li key={doc.id} className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[var(--color-text-primary)]">
                {doc.filename}
              </p>
              <p className="truncate text-xs text-[var(--color-text-muted)]">
                {isExternal ? doc.source_url : getDisplayPath(doc.file_path, ticker)}
              </p>
            </div>
            <a
              href={openUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 text-xs text-[var(--color-brand)] underline hover:no-underline"
            >
              ↗ Open
            </a>
          </li>
        )
      })}
    </ul>
  )
}
