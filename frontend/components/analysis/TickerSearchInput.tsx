'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

type TickerResult = {
  symbol: string
  name: string
  exchange: string
  type_display: string
}

export function TickerSearchInput({ onClose }: { onClose: () => void }) {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await api.get(`/api/v1/assets/market-search?q=${encodeURIComponent(query)}`)
        if (res.ok) setResults(await res.json())
      } finally {
        setLoading(false)
        setActiveIndex(-1)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  function navigate(symbol: string) {
    onClose()
    router.push(`/analysis/${symbol}`)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose()
      return
    }
    if (e.key === 'ArrowDown') {
      setActiveIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      setActiveIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      navigate(results[activeIndex].symbol)
    }
  }

  return (
    <div ref={containerRef} className="relative w-72">
      <input
        ref={inputRef}
        value={query}
        onChange={e => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Search ticker…"
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-brand)]"
      />
      {(results.length > 0 || loading) && (
        <ul className="absolute left-0 top-full z-50 mt-1 w-full overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--card)] shadow-md">
          {loading && (
            <li className="px-3 py-2 text-xs text-[var(--color-text-muted)]">Searching…</li>
          )}
          {results.map((r, i) => (
            <li
              key={r.symbol}
              className={`cursor-pointer px-3 py-2 text-sm transition-colors ${
                i === activeIndex
                  ? 'bg-[var(--color-brand)]/10 text-[var(--color-text-primary)]'
                  : 'hover:bg-[var(--color-brand)]/5 text-[var(--color-text-primary)]'
              }`}
              onMouseDown={() => navigate(r.symbol)}
            >
              <span className="font-semibold">{r.symbol}</span>
              <span className="ml-2 text-[var(--color-text-muted)]">
                {r.name} · {r.exchange}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
