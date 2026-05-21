"use client"

import { useCallback, useEffect, useRef, useState } from "react"

interface UseAnalysisPollingOptions<T> {
  fetchFn: () => Promise<T | null>
  interval?: number
  maxAttempts?: number
}

interface UseAnalysisPollingReturn<T> {
  data: T | null
  loading: boolean
  error: string | null
  trigger: () => Promise<void>
  setData: (d: T | null) => void
}

export function useAnalysisPolling<T extends { id: string; status?: string; error_message?: string | null }>(
  triggerFn: () => Promise<void>,
  { fetchFn, interval = 3000, maxAttempts = 40 }: UseAnalysisPollingOptions<T>,
): UseAnalysisPollingReturn<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const prevIdRef = useRef<string | null>(null)
  const attemptsRef = useRef(0)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const trigger = useCallback(async () => {
    setLoading(true)
    setError(null)
    prevIdRef.current = data?.id ?? null
    attemptsRef.current = 0

    try {
      await triggerFn()
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to trigger"
      setError(msg)
      setLoading(false)
      return
    }

    stopPolling()
    pollRef.current = setInterval(async () => {
      attemptsRef.current += 1

      if (attemptsRef.current >= maxAttempts) {
        setError("Analysis timed out — check server logs")
        setLoading(false)
        stopPolling()
        return
      }

      try {
        const result = await fetchFn()
        if (result && result.id !== prevIdRef.current) {
          if (result.status === "error" && result.error_message) {
            setError(result.error_message)
            setLoading(false)
            stopPolling()
          } else {
            setData(result)
            setError(null)
            setLoading(false)
            stopPolling()
          }
        }
      } catch {
        setError("Polling failed")
        setLoading(false)
        stopPolling()
      }
    }, interval)
  }, [triggerFn, fetchFn, interval, maxAttempts, data?.id, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  return { data, loading, error, trigger, setData }
}
