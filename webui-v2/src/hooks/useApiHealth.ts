/**
 * useApiHealth - API Health Check Hook
 *
 * Monitors API connection status with automatic polling
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { httpClient } from '@platform/http'
import type { ApiStatusType } from '@/ui'

interface ApiHealthResponse {
  status: 'ok' | 'error'
  timestamp: string
  details?: {
    database?: 'connected' | 'disconnected'
    cache?: 'connected' | 'disconnected'
    [key: string]: string | undefined
  }
}

interface UseApiHealthOptions {
  /**
   * Polling interval in milliseconds
   * @default 30000 (30 seconds)
   */
  pollInterval?: number
  /**
   * Enable/disable automatic polling
   * @default true
   */
  enabled?: boolean
}

interface UseApiHealthReturn {
  status: ApiStatusType
  lastCheck: Date | null
  details: ApiHealthResponse | null
  error: Error | null
  refresh: () => Promise<void>
}

/**
 * Hook to monitor API health status
 */
export function useApiHealth(options: UseApiHealthOptions = {}): UseApiHealthReturn {
  const { pollInterval = 30000, enabled = true } = options

  const [status, setStatus] = useState<ApiStatusType>('checking')
  const [lastCheck, setLastCheck] = useState<Date | null>(null)
  const [details, setDetails] = useState<ApiHealthResponse | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const inFlightRef = useRef(false)

  const checkHealth = useCallback(async (showChecking = false) => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    let timeoutId: number | undefined
    const startedAt = Date.now()

    if (import.meta.env.DEV) {
      console.debug('[ApiHealth] check started', {
        showChecking,
        pollInterval,
        endpoint: '/api/health',
      })
    }

    if (showChecking) {
      setStatus('checking')
    }
    setError(null)

    try {
      // Keep a hard timeout guard to avoid hanging forever in checking state.
      const timeoutPromise = new Promise<never>((_, reject) => {
        timeoutId = window.setTimeout(() => reject(new Error('Health check timeout')), 5500)
      })
      const response = await Promise.race([
        httpClient.get<ApiHealthResponse>('/api/health', { timeout: 5000 }),
        timeoutPromise,
      ])

      setStatus('connected')
      setDetails(response.data ?? null)
      if (import.meta.env.DEV) {
        console.debug('[ApiHealth] check success', {
          elapsedMs: Date.now() - startedAt,
          apiStatus: response.data?.status,
          hasDetails: !!response.data?.details,
        })
      }
    } catch (err) {
      setStatus('disconnected')
      setDetails(null)
      const normalizedError = err instanceof Error ? err : new Error('Unknown error')
      setError(normalizedError)
      if (import.meta.env.DEV) {
        console.warn('[ApiHealth] check failed', {
          elapsedMs: Date.now() - startedAt,
          message: normalizedError.message,
          name: normalizedError.name,
        })
      }
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId)
      }
      setLastCheck(new Date())
      inFlightRef.current = false
    }
  }, [])

  // Initial check and polling
  useEffect(() => {
    if (!enabled) {
      return
    }
    if (import.meta.env.DEV) {
      console.debug('[ApiHealth] polling enabled', { pollInterval })
    }

    // Initial check
    void checkHealth(true)

    // Set up polling
    const interval = setInterval(() => {
      // Preserve last known status during background checks.
      void checkHealth(false)
    }, pollInterval)

    return () => {
      clearInterval(interval)
      if (import.meta.env.DEV) {
        console.debug('[ApiHealth] polling disabled')
      }
    }
  }, [checkHealth, pollInterval, enabled])

  return {
    status,
    lastCheck,
    details,
    error,
    refresh: () => checkHealth(true),
  }
}
