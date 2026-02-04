/**
 * useApiHealth - API Health Check Hook
 *
 * Monitors API connection status with automatic polling
 */

import { useState, useEffect, useCallback } from 'react'
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

  const checkHealth = useCallback(async () => {
    setStatus('checking')
    setError(null)

    try {
      // Try to check API health using httpClient
      const response = await httpClient.get<ApiHealthResponse>('/api/health', {
        timeout: 5000,
      })

      // httpClient returns response.data directly for 2xx responses
      setStatus('connected')
      setDetails(response.data)
      setLastCheck(new Date())
    } catch (err) {
      // If API is not reachable or times out
      setStatus('disconnected')
      setDetails(null)
      setError(err instanceof Error ? err : new Error('Unknown error'))
      setLastCheck(new Date())
    }
  }, [])

  // Initial check and polling
  useEffect(() => {
    if (!enabled) {
      return
    }

    // Initial check
    checkHealth()

    // Set up polling
    const interval = setInterval(checkHealth, pollInterval)

    return () => clearInterval(interval)
  }, [checkHealth, pollInterval, enabled])

  return {
    status,
    lastCheck,
    details,
    error,
    refresh: checkHealth,
  }
}
