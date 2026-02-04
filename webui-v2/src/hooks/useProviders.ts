/**
 * useProviders - Providers data management hook
 *
 * Manages provider list, status, and lifecycle operations
 */

import { useState, useEffect, useCallback } from 'react'
import {
  providersApi,
  type ProviderStatusResponse,
} from '@/api/providers'

export interface ProviderCardData {
  id: string
  label: string
  type: string
  state: string
  endpoint: string | null
  supports_models: boolean
  supports_start: boolean
  latency_ms: number | null
  last_ok_at: string | null
  last_error: string | null
  models_count?: number
}

interface UseProvidersOptions {
  /**
   * Auto-refresh interval in milliseconds
   * @default 0 (disabled)
   */
  pollInterval?: number
}

interface UseProvidersReturn {
  providers: ProviderCardData[]
  loading: boolean
  error: Error | null
  refresh: () => Promise<void>
  startOllama: () => Promise<void>
  stopOllama: () => Promise<void>
  restartOllama: () => Promise<void>
}

/**
 * Hook to manage providers data
 *
 * P0-17: Loads provider list and status
 * P0-20: Provides lifecycle control methods
 * P0-21: Supports manual and automatic refresh
 */
export function useProviders(options: UseProvidersOptions = {}): UseProvidersReturn {
  const { pollInterval = 0 } = options

  const [providers, setProviders] = useState<ProviderCardData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  /**
   * Load providers list and status
   */
  const loadProviders = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch list and status in parallel
      const [listResult, statusResult] = await Promise.all([
        providersApi.listProviders(),
        providersApi.getProvidersStatus(),
      ])

      // Create status lookup map
      const statusMap = new Map<string, ProviderStatusResponse>()
      statusResult.providers.forEach((status) => {
        statusMap.set(status.id, status)
      })

      // Merge list and status data
      const allProviders = [...listResult.local, ...listResult.cloud]
      const merged = allProviders.map((info) => {
        const status = statusMap.get(info.id)
        return {
          id: info.id,
          label: info.label,
          type: info.type,
          state: status?.state || 'unknown',
          endpoint: status?.endpoint || null,
          supports_models: info.supports_models,
          supports_start: info.supports_start,
          latency_ms: status?.latency_ms || null,
          last_ok_at: status?.last_ok_at || null,
          last_error: status?.last_error || null,
        }
      })

      setProviders(merged)
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load providers'))
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * P0-20: Start Ollama service
   */
  const startOllama = useCallback(async () => {
    try {
      await providersApi.startOllama()
      // Refresh status after starting
      await loadProviders()
    } catch (err) {
      throw err instanceof Error ? err : new Error('Failed to start Ollama')
    }
  }, [loadProviders])

  /**
   * P0-20: Stop Ollama service
   */
  const stopOllama = useCallback(async () => {
    try {
      await providersApi.stopOllama()
      // Refresh status after stopping
      await loadProviders()
    } catch (err) {
      throw err instanceof Error ? err : new Error('Failed to stop Ollama')
    }
  }, [loadProviders])

  /**
   * P0-20: Restart Ollama service
   */
  const restartOllama = useCallback(async () => {
    try {
      await providersApi.restartOllama()
      // Refresh status after restarting
      await loadProviders()
    } catch (err) {
      throw err instanceof Error ? err : new Error('Failed to restart Ollama')
    }
  }, [loadProviders])

  /**
   * P0-21: Manual refresh
   */
  const refresh = useCallback(async () => {
    await loadProviders()
  }, [loadProviders])

  // Initial load
  useEffect(() => {
    loadProviders()
  }, [loadProviders])

  // P0-21: Auto-refresh polling
  useEffect(() => {
    if (pollInterval <= 0) {
      return
    }

    const interval = setInterval(() => {
      loadProviders()
    }, pollInterval)

    return () => clearInterval(interval)
  }, [pollInterval, loadProviders])

  return {
    providers,
    loading,
    error,
    refresh,
    startOllama,
    stopOllama,
    restartOllama,
  }
}
