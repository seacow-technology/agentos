/**
 * Common API response types
 */

export interface ApiResponse<T> {
  ok: boolean
  data?: T
  error?: ApiError
  timestamp?: string
}

export interface ApiError {
  code: string
  message: string
  details?: unknown
}

/**
 * Simple success response
 */
export interface SuccessResponse {
  ok: boolean
  message: string
}

/**
 * Timestamped response
 */
export interface TimestampedResponse {
  ts: string
  cache_ttl_ms?: number
}
