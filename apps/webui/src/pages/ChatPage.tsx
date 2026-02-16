/**
 * ChatPage - Real-time Chat Interface
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.chat.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Chat Contract: AppChatShell Pattern
 * - ✅ P0 Implementation: WebSocket + Session API integration
 * - ✅ Unified Exit: 不自定义布局，使用 AppChatShell 封装
 */

import { useState, useCallback, useEffect, useMemo, useRef, startTransition } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { AppChatShell, type ChatMessageType, type ChatSession } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { usePromptDialog } from '@/ui/interaction/usePromptDialog'
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Chip, TextField } from '@/ui'
import { Box, Typography } from '@mui/material'
import { MessageIcon, PlayIcon as PlayArrowIcon, CheckCircleIcon, SettingsIcon } from '@/ui/icons'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useSessionState } from '@/hooks/useSessionState'
import { systemService } from '@services'
import { providersApi } from '@/api/providers'
import { HealthWarningBanner } from '@/components/HealthWarningBanner'
import { httpClient } from '@platform/http'
import { useDraftProtection } from '@/hooks/useDraftProtection'
import { getChatPreset, type ChatPresetId } from '@/features/chat/presets/chat_presets'

type ConversationMode = 'chat' | 'discussion' | 'plan' | 'development' | 'task'
type ExecutionPhase = 'planning' | 'execution'
type ReplyWaitStage = 'pending' | 'slow' | 'verySlow'

const DEFAULT_CONVERSATION_MODE: ConversationMode = 'chat'
const DEFAULT_EXECUTION_PHASE: ExecutionPhase = 'planning'
const REPLY_RECOVERY_TIMEOUT_MS = 120000

function isPlaceholderLastError(value: unknown): boolean {
  if (value == null) return true
  const normalized = String(value).trim().toLowerCase()
  return normalized === '' || normalized === '-' || normalized === 'none' || normalized === 'null' || normalized === 'undefined' || normalized === 'n/a'
}

function evaluateDaemonHealth(health: any): { healthy: boolean; issues: string[]; hints: string[] } {
  const issues: string[] = []
  const hints: string[] = []

  // Highest-priority signal: explicit ok flag.
  if (typeof health?.ok === 'boolean') {
    if (health.ok) return { healthy: true, issues, hints }
    issues.push('Daemon reported ok=false')
    if (!isPlaceholderLastError(health?.last_error)) {
      hints.push(String(health?.last_error))
    }
    return { healthy: false, issues, hints }
  }

  // Secondary explicit signal.
  if (typeof health?.running === 'boolean') {
    if (health.running) return { healthy: true, issues, hints }
    issues.push('Daemon reported running=false')
    if (!isPlaceholderLastError(health?.last_error)) {
      hints.push(String(health?.last_error))
    }
    return { healthy: false, issues, hints }
  }

  const status = typeof health?.status === 'string' ? health.status.trim().toLowerCase() : ''
  if (status === 'error' || status === 'failed' || status === 'down' || status === 'stopped' || status === 'unhealthy') {
    issues.push(`Daemon status=${status}`)
    if (!isPlaceholderLastError(health?.last_error)) {
      hints.push(String(health?.last_error))
    }
    return { healthy: false, issues, hints }
  }

  // No explicit negative signal: treat as healthy to avoid false positives.
  return { healthy: true, issues, hints }
}

function normalizeConversationMode(value: unknown): ConversationMode {
  const allowed: ConversationMode[] = ['chat', 'discussion', 'plan', 'development', 'task']
  return typeof value === 'string' && allowed.includes(value as ConversationMode)
    ? (value as ConversationMode)
    : DEFAULT_CONVERSATION_MODE
}

function normalizeExecutionPhase(value: unknown): ExecutionPhase {
  return value === 'execution' ? 'execution' : 'planning'
}

function deriveExecutionPhaseByMode(mode: ConversationMode, phase: ExecutionPhase): ExecutionPhase {
  return mode === 'development' || mode === 'task' ? phase : 'planning'
}

export default function ChatPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [currentSessionId, setCurrentSessionId] = useState<string>('')
  const [sessions, setSessions] = useState<Array<ChatSession & { metadata?: Record<string, any> }>>([])
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [awaitingReply, setAwaitingReply] = useState(false)
  const [replyWaitStage, setReplyWaitStage] = useState<ReplyWaitStage>('pending')
  const [currentRunId, setCurrentRunId] = useState<string>('')
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingMessage, setEditingMessage] = useState<ChatMessageType | null>(null)
  const [editingText, setEditingText] = useState('')
  const [editSubmitting, setEditSubmitting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const isE2eBootstrap = useMemo(() => {
    const query = new URLSearchParams(location.search)
    return query.get('e2e') === '1'
  }, [location.search])

  const currentSession = useMemo(() => {
    if (!currentSessionId) return null
    return sessions.find((session) => session.id === currentSessionId) || null
  }, [currentSessionId, sessions])
  const { sessionState, refreshSessionState } = useSessionState(currentSessionId)

  const presetTag = useMemo(() => {
    const presetId = currentSession?.metadata?.preset_id as ChatPresetId | undefined
    if (!presetId || presetId === 'free') return null
    const preset = getChatPreset(presetId)
    return preset?.title ?? null
  }, [currentSession])

  // 🎯 产品级功能：Draft 保护（输入框内容）
  const [inputValue, setInputValue] = useState<string>('')
  const [inputFocused, setInputFocused] = useState(false)

  // 🎯 产品级功能：自动保存 + 崩溃恢复
  const { clearDraft } = useDraftProtection(
    currentSessionId,
    inputValue,
    (restoredContent) => {
      setInputValue(restoredContent)
      console.log('[ChatPage] ✅ Draft restored from crash recovery')
    },
    async ({ preview, contentLength }) => {
      return confirmDialog({
        title: t('page.chat.draftRestoreTitle'),
        message: t('page.chat.draftRestoreMessage', { contentLength, preview }),
        confirmText: t('page.chat.draftRestoreConfirm'),
        cancelText: t('page.chat.draftRestoreDiscard'),
        color: 'warning',
        testId: 'chat-draft-restore-dialog',
      })
    },
  )

  // ✅ Use ref to track streaming message for stable callback reference
  const streamingMessageRef = useRef<string>('')
  const slowReplyTimerRef = useRef<number | null>(null)
  const verySlowReplyTimerRef = useRef<number | null>(null)

  // ✅ P1: Optimization - Buffer for batching delta updates
  const bufferRef = useRef<string>('')
  const rafRef = useRef<number | null>(null)
  const pendingEditCommandsRef = useRef<Record<string, { targetId: string; newContent: string }>>({})
  const pendingToolResultsRef = useRef<Record<string, Record<string, unknown>>>({})
  const pendingReplyStartedAtRef = useRef<number | null>(null)
  const e2eBootstrapDoneRef = useRef(false)
  const interruptedToastShownRef = useRef<Record<string, boolean>>({})
  // Route switch safety: use this to ignore late async responses from old sessions.
  const currentSessionIdRef = useRef<string>('')

  // Dialog & Drawer States
  const [statusDialogOpen, setStatusDialogOpen] = useState(false)
  const [selfCheckDrawerOpen, setSelfCheckDrawerOpen] = useState(false)
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false)
  const [clearAllDialogOpen, setClearAllDialogOpen] = useState(false)
  const [clearingAll, setClearingAll] = useState(false)

  // P0: Health Warning State
  const [healthWarning, setHealthWarning] = useState<{
    show: boolean
    issues: string[]
    hints: string[]
  } | null>(null)

  // Model Selection States
  const [mode, setMode] = useState<'local' | 'cloud'>('local')
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')  // ✅ Start with empty, will be set when models load
  const [conversationMode, setConversationMode] = useState<ConversationMode>(DEFAULT_CONVERSATION_MODE)
  const [executionPhase, setExecutionPhase] = useState<ExecutionPhase>(DEFAULT_EXECUTION_PHASE)
  const [phaseConfirmOpen, setPhaseConfirmOpen] = useState(false)
  const [pendingPhase, setPendingPhase] = useState<ExecutionPhase | null>(null)
  const { confirm: confirmDialog, dialog: promptDialog } = usePromptDialog()

  // Computed values
  const sessionCountLabel = `${sessions.length} ${t(K.page.chat.conversationCount)}`

  // ===================================
  // P1: Optimization - Flush buffered streaming message
  // ===================================
  const flushStreamingMessage = useCallback(() => {
    rafRef.current = null
    setStreamingMessage(bufferRef.current)
  }, [])

  const clearReplyWaitTimers = useCallback(() => {
    if (slowReplyTimerRef.current !== null) {
      clearTimeout(slowReplyTimerRef.current)
      slowReplyTimerRef.current = null
    }
    if (verySlowReplyTimerRef.current !== null) {
      clearTimeout(verySlowReplyTimerRef.current)
      verySlowReplyTimerRef.current = null
    }
  }, [])

  const startReplyWaitTimers = useCallback(() => {
    clearReplyWaitTimers()
    setReplyWaitStage('pending')
    slowReplyTimerRef.current = window.setTimeout(() => {
      setReplyWaitStage('slow')
    }, 3000)
    verySlowReplyTimerRef.current = window.setTimeout(() => {
      setReplyWaitStage('verySlow')
    }, 12000)
  }, [clearReplyWaitTimers])

  const clearAwaitingReply = useCallback(() => {
    setAwaitingReply(false)
    setReplyWaitStage('pending')
    clearReplyWaitTimers()
    pendingReplyStartedAtRef.current = null
  }, [clearReplyWaitTimers])

  // ===================================
  // P0-1: WebSocket Integration
  // ===================================
  const {
    isConnected,
    isConnecting,
    error: wsError,
    sendMessage: wsSendMessage,
    sendControlStop: wsSendControlStop,
    sendEditResend: wsSendEditResend,
    connect
  } = useWebSocket({
    sessionId: currentSessionId,
    onMessage: useCallback((msg: { type: string; content?: string; delta?: string; message_id?: string; messageId?: string; metadata?: Record<string, unknown>; run_id?: string; runId?: string; seq?: number; command_id?: string; commandId?: string; status?: string; reason?: string; target_message_id?: string; new_message_id?: string; by_command_id?: string; result_type?: string; location?: string; provider?: string; payload?: Record<string, unknown> }) => {
      // console.log('[ChatPage] 📨 WebSocket message received:', msg)

      // ✅ Backend returns message_id (snake_case), normalize to messageId
      const messageId = msg.message_id || msg.messageId
      const runId = msg.run_id || msg.runId
      const chunk = msg.delta ?? msg.content ?? ''

      if (msg.type === 'message.start') {
        setEditSubmitting(false)
        if (runId) {
          setCurrentRunId(runId)
          delete pendingToolResultsRef.current[runId]
        }
        // console.log('[ChatPage] 🎬 Stream start')
        // ✅ Stream start - initialize streaming state
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setStreamingMessage('')
        setIsStreaming(true)
        if (pendingReplyStartedAtRef.current === null) {
          pendingReplyStartedAtRef.current = Date.now()
        }
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
      } else if (msg.type === 'message.delta') {
        if (currentRunId && runId && runId !== currentRunId) {
          return
        }
        // console.log('[ChatPage] 📝 Stream delta, content length:', msg.content.length)
        // ✅ P1: Optimization - Accumulate to buffer and schedule RAF flush
        clearAwaitingReply()
        streamingMessageRef.current += chunk
        bufferRef.current = streamingMessageRef.current

        // Schedule RAF flush if not already scheduled
        if (rafRef.current === null) {
          rafRef.current = requestAnimationFrame(flushStreamingMessage)
        }
        setIsStreaming(true)
      } else if (msg.type === 'message.end') {
        if (currentRunId && runId && runId !== currentRunId) {
          return
        }
        // ✅ Stream complete - finalize message
        // Use ref to get latest streaming content, fallback to msg.content if no streaming happened
        const finalContent = streamingMessageRef.current || msg.content || ''
        // console.log('[ChatPage] 🏁 Stream end, final content length:', finalContent.length)
        // console.log('[ChatPage] 🏁 Final content:', finalContent)
        // console.log('[ChatPage] 💾 Saving message to state...')

        const toolResult = runId ? pendingToolResultsRef.current[runId] : undefined
        const cleanToolResult = toolResult
          ? Object.fromEntries(Object.entries(toolResult).filter(([k]) => k !== '__seq'))
          : undefined
        if (runId) {
          delete pendingToolResultsRef.current[runId]
        }

        setMessages((prev) => {
          const newMessage = {
            id: messageId || `msg-${Date.now()}`,
            role: 'assistant' as const,
            content: finalContent,
            timestamp: new Date().toISOString(),
            metadata: { ...(msg.metadata || {}), ...(cleanToolResult || {}), run_id: runId },
          }
          // console.log('[ChatPage] 💾 Previous messages count:', prev.length)
          // console.log('[ChatPage] 💾 New message:', newMessage)
          const newMessages = [...prev, newMessage]
          // console.log('[ChatPage] 💾 Total messages after save:', newMessages.length)
          return newMessages
        })

        // 🔧 更新当前 session 的 lastMessage（非紧急更新 - 使用 startTransition）
        startTransition(() => {
          setSessions(prevSessions => {
            const preview = finalContent.substring(0, 50).replace(/\n/g, ' ')
            return prevSessions.map(s =>
              s.id === currentSessionId
                ? { ...s, lastMessage: preview }
                : s
            )
          })
        })

        streamingMessageRef.current = ''
        bufferRef.current = ''
        setStreamingMessage('')
        setIsStreaming(false)
        setCurrentRunId('')
        clearAwaitingReply()
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
      } else if (msg.type === 'message.tool_result') {
        if (runId) {
          const nextSeq = Number(msg.seq || 0)
          const currentSeq = Number((pendingToolResultsRef.current[runId] as any)?.__seq || 0)
          if (nextSeq < currentSeq) {
            return
          }
          pendingToolResultsRef.current[runId] = {
            result_type: msg.result_type,
            location: msg.location,
            provider: msg.provider,
            payload: msg.payload,
            __seq: nextSeq,
          }
        }
      } else if (msg.type === 'message.cancelled') {
        setEditSubmitting(false)
        if (currentRunId && runId && runId !== currentRunId) {
          return
        }
        setIsStreaming(false)
        setStreamingMessage('')
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setCurrentRunId('')
        if (runId) {
          delete pendingToolResultsRef.current[runId]
        }
        clearAwaitingReply()
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
        toast.info(t(K.page.chat.generationStopped))
      } else if (msg.type === 'control.ack') {
        if (msg.status === 'rejected') {
          setEditSubmitting(false)
          toast.warning(msg.reason || 'Control command rejected')
        }
      } else if (msg.type === 'resume.status') {
        const status = String((msg as any).status || '')
        if (status === 'required_retry') {
          setIsStreaming(false)
          setCurrentRunId('')
          clearAwaitingReply()
          void refreshSessionState()
          toast.warning(t(K.page.chat.replyVerySlow))
        }
      } else if (msg.type === 'message.superseded') {
        const targetId = msg.target_message_id || ''
        const newMessageId = msg.new_message_id || `msg-${Date.now()}`
        const cmd = msg.by_command_id ? pendingEditCommandsRef.current[msg.by_command_id] : null
        const newContent = cmd?.newContent || ''

        setMessages((prev) => {
          const marked = prev.map((m) => (
            m.id === targetId
              ? { ...m, metadata: { ...(m.metadata || {}), status: 'superseded' } }
              : m
          ))
          if (!newContent) return marked
          return [
            ...marked,
            {
              id: newMessageId,
              role: 'user',
              content: newContent,
              timestamp: new Date().toISOString(),
              metadata: {
                status: 'active',
                revision: Number((msg as any).revision || 1),
                parent_message_id: targetId,
              },
            },
          ]
        })
        if (msg.by_command_id) {
          delete pendingEditCommandsRef.current[msg.by_command_id]
        }
      } else if (msg.type === 'run.started') {
        setEditSubmitting(false)
        if (runId) {
          setCurrentRunId(runId)
        }
      } else if (msg.type === 'message.error' || msg.type === 'error') {
        setEditSubmitting(false)
        console.error('[ChatPage] ❌ Message error:', msg.content)
        // ✅ Error message
        toast.error(msg.content || t(K.page.chat.connectionError))
        clearAwaitingReply()
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setIsStreaming(false)
        setStreamingMessage('')
        setCurrentRunId('')
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
      } else if (msg.type === 'pong') {
        // ✅ Heartbeat response - ignore
        console.debug('[ChatPage] 💓 Received pong')
      } else {
        // ✅ Unknown message types - log but don't show error
        console.debug(`[ChatPage] ❓ Unhandled message type: ${msg.type}`, msg)
      }
    }, [t, currentSessionId, flushStreamingMessage, clearAwaitingReply, currentRunId, refreshSessionState]),
    onConnect: useCallback(() => {
      void refreshSessionState()
    }, [refreshSessionState]),
    onDisconnect: useCallback(() => {
      // console.log('WebSocket disconnected')
    }, []),
    onError: useCallback(() => {
      toast.error(t(K.page.chat.connectionError))
    }, [t]),
    autoConnect: false, // Don't auto-connect until we have a valid session ID
  })

  // Show WebSocket error as toast
  useEffect(() => {
    if (wsError) {
      toast.error(wsError)
      clearAwaitingReply()
    }
  }, [wsError, clearAwaitingReply])

  // Connect WebSocket when currentSessionId is available
  useEffect(() => {
    if (currentSessionId) {
      // console.log('[ChatPage] Connecting WebSocket for session:', currentSessionId)
      connect()
    }
    // ✅ 移除 connect 依赖，避免频繁重连
    // connect 函数会在 sessionId 改变时重新创建，但我们只想在 sessionId 改变时连接
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId])

  useEffect(() => {
    return () => {
      clearReplyWaitTimers()
    }
  }, [clearReplyWaitTimers])

  // ===================================
  // P0: WebSocket Lifecycle Enhancement
  // ===================================
  // Handle page visibility changes and bfcache restoration
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && currentSessionId && !isConnected) {
        // console.log('[ChatPage] Page visible, reconnecting WebSocket')
        connect()
      }
    }

    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted && currentSessionId) {
        // console.log('[ChatPage] Page restored from bfcache, reconnecting WebSocket')
        connect()
      }
    }

    const handleFocus = () => {
      if (currentSessionId && !isConnected) {
        // console.log('[ChatPage] Window focused, reconnecting WebSocket')
        connect()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('pageshow', handlePageShow)
    window.addEventListener('focus', handleFocus)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('pageshow', handlePageShow)
      window.removeEventListener('focus', handleFocus)
    }
    // ✅ 移除 connect 依赖，避免频繁重新绑定事件监听
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId, isConnected])

  // ===================================
  // P0-2: Load All Sessions
  // ===================================
  const loadSessions = useCallback(async () => {
    // console.log('[ChatPage] 📂 Loading sessions...')
    setSessionsLoading(true)
    try {
      // Backend returns array directly: Session[]
      const sessions = await systemService.listSessionsApiSessionsGet()
      // console.log('[ChatPage] 📂 API returned sessions count:', sessions.length)

      // 🚀 为每个 session 并发加载最后一条消息
      const sessionsWithLastMessage = await Promise.all(
        sessions.map(async (session: any) => {
          let lastMessage = session.last_message || session.lastMessage || ''

          // 如果后端没有返回 lastMessage，尝试加载消息列表获取最后一条
          if (!lastMessage) {
            try {
              const response = await systemService.listMessagesApiSessionsSessionIdMessagesGet(session.id)
              const messagesArray = Array.isArray(response) ? response : (response?.messages || [])

              if (messagesArray.length > 0) {
                const lastMsg = messagesArray[messagesArray.length - 1]
                // 截取前50个字符作为预览，移除换行符
                lastMessage = (lastMsg.content || '').substring(0, 50).replace(/\n/g, ' ')
              }
            } catch (err) {
              console.warn(`[ChatPage] ⚠️ Failed to load last message for session ${session.id}:`, err)
              // 忽略单个 session 的错误，继续处理其他 sessions
            }
          }

          return {
            id: session.id,
            title: session.title || 'Untitled Chat',
            lastMessage,
            timestamp: session.created_at,
            unreadCount: session.unread_count || session.unreadCount || 0,
            metadata: session.metadata,
          } as ChatSession
        })
      )

      // console.log('[ChatPage] 📂 Loaded sessions with last messages:', sessionsWithLastMessage)
      // console.log('[ChatPage] 🔍 Sample session data:', sessions[0])
      // ✅ P1 优化：loadSessions 后的状态更新使用 startTransition（非紧急更新）
      startTransition(() => {
        setSessions(sessionsWithLastMessage)
      })

      // Set first session as current if none selected
      if (!currentSessionId && sessionsWithLastMessage.length > 0) {
        // console.log('[ChatPage] 📂 No current session, setting first session as current:', sessionsWithLastMessage[0].id)
        setCurrentSessionId(sessionsWithLastMessage[0].id)
      } else {
        // console.log('[ChatPage] 📂 Current session already set:', currentSessionId)
      }
    } catch (error) {
      console.error('[ChatPage] ❌ Failed to load sessions:', error)
      // Don't show toast on initial load failure - just show empty state
    } finally {
      setSessionsLoading(false)
    }
  }, [currentSessionId])

  const persistSessionMetadata = useCallback(async (updates: Record<string, unknown>) => {
    if (!currentSessionId) return

    const currentMetadata = (currentSession?.metadata || {}) as Record<string, unknown>
    const mergedMetadata = {
      ...currentMetadata,
      ...updates,
    }
    const nextMode = normalizeConversationMode(mergedMetadata.conversation_mode)
    const nextPhase = deriveExecutionPhaseByMode(
      nextMode,
      normalizeExecutionPhase(mergedMetadata.execution_phase)
    )
    const nextMetadata = {
      ...mergedMetadata,
      conversation_mode: nextMode,
      execution_phase: nextPhase,
    }

    try {
      await httpClient.put(`/api/sessions/${currentSessionId}`, { metadata: nextMetadata })
      setSessions((prev) =>
        prev.map((session) =>
          session.id === currentSessionId
            ? { ...session, metadata: nextMetadata }
            : session
        )
      )
    } catch (error) {
      console.error('[ChatPage] Failed to persist session metadata:', error)
      toast.error('Failed to save conversation settings')
    }
  }, [currentSessionId, currentSession?.metadata])

  // ✅ Initialize CSRF token and load sessions on mount
  useEffect(() => {
    const initializeApp = async () => {
      // First, ensure CSRF token is available
      try {
        await systemService.listSessionsApiSessionsGet({ limit: 1, offset: 0 })
        // console.log('[ChatPage] ✅ CSRF token initialized')
      } catch (err) {
        console.error('[ChatPage] Failed to initialize CSRF token:', err)
      }

      // Then load sessions
      loadSessions()
    }

    initializeApp()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run once on mount

  // ===================================
  // P0-3: Session Creation API
  // ===================================
  const handleNewConversation = useCallback(async (presetId?: ChatPresetId) => {
    setLoading(true)
    try {
      const preset = getChatPreset(presetId ?? null)
      const metadata = preset
        ? {
            preset_id: preset.id,
            conversation_mode: DEFAULT_CONVERSATION_MODE,
            execution_phase: DEFAULT_EXECUTION_PHASE,
            preset_payload: preset.systemPrompt
              ? {
                  system_prompt: preset.systemPrompt,
                  tone: preset.tone,
                  scope: preset.scope,
                  inherit_project: preset.inheritProject,
                }
              : undefined,
          }
        : {
            conversation_mode: DEFAULT_CONVERSATION_MODE,
            execution_phase: DEFAULT_EXECUTION_PHASE,
          }

      // Backend returns SessionResponse directly, not wrapped in { session: ... }
      const response = await systemService.createSessionApiSessionsPost({
        title: `New Chat - ${new Date().toLocaleString()}`,
        metadata,
      })

      // Handle both response formats for backward compatibility
      const sessionData = 'session' in response ? response.session : response

      const newSession: ChatSession & { metadata?: Record<string, any> } = {
        id: sessionData.id,
        title: sessionData.title || 'New Chat',
        lastMessage: '',
        timestamp: sessionData.created_at,
        unreadCount: 0,
        metadata,
      }

      setSessions((prev) => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      setConversationMode(DEFAULT_CONVERSATION_MODE)
      setExecutionPhase(DEFAULT_EXECUTION_PHASE)
      setMessages([])
      toast.success(t(K.page.chat.newConversationSuccess))
    } catch (error) {
      console.error('Failed to create session:', error)
      if (isE2eBootstrap) {
        const e2eSession: ChatSession & { metadata?: Record<string, any> } = {
          id: `e2e-session-${Date.now()}`,
          title: 'E2E Chat Session',
          lastMessage: '',
          timestamp: new Date().toISOString(),
          unreadCount: 0,
          metadata: {
            conversation_mode: DEFAULT_CONVERSATION_MODE,
            execution_phase: DEFAULT_EXECUTION_PHASE,
            source: 'e2e_local_fallback',
          },
        }
        setSessions((prev) => [e2eSession, ...prev])
        setCurrentSessionId(e2eSession.id)
        setConversationMode(DEFAULT_CONVERSATION_MODE)
        setExecutionPhase(DEFAULT_EXECUTION_PHASE)
        setMessages([])
        console.warn('[ChatPage] E2E fallback session created due create-session API failure')
      } else {
        toast.error(t(K.page.chat.newConversationFailed))
      }
    } finally {
      setLoading(false)
    }
  }, [isE2eBootstrap, t])

  useEffect(() => {
    const metadata = (currentSession?.metadata || {}) as Record<string, unknown>
    const nextMode = normalizeConversationMode(metadata.conversation_mode)
    const nextPhase = deriveExecutionPhaseByMode(
      nextMode,
      normalizeExecutionPhase(metadata.execution_phase)
    )

    setConversationMode(nextMode)
    setExecutionPhase(nextPhase)
  }, [currentSession?.id, currentSession?.metadata])

  useEffect(() => {
    const presetId = (location.state as { presetId?: ChatPresetId } | null)?.presetId
    if (!presetId) return
    handleNewConversation(presetId).finally(() => {
      navigate('/chat', { replace: true, state: null })
    })
  }, [handleNewConversation, location.state, navigate])

  // Allow deep-link style navigation into a specific session (used by productized flows like AWS Ops).
  useEffect(() => {
    const sessionId = (location.state as { sessionId?: string } | null)?.sessionId
    if (!sessionId) return
    setCurrentSessionId(String(sessionId))
    navigate('/chat', { replace: true, state: null })
    window.setTimeout(() => {
      const input = document.querySelector('[data-testid="chat-input"]') as HTMLElement | null
      input?.focus()
    }, 0)
  }, [location.state, navigate])

  useEffect(() => {
    const query = new URLSearchParams(location.search)
    const shouldCreate = query.get('new') === '1'
    if (!isE2eBootstrap || e2eBootstrapDoneRef.current || sessionsLoading) return

    const focusInput = () => {
      window.setTimeout(() => {
        const input = document.querySelector('[data-testid="chat-input"]') as HTMLElement | null
        input?.focus()
      }, 0)
    }

    if (currentSessionId) {
      e2eBootstrapDoneRef.current = true
      focusInput()
      return
    }

    if (shouldCreate) {
      e2eBootstrapDoneRef.current = true
      void handleNewConversation().finally(() => {
        focusInput()
      })
      return
    }

    if (sessions.length > 0) {
      e2eBootstrapDoneRef.current = true
      setCurrentSessionId(sessions[0].id)
      focusInput()
    }
  }, [location.search, sessionsLoading, currentSessionId, sessions, handleNewConversation])

  // ===================================
  // P0-4: Single Session Deletion API
  // ===================================
  const handleSessionClear = useCallback(
    async (sessionId: string) => {
      try {
        await systemService.deleteSessionApiSessionsSessionIdDelete(sessionId)
        setSessions((prev) => prev.filter((s) => s.id !== sessionId))

        // If deleted session was current, switch to another session
        if (currentSessionId === sessionId) {
          const remainingSessions = sessions.filter((s) => s.id !== sessionId)
          if (remainingSessions.length > 0) {
            setCurrentSessionId(remainingSessions[0].id)
          } else {
            setCurrentSessionId('')
            setMessages([])
          }
        }

        toast.success(t(K.page.chat.clearAllSuccess)) // Reuse existing key
      } catch (error) {
        console.error('Failed to delete session:', error)
        toast.error(t(K.page.chat.clearAllFailed)) // Reuse existing key
      }
    },
    [currentSessionId, sessions, t]
  )

  // ===================================
  // P0-5: Session Deletion API (Clear All)
  // ===================================
  const handleClearAll = useCallback(async () => {
    setClearingAll(true)
    try {
      await systemService.deleteAllSessionsApiSessionsDelete()
      setSessions([])
      setMessages([])
      setCurrentSessionId('')
      toast.success(t(K.page.chat.clearAllSuccess))
    } catch (error) {
      console.error('Failed to clear all sessions:', error)
      toast.error(t(K.page.chat.clearAllFailed))
    } finally {
      setClearingAll(false)
      setClearAllDialogOpen(false)
    }
  }, [t])

  // ===================================
  // P0-2: Load messages for a session (extracted logic)
  // ===================================
  const loadMessagesForSession = useCallback(async (sessionId: string) => {
    // console.log('[ChatPage] 🔄 Loading messages for session:', sessionId)
    setMessagesLoading(true)
    setMessages([])  // Clear old messages

    try {
      const sessionIdForRequest = sessionId
      // P0: Load message history from API
      const response = await systemService.listMessagesApiSessionsSessionIdMessagesGet(sessionIdForRequest)
      // console.log('[ChatPage] 📥 API Response:', response)
      // console.log('[ChatPage] 📥 Response.messages:', response?.messages)

      // ✅ Backend returns array directly, not {messages: [...]}
      const messagesArray = Array.isArray(response) ? response : (response?.messages || [])
      // console.log('[ChatPage] 📦 Messages array length:', messagesArray.length)
      // console.log('[ChatPage] 📦 Messages array:', messagesArray)

      const loadedMessages: ChatMessageType[] = messagesArray.map((msg: any) => ({
        id: msg.id || `msg-${Date.now()}-${Math.random()}`,
        role: msg.role || 'assistant',
        content: msg.content || '',
        timestamp: msg.timestamp || new Date().toISOString(),
        metadata: msg.metadata,
      })).filter((msg: ChatMessageType) => msg.role !== 'tool')
      // console.log('[ChatPage] ✅ Loaded messages count:', loadedMessages.length)
      // console.log('[ChatPage] ✅ Loaded messages:', loadedMessages)

      // 🔍 Debug: 查看包含 HTML 的消息内容
      loadedMessages.forEach((msg) => {
        if (msg.content.includes('DOCTYPE') || msg.content.includes('&lt;')) {
          // console.log(`[ChatPage] 🔍 Message with HTML content:`, {
          //   id: msg.id,
          //   role: msg.role,
          //   contentPreview: msg.content.substring(0, 200),
          //   hasCodeBlock: msg.content.includes('```'),
          //   fullContent: msg.content,
          // })
        }
      })

      // Route switch safety: ignore late responses for a session that's no longer active.
      if (currentSessionIdRef.current !== sessionIdForRequest) return

      setMessages(loadedMessages)

      // 🔧 更新 session 的 lastMessage 预览（非紧急更新 - 使用 startTransition）
      if (loadedMessages.length > 0) {
        const lastMsg = loadedMessages[loadedMessages.length - 1]
        // 截取前50个字符作为预览
        const preview = lastMsg.content.substring(0, 50).replace(/\n/g, ' ')

        startTransition(() => {
          setSessions(prevSessions =>
            prevSessions.map(s =>
              s.id === sessionId
                ? { ...s, lastMessage: preview }
                : s
            )
          )
        })
        // console.log('[ChatPage] 🔧 Updated lastMessage preview for session:', sessionId)
      }
    } catch (error) {
      console.error('[ChatPage] ❌ Failed to load messages for session:', error)
      // Avoid spurious toasts/state changes if the user already switched sessions.
      if (currentSessionIdRef.current === sessionId) {
        toast.error('Failed to load conversation history')
        setMessages([])  // Clear on error
      }
    } finally {
      setMessagesLoading(false)
    }
  }, [])

  const reconcilePendingReplyState = useCallback(async () => {
    if (!currentSessionId || !awaitingReply || isStreaming) return

    const startedAt = pendingReplyStartedAtRef.current
    if (startedAt == null) return

    try {
      const response = await systemService.listMessagesApiSessionsSessionIdMessagesGet(currentSessionId)
      const messagesArray = Array.isArray(response) ? response : ((response as any)?.messages || [])
      const loadedMessages: ChatMessageType[] = messagesArray.map((msg: any) => ({
        id: msg.id || `msg-${Date.now()}-${Math.random()}`,
        role: msg.role || 'assistant',
        content: msg.content || '',
        timestamp: msg.timestamp || new Date().toISOString(),
        metadata: msg.metadata,
      })).filter((msg: ChatMessageType) => msg.role !== 'tool')

      const isCompletionForPendingRun = loadedMessages.some((m) => {
        if (m.role !== 'assistant') return false
        if (currentRunId) {
          const runId = (m.metadata as any)?.run_id
          if (runId && runId === currentRunId) return true
        }
        const ts = Date.parse(m.timestamp || '')
        return Number.isFinite(ts) && ts >= startedAt
      })

      if (isCompletionForPendingRun) {
        setMessages(loadedMessages)
        setStreamingMessage('')
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setIsStreaming(false)
        setCurrentRunId('')
        clearAwaitingReply()
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
        return
      }

      if (Date.now() - startedAt >= REPLY_RECOVERY_TIMEOUT_MS) {
        setStreamingMessage('')
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setIsStreaming(false)
        setCurrentRunId('')
        clearAwaitingReply()
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
        toast.warning(t(K.page.chat.replyVerySlow))
      }
    } catch {
      // Reconcile is best-effort and should never break chat UI
    }
  }, [awaitingReply, clearAwaitingReply, currentRunId, currentSessionId, isStreaming, t])

  // ===================================
  // P0-2: Session Selection Handler
  // ===================================
  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      clearAwaitingReply()
      setCurrentRunId('')
      pendingEditCommandsRef.current = {}
      setCurrentSessionId(sessionId)
      // Messages will be loaded by useEffect watching currentSessionId
    },
    [clearAwaitingReply]
  )

  // ===================================
  // Auto-load messages when currentSessionId changes
  // ===================================
  useEffect(() => {
    // console.log('[ChatPage] 🔄 useEffect triggered, currentSessionId:', currentSessionId)
    if (currentSessionId) {
      // console.log('[ChatPage] 🔄 Calling loadMessagesForSession...')
      loadMessagesForSession(currentSessionId)
    } else {
      // console.log('[ChatPage] 🔄 No currentSessionId, skipping load')
    }
  }, [currentSessionId, loadMessagesForSession])

  useEffect(() => {
    const currentState = String(sessionState?.state || '')
    if (!currentSessionId || currentState !== 'interrupted') return
    if (interruptedToastShownRef.current[currentSessionId]) return
    interruptedToastShownRef.current[currentSessionId] = true
    toast.warning(t(K.page.chat.replyVerySlow))
  }, [sessionState?.state, currentSessionId, t])

  const effectiveIsStreaming = isStreaming || sessionState?.state === 'streaming'
  const sessionStateBanner = sessionState
    ? (
      <Box sx={{ px: 1, pt: 1 }}>
        <Chip
          data-testid="chat-session-state"
          label={`session: ${sessionState.state}`}
          color={sessionState.state === 'interrupted' ? 'warning' : 'default'}
          size={'small' as const}
          variant={'outlined' as const}
        />
      </Box>
      )
    : undefined

  useEffect(() => {
    if (!awaitingReply || isStreaming || !currentSessionId) {
      return
    }

    const timer = window.setInterval(() => {
      void reconcilePendingReplyState()
    }, 3000)

    // Run once immediately to recover quickly after reconnect/event loss.
    void reconcilePendingReplyState()

    return () => {
      clearInterval(timer)
    }
  }, [awaitingReply, isStreaming, currentSessionId, reconcilePendingReplyState])

  // ===================================
  // Gate-3: Session presence heartbeat (for chat injection guard)
  // ===================================
  useEffect(() => {
    if (!currentSessionId) return
    let cancelled = false
    const sessionIdForEffect = currentSessionId

    const touch = async () => {
      try {
        await httpClient.post(`/api/sessions/${sessionIdForEffect}/presence/touch`, {})
      } catch {
        // best-effort
      }
    }

    void touch()
    const timer = window.setInterval(() => {
      if (cancelled) return
      void touch()
    }, 15_000)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [currentSessionId])

  // ===================================
  // Gate-3: Background message refresh (captures injected system messages)
  // ===================================
  const lastMessagesSignatureRef = useRef<string>('')
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId
  }, [currentSessionId])
  useEffect(() => {
    if (!currentSessionId) return
    if (effectiveIsStreaming) return

    let cancelled = false
    const sessionIdForEffect = currentSessionId

    const refresh = async () => {
      try {
        const response = await systemService.listMessagesApiSessionsSessionIdMessagesGet(sessionIdForEffect)
        const messagesArray = Array.isArray(response) ? response : ((response as any)?.messages || [])
        const loadedMessages: ChatMessageType[] = messagesArray.map((msg: any) => ({
          id: msg.id || `msg-${Date.now()}-${Math.random()}`,
          role: msg.role || 'assistant',
          content: msg.content || '',
          timestamp: msg.timestamp || new Date().toISOString(),
          metadata: msg.metadata,
        })).filter((msg: ChatMessageType) => msg.role !== 'tool')

        // Route switch safety: ignore late responses for a session that's no longer active.
        if (cancelled || currentSessionIdRef.current !== sessionIdForEffect) return

        const sig = `${loadedMessages.length}:${loadedMessages[loadedMessages.length - 1]?.id || ''}`
        if (sig !== lastMessagesSignatureRef.current) {
          lastMessagesSignatureRef.current = sig
          setMessages(loadedMessages)
        }
      } catch {
        // best-effort
      }
    }

    void refresh()
    const timer = window.setInterval(() => {
      if (cancelled) return
      void refresh()
    }, 2500)

    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [currentSessionId, effectiveIsStreaming])

  // ===================================
  // P0-7: Session Search Handler
  // ===================================
  const handleSearchSessions = useCallback((keyword: string) => {
    // Client-side search - filter sessions by title
    if (!keyword.trim()) {
      // Reset to all sessions
      loadSessions()
      return
    }

    // ✅ P1 优化：搜索过滤是非紧急更新，使用 startTransition
    startTransition(() => {
      setSessions((prev) =>
        prev.filter((session) =>
          session.title.toLowerCase().includes(keyword.toLowerCase())
        )
      )
    })
  }, [loadSessions])

  // ===================================
  // Message Sending Handler (Optimistic Update Pattern)
  // ===================================
  const handleSendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || !isConnected) {
        if (!isConnected) {
          toast.error(t(K.page.chat.connectionError))
        }
        return false
      }
      if (!currentSessionId) {
        toast.error(t(K.page.chat.connectionError))
        return false
      }
      if (isConnecting) {
        toast.warning(t(K.page.chat.connectionLost))
        return
      }
      if (isStreaming || awaitingReply) {
        toast.warning(t(K.page.chat.waitForCurrentReply))
        return false
      }

      // ✅ Optimistic Update: Add user message to UI immediately (不等待任何 API 响应)
      const userMessage: ChatMessageType = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
      }
      // console.log('[ChatPage] 💬 User message created:', userMessage)

      setMessages((prev) => {
        // console.log('[ChatPage] 💬 Previous messages count:', prev.length)
        const newMessages = [...prev, userMessage]
        // console.log('[ChatPage] 💬 Total messages after user message:', newMessages.length)
        return newMessages
      })

      // 🔧 更新当前 session 的 lastMessage（用户消息 - 非紧急更新，使用 startTransition）
      startTransition(() => {
        setSessions(prevSessions => {
          const preview = text.substring(0, 50).replace(/\n/g, ' ')
          return prevSessions.map(s =>
            s.id === currentSessionId
              ? { ...s, lastMessage: preview }
              : s
          )
        })
      })

      // ✅ 后台异步检查健康状态（不阻塞消息发送）
      systemService.daemonStatusApiDaemonStatusGet()
        .then((health: any) => {
          const evaluation = evaluateDaemonHealth(health)
          if (!evaluation.healthy) {
            // 仅在健康检查失败时显示警告（不阻止消息发送）
            setHealthWarning({
              show: true,
              issues: evaluation.issues.length > 0 ? evaluation.issues : ['Daemon not healthy'],
              hints: evaluation.hints
            })
          }
        })
        .catch((error: any) => {
          console.warn('[ChatPage] Background health check failed:', error)
          // 静默失败，不影响用户体验
        })

      // Send via WebSocket with metadata
      const effectiveExecutionPhase = deriveExecutionPhaseByMode(conversationMode, executionPhase)
      const metadata = {
        model_type: mode,
        provider,
        model,
        conversation_mode: conversationMode,
        execution_phase: effectiveExecutionPhase,
      }
      // console.log('[ChatPage] 📤 Sending message via WebSocket:', { text, metadata })

      // ✅ 错误处理：WebSocket 发送失败时提示
      try {
        pendingReplyStartedAtRef.current = Date.now()
        setAwaitingReply(true)
        startReplyWaitTimers()
        const sent = wsSendMessage(text, metadata)
        if (!sent) {
          clearAwaitingReply()
          toast.error(t(K.page.chat.connectionError))
          return false
        }

        // 🎯 产品级功能：发送成功后清除草稿和输入框
        clearDraft()
        setInputValue('')
        return true
      } catch (error) {
        console.error('[ChatPage] Failed to send message via WebSocket:', error)
        clearAwaitingReply()
        toast.error(t(K.page.chat.connectionError))
        return false
      }
    },
    [isConnected, isConnecting, isStreaming, awaitingReply, wsSendMessage, mode, provider, model, conversationMode, executionPhase, currentSessionId, t, clearDraft, startReplyWaitTimers, clearAwaitingReply]
  )

  const awaitingReplyMessage = useMemo(() => {
    if (replyWaitStage === 'verySlow') return t(K.page.chat.replyVerySlow)
    if (replyWaitStage === 'slow') return t(K.page.chat.replySlow)
    return t(K.page.chat.replyPending)
  }, [replyWaitStage, t])

  const generateCommandId = useCallback((prefix: string) => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return `${prefix}_${crypto.randomUUID()}`
    }
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
  }, [])

  const handleStopStreaming = useCallback(() => {
    if (!currentRunId) return
    const commandId = generateCommandId('c_stop')
    const sent = wsSendControlStop(currentRunId, commandId, 'user_clicked_stop')
    if (!sent) {
      toast.error(t(K.page.chat.stopCommandFailed))
    }
  }, [currentRunId, generateCommandId, wsSendControlStop])

  const handleEditMessage = useCallback((message: ChatMessageType) => {
    if (message.role !== 'user') return
    if (!message.id || message.id.startsWith('msg-')) {
      toast.warning(t(K.page.chat.editNotPersisted))
      return
    }
    setEditingMessage(message)
    setEditingText(message.content)
    setEditDialogOpen(true)
  }, [])

  const handleConfirmEditResend = useCallback(() => {
    if (!editingMessage) return
    const nextContent = editingText.trim()
    if (!nextContent) {
      toast.warning(t(K.page.chat.editEmpty))
      return
    }
    const commandId = generateCommandId('c_edit')
    const effectiveExecutionPhase = deriveExecutionPhaseByMode(conversationMode, executionPhase)
    const sent = wsSendEditResend(
      editingMessage.id,
      nextContent,
      commandId,
      'typo_fix',
      {
        model_type: mode,
        provider,
        model,
        conversation_mode: conversationMode,
        execution_phase: effectiveExecutionPhase,
      }
    )
    if (!sent) {
      toast.error(t(K.page.chat.editCommandFailed))
      return
    }

    pendingEditCommandsRef.current[commandId] = {
      targetId: editingMessage.id,
      newContent: nextContent,
    }
    setEditSubmitting(true)
    setEditDialogOpen(false)
    setEditingMessage(null)
    setEditingText('')
    pendingReplyStartedAtRef.current = Date.now()
    setAwaitingReply(true)
    startReplyWaitTimers()
  }, [editingMessage, editingText, generateCommandId, wsSendEditResend, mode, provider, model, conversationMode, executionPhase, startReplyWaitTimers, t])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: presetTag ? (
      <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
        <Box component="span">{t(K.page.chat.title)}</Box>
        <Box
          component="span"
          sx={{
            fontSize: '0.75rem',
            fontWeight: 600,
            px: 1,
            py: 0.25,
            borderRadius: 1,
            bgcolor: 'action.hover',
            color: 'text.secondary',
          }}
        >
          {presetTag}
        </Box>
      </Box>
    ) : (
      t(K.page.chat.title)
    ),
    subtitle: t(K.page.chat.subtitle),
  })

  usePageActions([
    {
      key: 'running',
      label: t(K.page.chat.running),
      icon: <PlayArrowIcon />,
      variant: 'outlined',
      onClick: () => {
        setStatusDialogOpen(true)
      },
    },
    {
      key: 'selfcheck',
      label: t(K.page.chat.selfCheck),
      icon: <CheckCircleIcon />,
      variant: 'outlined',
      onClick: () => {
        setSelfCheckDrawerOpen(true)
      },
    },
    {
      key: 'config',
      label: t(K.page.chat.config),
      icon: <SettingsIcon />,
      variant: 'outlined',
      onClick: () => {
        setConfigDrawerOpen(true)
      },
    },
    {
      key: 'new',
      label: t(K.page.chat.newConversation),
      variant: 'contained',
      onClick: handleNewConversation,
    },
  ])

  // ===================================
  // P0-8: Load Providers & Models from API (v1 Three-Layer Logic)
  // ===================================
  const [providers, setProviders] = useState<string[]>([])
  const [models, setModels] = useState<string[]>([])

  // Helper: Load models for specific provider
  const loadModelsForProvider = useCallback(async (targetProvider: string) => {
    try {
      const modelsResp = await providersApi.getProviderModels(targetProvider)
      const loadedModels = Array.isArray(modelsResp?.models)
        ? modelsResp.models.map((m: any) => m.id || m.name || m.label).filter(Boolean)
        : []
      setModels(loadedModels)
      // console.log(`[ChatPage] Loaded models for ${targetProvider}:`, loadedModels.length)

      // ✅ Auto-select first model if current model is not in the list
      if (loadedModels.length > 0 && !loadedModels.includes(model)) {
        setModel(loadedModels[0])
        // console.log(`[ChatPage] Auto-selected model: ${loadedModels[0]}`)
      }
    } catch (error) {
      console.error(`Failed to load models for ${targetProvider}:`, error)
      // Fallback: load installed models
      try {
        const installedResp = await systemService.listModelsApiModelsListGet()
        const providerModels = installedResp.models
          .filter((m: any) => m.provider === targetProvider)
          .map((m: any) => m.name)
        setModels(providerModels.length > 0 ? providerModels : [])

        // ✅ Auto-select first model from fallback list
        if (providerModels.length > 0 && !providerModels.includes(model)) {
          setModel(providerModels[0])
          // console.log(`[ChatPage] Auto-selected fallback model: ${providerModels[0]}`)
        }
      } catch (installedError) {
        console.error('Failed to load installed models:', installedError)
        setModels([])
        setModel('')  // ✅ Clear model if no models available
      }
    }
  }, [model])

  const loadProvidersAndModels = useCallback(async () => {
    try {
      // Read-only warm-up for provider status cache.
      try {
        await providersApi.getProvidersStatus()
      } catch (statusError) {
        console.warn('[ChatPage] ⚠️ Failed to read provider status:', statusError)
      }

      // P0: Load providers from API
      const providersResp = await systemService.listProvidersApiProvidersGet()
      if (!Array.isArray(providersResp.local) || !Array.isArray(providersResp.cloud)) {
        throw new Error('Invalid providers response: expected { local: [], cloud: [] }')
      }

      // New contract only: { local: [...], cloud: [...] }
      const filteredProviders =
        mode === 'local'
          ? providersResp.local.map((p: any) => p.id).filter(Boolean)
          : providersResp.cloud.map((p: any) => p.id).filter(Boolean)

      setProviders(filteredProviders)
      // console.log(`[ChatPage] Loaded ${mode} providers:`, filteredProviders)

      // P0: Load models for the current provider
      if (provider && filteredProviders.includes(provider)) {
        // Current provider is valid for this mode
        await loadModelsForProvider(provider)
      } else if (filteredProviders.length > 0) {
        // Current provider invalid, switch to first available
        const firstProvider = filteredProviders[0]
        setProvider(firstProvider)
        await loadModelsForProvider(firstProvider)
      }
    } catch (error) {
      console.error('Failed to load providers/models:', error)
      setProviders([])
      setModels([])
      setModel('')
    }
  // ✅ 移除 loadModelsForProvider 和 provider 依赖，避免无限循环
  // provider 值会在函数执行时读取，不需要作为依赖
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  // ✅ 只在 mode 改变时触发，移除重复的 useEffect
  useEffect(() => {
    // console.log(`[ChatPage] Mode changed to: ${mode}, reloading providers`)
    loadProvidersAndModels()
  }, [mode, loadProvidersAndModels])

  // ===================================
  // P2: Startup Health Check
  // ===================================
  useEffect(() => {
    // 启动时执行一次健康检查
    const performStartupHealthCheck = async () => {
      try {
        const health = await systemService.daemonStatusApiDaemonStatusGet()
        const evaluation = evaluateDaemonHealth(health)

        if (!evaluation.healthy) {
          console.warn('[ChatPage] ⚠️ Startup health check failed:', evaluation.issues)
          setHealthWarning({
            show: true,
            issues: evaluation.issues.length > 0 ? evaluation.issues : ['Daemon not healthy'],
            hints: evaluation.hints,
          })
        } else {
          // console.log('[ChatPage] ✅ Startup health check passed')
        }
      } catch (error) {
        console.error('[ChatPage] ❌ Startup health check error:', error)
        // 静默失败，不显示错误提示（避免干扰用户初始体验）
      }
    }

    performStartupHealthCheck()
  }, []) // Only run once on mount

  // ===================================
  // P2: Periodic Health Check (Optional)
  // ===================================
  useEffect(() => {
    // 每30秒执行一次定时健康检查
    const healthCheckInterval = setInterval(async () => {
      try {
        const health = await systemService.daemonStatusApiDaemonStatusGet()
        const evaluation = evaluateDaemonHealth(health)
        if (!evaluation.healthy) {
          console.warn('[ChatPage] ⚠️ Periodic health check failed')
          setHealthWarning({
            show: true,
            issues: evaluation.issues.length > 0 ? evaluation.issues : ['Daemon not healthy'],
            hints: evaluation.hints
          })
        }
      } catch (error) {
        console.warn('[ChatPage] ⚠️ Periodic health check error:', error)
        // 静默失败，不影响用户体验
      }
    }, 30000) // 30 seconds

    // Cleanup: clear interval on unmount
    return () => {
      clearInterval(healthCheckInterval)
    }
  }, [])

  // ===================================
  // Handler Functions (v1 Three-Layer Logic)
  // ===================================
  const handleModeChange = useCallback((newMode: 'local' | 'cloud') => {
    // console.log(`[ChatPage] User switched mode: ${mode} → ${newMode}`)
    setMode(newMode)
    // loadProvidersAndModels will be triggered by useEffect
  }, [mode])

  const handleProviderChange = useCallback(async (newProvider: string) => {
    // console.log(`[ChatPage] User switched provider: ${provider} → ${newProvider}`)
    setProvider(newProvider)

    // P0: Load models for new provider
    await loadModelsForProvider(newProvider)
  }, [provider, loadModelsForProvider])

  const handleModelChange = useCallback((newModel: string) => {
    // console.log(`[ChatPage] User selected model: ${newModel}`)
    setModel(newModel)
  }, [])

  const handleConversationModeChange = useCallback(async (newMode: ConversationMode) => {
    const normalizedMode = normalizeConversationMode(newMode)
    const normalizedPhase = deriveExecutionPhaseByMode(normalizedMode, executionPhase)

    setConversationMode(normalizedMode)
    setExecutionPhase(normalizedPhase)
    await persistSessionMetadata({
      conversation_mode: normalizedMode,
      execution_phase: normalizedPhase,
    })
  }, [executionPhase, persistSessionMetadata])

  const applyExecutionPhaseChange = useCallback(async (nextPhase: ExecutionPhase) => {
    const normalized = normalizeExecutionPhase(nextPhase)

    if (conversationMode !== 'development' && conversationMode !== 'task' && normalized === 'execution') {
      toast.warning('Execution phase is only available in development and task modes')
      return
    }

    setExecutionPhase(normalized)
    await persistSessionMetadata({ execution_phase: normalized })
  }, [conversationMode, persistSessionMetadata])

  const handleExecutionPhaseChange = useCallback((nextPhase: ExecutionPhase) => {
    const normalized = normalizeExecutionPhase(nextPhase)
    if (normalized === executionPhase) return

    if (conversationMode !== 'development' && conversationMode !== 'task') {
      void applyExecutionPhaseChange('planning')
      return
    }

    if (normalized === 'execution') {
      setPendingPhase('execution')
      setPhaseConfirmOpen(true)
      return
    }

    void applyExecutionPhaseChange(normalized)
  }, [applyExecutionPhaseChange, executionPhase])

  // ===================================
  // Render: AppChatShell Pattern
  // ===================================
  const uiDisabled = !currentSessionId

  // console.log('[ChatPage] 🎨 Rendering, messages count:', messages.length)
  // console.log('[ChatPage] 🎨 Current messages:', messages)
  // console.log('[ChatPage] 🎨 Current sessionId:', currentSessionId)
  // console.log('[ChatPage] 🎨 isStreaming:', isStreaming)
  // console.log('[ChatPage] 🎨 streamingMessage:', streamingMessage)

  return (
    <>
      <AppChatShell
        sessions={sessions}
        currentSessionId={currentSessionId}
        messages={messages}
        loading={loading || sessionsLoading || messagesLoading}
        streamingMessage={streamingMessage}
        isStreaming={effectiveIsStreaming}
        awaitingReply={awaitingReply}
        awaitingReplyMessage={awaitingReplyMessage}
        onSessionSelect={handleSessionSelect}
        onSessionClear={handleSessionClear}
        onClearAll={() => {
          setClearAllDialogOpen(true)
        }}
        onSearchSessions={handleSearchSessions}
        onSendMessage={handleSendMessage}
        onStopStreaming={handleStopStreaming}
        onEditMessage={handleEditMessage}
        inputPlaceholder={t(K.page.chat.inputPlaceholder)}
        disabled={uiDisabled}
        inputValue={inputValue}
        onInputChange={setInputValue}
        onInputFocusChange={setInputFocused}
        suppressAutoFollow={inputFocused && Boolean(inputValue.trim())}
        emptyState={!currentSessionId ? {
          icon: <MessageIcon sx={{ fontSize: 64 }} />,
          message: t(K.page.chat.emptyDescription),
        } : undefined}
        modelSelection={{
          mode,
          provider,
          model,
          providers,
          models,
          onModeChange: (newMode: string) => {
            // Type guard: ensure newMode is 'local' or 'cloud'
            if (newMode === 'local' || newMode === 'cloud') {
              handleModeChange(newMode)
            } else {
              console.warn(`[ChatPage] Invalid mode: ${newMode}, ignoring`)
            }
          },
          onProviderChange: handleProviderChange,
          onModelChange: handleModelChange,
          onEmpty: () => {
            // console.log('Empty clicked')
          },
        }}
        contextSelection={{
          conversationMode,
          executionPhase,
          onConversationModeChange: (newMode) => {
            void handleConversationModeChange(newMode)
          },
          onExecutionPhaseChange: (newPhase) => {
            handleExecutionPhaseChange(newPhase)
          },
        }}
        banner={
          <>
            {sessionStateBanner}
            {healthWarning && (
              <HealthWarningBanner
                open={healthWarning.show}
                issues={healthWarning.issues}
                hints={healthWarning.hints}
                onClose={() => setHealthWarning(null)}
              />
            )}
          </>
        }
      />

      {/* P0-3: Clear All Confirmation Dialog */}
      <ConfirmDialog
        open={clearAllDialogOpen}
        onClose={() => setClearAllDialogOpen(false)}
        title={t(K.page.chat.confirmClearAll)}
        message={t(K.page.chat.confirmClearAllMessage)}
        confirmText={t(K.common.confirm)}
        cancelText={t(K.common.cancel)}
        onConfirm={handleClearAll}
        loading={clearingAll}
        color={'error' as const}
      />

      <ConfirmDialog
        open={phaseConfirmOpen}
        onClose={() => {
          setPhaseConfirmOpen(false)
          setPendingPhase(null)
        }}
        title={t(K.page.chat.phaseSwitchTitle)}
        message={t(K.page.chat.phaseSwitchMessage)}
        confirmText={t(K.page.chat.phaseSwitchConfirm)}
        cancelText={t(K.common.cancel)}
        onConfirm={() => {
          const nextPhase = pendingPhase ?? 'planning'
          setPhaseConfirmOpen(false)
          setPendingPhase(null)
          void applyExecutionPhaseChange(nextPhase)
        }}
      />

      <Dialog
        open={editDialogOpen}
        onClose={() => {
          if (editSubmitting) return
          setEditDialogOpen(false)
          setEditingMessage(null)
          setEditingText('')
        }}
        maxWidth={'sm' as const}
        fullWidth
      >
        <DialogTitle>{t(K.page.chat.editDialogTitle)}</DialogTitle>
        <DialogContent>
          <TextField
            multiline
            minRows={4}
            fullWidth
            value={editingText}
            onChange={(e) => setEditingText(e.target.value)}
            disabled={editSubmitting}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setEditDialogOpen(false)
              setEditingMessage(null)
              setEditingText('')
            }}
            disabled={editSubmitting}
          >
            {t(K.common.cancel)}
          </Button>
          <Button
            variant={'contained' as const}
            onClick={handleConfirmEditResend}
            disabled={editSubmitting || !editingText.trim()}
          >
            {t(K.page.chat.editDialogConfirm)}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Running Status Dialog */}
      <Dialog
        open={statusDialogOpen}
        onClose={() => setStatusDialogOpen(false)}
        maxWidth={'sm' as const}
        fullWidth
        disableRestoreFocus={false}
        disableEnforceFocus={false}
        sx={{ zIndex: (theme) => theme.zIndex.modal }}
      >
        <DialogTitle>{t(K.page.chat.statusDialogTitle)}</DialogTitle>
        <DialogContent>
          <Box>
            <Typography variant={'body1' as const} gutterBottom>
              {t(K.page.chat.statusDialogDescription)}
            </Typography>
            <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  label={
                    isConnected
                      ? t(K.page.chat.statusConnected)
                      : isConnecting
                        ? t(K.page.chat.statusConnecting)
                        : t(K.page.chat.statusDisconnected)
                  }
                  color={isConnected ? 'success' : 'warning'}
                  size={'small' as const}
                />
                <Typography variant={'body2' as const}>{t(K.page.chat.statusWebSocketConnection)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip label={t(K.page.chat.statusActive)} color={'success' as const} size={'small' as const} />
                <Typography variant={'body2' as const}>{t(K.page.chat.statusSessionManager)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip label={t(K.page.chat.statusActive)} color={'success' as const} size={'small' as const} />
                <Typography variant={'body2' as const}>{t(K.page.chat.statusModelConnection)}</Typography>
              </Box>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setStatusDialogOpen(false)} variant={'contained' as const} color={'primary' as const}>
            {t(K.common.ok)}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Self-Check Drawer */}
      <DetailDrawer
        open={selfCheckDrawerOpen}
        onClose={() => setSelfCheckDrawerOpen(false)}
        title={t(K.page.chat.selfCheckTitle)}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography variant={'h6' as const}>{t(K.page.chat.selfCheckHealthChecks)}</Typography>

          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.selfCheckWebSocketConnection)}
            </Typography>
            <Chip
              label={isConnected ? t(K.page.chat.selfCheckHealthy) : t(K.page.chat.statusDisconnected)}
              color={isConnected ? 'success' : 'error'}
              size={'small' as const}
            />
            <Typography variant={'body2' as const} color={'text.secondary' as const} sx={{ mt: 0.5 }}>
              {isConnected
                ? `${t(K.page.chat.selfCheckConnectedTo)} chat server`
                : t(K.page.chat.selfCheckNotConnected)}
            </Typography>
          </Box>

          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.selfCheckModelConnection)}
            </Typography>
            <Chip label={t(K.page.chat.selfCheckHealthy)} color={'success' as const} size={'small' as const} />
            <Typography variant={'body2' as const} color={'text.secondary' as const} sx={{ mt: 0.5 }}>
              {t(K.page.chat.selfCheckConnectedTo)} {model}
            </Typography>
          </Box>

          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.selfCheckSessionStorage)}
            </Typography>
            <Chip label={t(K.page.chat.selfCheckHealthy)} color={'success' as const} size={'small' as const} />
            <Typography variant={'body2' as const} color={'text.secondary' as const} sx={{ mt: 0.5 }}>
              {sessions.length} {t(K.page.chat.selfCheckActiveSessions)}
            </Typography>
          </Box>

          <Box sx={{ mt: 2 }}>
            <Button
              variant={'contained' as const}
              fullWidth
              onClick={async () => {
                try {
                  const response = await httpClient.get<{ ok: boolean }>('/api/support/diagnostics')
                  if (response.data?.ok) {
                    toast.success(t(K.page.chat.selfCheckCompleted))
                  } else {
                    toast.error('Diagnostic check failed')
                  }
                } catch (error) {
                  console.error('Diagnostic failed:', error)
                  toast.error('Diagnostic check failed')
                }
              }}
            >
              {t(K.page.chat.selfCheckRunFullDiagnostic)}
            </Button>
          </Box>
        </Box>
      </DetailDrawer>

      {/* Configuration Drawer */}
      <DetailDrawer
        open={configDrawerOpen}
        onClose={() => setConfigDrawerOpen(false)}
        title={t(K.page.chat.configTitle)}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.configModelSettings)}
            </Typography>
            <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
              {t(K.page.chat.configMode)}{': '}
              {mode === 'local' ? t(K.page.chat.modeLocal) : t(K.page.chat.modeCloud)}
            </Typography>
            <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
              {t(K.page.chat.configProvider)}{': '}
              {provider}
            </Typography>
            <Typography variant={'body2' as const} color={'text.secondary' as const}>
              {t(K.page.chat.configModel)}{': '}
              {model}
            </Typography>
          </Box>

          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.configConnectionSettings)}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <Chip
                label={isConnected ? t(K.page.chat.statusConnected) : t(K.page.chat.statusDisconnected)}
                color={isConnected ? 'success' : 'error'}
                size={'small' as const}
              />
              <Typography variant={'body2' as const} color={'text.secondary' as const}>
                {t(K.page.chat.configWebSocketStatus)}
              </Typography>
            </Box>
          </Box>

          <Box>
            <Typography variant={'subtitle2' as const} gutterBottom>
              {t(K.page.chat.configSessionSettings)}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <Chip label={sessionCountLabel} size={'small' as const} />
              <Typography variant={'body2' as const} color={'text.secondary' as const}>
                {t(K.page.chat.configAutoSaveEnabled)}
              </Typography>
            </Box>
          </Box>
        </Box>
      </DetailDrawer>
      {promptDialog}
    </>
  )
}
