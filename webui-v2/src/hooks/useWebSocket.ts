/**
 * useWebSocket - WebSocket Hook for Real-time Chat
 *
 * Provides WebSocket connection management with:
 * - Auto-connect/disconnect lifecycle
 * - Message streaming support
 * - Reconnection handling
 * - Error recovery
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { config } from '@platform/config/env'

export interface WebSocketMessage {
  type: 'token' | 'complete' | 'error'
  content: string
  messageId?: string
  metadata?: Record<string, unknown>
}

export interface WebSocketOptions {
  sessionId: string
  onMessage?: (message: WebSocketMessage) => void
  onError?: (error: Event) => void
  onConnect?: () => void
  onDisconnect?: () => void
  autoConnect?: boolean
}

export interface UseWebSocketReturn {
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  sendMessage: (content: string, metadata?: Record<string, unknown>) => void
  connect: () => void
  disconnect: () => void
}

/**
 * useWebSocket Hook
 *
 * Manages WebSocket connection for real-time chat
 *
 * @param options WebSocket connection options
 * @returns WebSocket state and control methods
 *
 * @example
 * ```tsx
 * const { isConnected, sendMessage } = useWebSocket({
 *   sessionId: 'session-1',
 *   onMessage: (msg) => {
 *     if (msg.type === 'token') {
 *       appendToken(msg.content)
 *     } else if (msg.type === 'complete') {
 *       finalizeMessage()
 *     }
 *   }
 * })
 * ```
 */
export function useWebSocket({
  sessionId,
  onMessage,
  onError,
  onConnect,
  onDisconnect,
  autoConnect = true,
}: WebSocketOptions): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef(0)

  const MAX_RECONNECT_ATTEMPTS = 5
  const RECONNECT_DELAY = 2000

  // Cleanup function
  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  // Connect function
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    cleanup()
    setIsConnecting(true)
    setError(null)

    try {
      // Construct WebSocket URL from API base URL
      // Convert http://localhost:9090 to ws://localhost:9090
      const apiUrl = new URL(config.apiBaseUrl)
      const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${apiUrl.host}/ws/chat/${sessionId}`

      console.log('[WebSocket] Connecting to:', wsUrl)
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        setIsConnecting(false)
        setError(null)
        reconnectAttemptsRef.current = 0
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage
          onMessage?.(message)
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = (event) => {
        setError('WebSocket connection error')
        onError?.(event)
      }

      ws.onclose = () => {
        setIsConnected(false)
        setIsConnecting(false)
        onDisconnect?.()

        // Auto-reconnect if not manually closed
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect()
          }, RECONNECT_DELAY)
        } else {
          setError('Connection lost. Please refresh the page.')
        }
      }
    } catch (err) {
      setError('Failed to create WebSocket connection')
      setIsConnecting(false)
    }
  }, [sessionId, onMessage, onError, onConnect, onDisconnect, cleanup])

  // Disconnect function
  const disconnect = useCallback(() => {
    reconnectAttemptsRef.current = MAX_RECONNECT_ATTEMPTS // Prevent auto-reconnect
    cleanup()
    setIsConnected(false)
    setIsConnecting(false)
  }, [cleanup])

  // Send message function
  const sendMessage = useCallback(
    (content: string, metadata?: Record<string, unknown>) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError('Not connected to server')
        return
      }

      try {
        const message = {
          type: 'user_message',  // ✅ Backend expects 'user_message', not 'message'
          content,
          metadata: metadata || {},
        }
        wsRef.current.send(JSON.stringify(message))
      } catch (err) {
        setError('Failed to send message')
        console.error('WebSocket send error:', err)
      }
    },
    []
  )

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect()
    }

    return () => {
      cleanup()
    }
  }, [autoConnect, connect, cleanup])

  return {
    isConnected,
    isConnecting,
    error,
    sendMessage,
    connect,
    disconnect,
  }
}
