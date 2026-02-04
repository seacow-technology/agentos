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

import { useState, useCallback, useEffect, useRef, startTransition } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { AppChatShell, type ChatMessageType, type ChatSession } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Chip } from '@/ui'
import { Box, Typography } from '@mui/material'
import { MessageIcon, PlayIcon as PlayArrowIcon, CheckCircleIcon, SettingsIcon } from '@/ui/icons'
import { useWebSocket } from '@/hooks/useWebSocket'
import { agentosService } from '@/services/agentos.service'
import { HealthWarningBanner } from '@/components/HealthWarningBanner'
import { httpClient } from '@platform/http'
import { useDraftProtection } from '@/hooks/useDraftProtection'

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
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [streamingMessage, setStreamingMessage] = useState<string>('')
  const [isStreaming, setIsStreaming] = useState(false)

  // 🎯 产品级功能：Draft 保护（输入框内容）
  const [inputValue, setInputValue] = useState<string>('')

  // 🎯 产品级功能：自动保存 + 崩溃恢复
  const { clearDraft } = useDraftProtection(
    currentSessionId,
    inputValue,
    (restoredContent) => {
      setInputValue(restoredContent)
      console.log('[ChatPage] ✅ Draft restored from crash recovery')
    }
  )

  // ✅ Use ref to track streaming message for stable callback reference
  const streamingMessageRef = useRef<string>('')

  // ✅ P1: Optimization - Buffer for batching delta updates
  const bufferRef = useRef<string>('')
  const rafRef = useRef<number | null>(null)

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
  const [provider, setProvider] = useState('llama.cpp')
  const [model, setModel] = useState('')  // ✅ Start with empty, will be set when models load

  // Computed values
  const sessionCountLabel = `${sessions.length} ${t(K.page.chat.conversationCount)}`

  // ===================================
  // P1: Optimization - Flush buffered streaming message
  // ===================================
  const flushStreamingMessage = useCallback(() => {
    rafRef.current = null
    setStreamingMessage(bufferRef.current)
  }, [])

  // ===================================
  // P0-1: WebSocket Integration
  // ===================================
  const { isConnected, isConnecting, error: wsError, sendMessage: wsSendMessage, connect } = useWebSocket({
    sessionId: currentSessionId,
    onMessage: useCallback((msg: { type: string; content: string; message_id?: string; messageId?: string; metadata?: Record<string, unknown> }) => {
      // console.log('[ChatPage] 📨 WebSocket message received:', msg)

      // ✅ Backend returns message_id (snake_case), normalize to messageId
      const messageId = msg.message_id || msg.messageId

      if (msg.type === 'message.start') {
        // console.log('[ChatPage] 🎬 Stream start')
        // ✅ Stream start - initialize streaming state
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setStreamingMessage('')
        setIsStreaming(true)
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
      } else if (msg.type === 'message.delta') {
        // console.log('[ChatPage] 📝 Stream delta, content length:', msg.content.length)
        // ✅ P1: Optimization - Accumulate to buffer and schedule RAF flush
        streamingMessageRef.current += msg.content
        bufferRef.current = streamingMessageRef.current

        // Schedule RAF flush if not already scheduled
        if (rafRef.current === null) {
          rafRef.current = requestAnimationFrame(flushStreamingMessage)
        }
        setIsStreaming(true)
      } else if (msg.type === 'message.end') {
        // ✅ Stream complete - finalize message
        // Use ref to get latest streaming content, fallback to msg.content if no streaming happened
        const finalContent = streamingMessageRef.current || msg.content || ''
        // console.log('[ChatPage] 🏁 Stream end, final content length:', finalContent.length)
        // console.log('[ChatPage] 🏁 Final content:', finalContent)
        // console.log('[ChatPage] 💾 Saving message to state...')

        setMessages((prev) => {
          const newMessage = {
            id: messageId || `msg-${Date.now()}`,
            role: 'assistant' as const,
            content: finalContent,
            timestamp: new Date().toISOString(),
            metadata: msg.metadata,
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
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current)
          rafRef.current = null
        }
      } else if (msg.type === 'message.error' || msg.type === 'error') {
        console.error('[ChatPage] ❌ Message error:', msg.content)
        // ✅ Error message
        toast.error(msg.content || t(K.page.chat.connectionError))
        streamingMessageRef.current = ''
        bufferRef.current = ''
        setIsStreaming(false)
        setStreamingMessage('')
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
    }, [t, currentSessionId, flushStreamingMessage]),
    onConnect: useCallback(() => {
      // console.log('WebSocket connected')
    }, []),
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
    }
  }, [wsError])

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
      const sessions = await agentosService.listSessions()
      // console.log('[ChatPage] 📂 API returned sessions count:', sessions.length)

      // 🚀 为每个 session 并发加载最后一条消息
      const sessionsWithLastMessage = await Promise.all(
        sessions.map(async (session: any) => {
          let lastMessage = session.last_message || session.lastMessage || ''

          // 如果后端没有返回 lastMessage，尝试加载消息列表获取最后一条
          if (!lastMessage) {
            try {
              const response = await agentosService.getSessionMessages(session.id)
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

  // ✅ Initialize CSRF token and load sessions on mount
  useEffect(() => {
    const initializeApp = async () => {
      // First, ensure CSRF token is available
      try {
        await agentosService.ensureCSRFToken()
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
  const handleNewConversation = useCallback(async () => {
    setLoading(true)
    try {
      // Backend returns SessionResponse directly, not wrapped in { session: ... }
      const response = await agentosService.createSession({
        title: `New Chat - ${new Date().toLocaleString()}`,
        metadata: {},
      })

      // Handle both response formats for backward compatibility
      const sessionData = 'session' in response ? response.session : response

      const newSession: ChatSession = {
        id: sessionData.id,
        title: sessionData.title || 'New Chat',
        lastMessage: '',
        timestamp: sessionData.created_at,
        unreadCount: 0,
      }

      setSessions((prev) => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      setMessages([])
      toast.success(t(K.page.chat.newConversationSuccess))
    } catch (error) {
      console.error('Failed to create session:', error)
      toast.error(t(K.page.chat.newConversationFailed))
    } finally {
      setLoading(false)
    }
  }, [t])

  // ===================================
  // P0-4: Single Session Deletion API
  // ===================================
  const handleSessionClear = useCallback(
    async (sessionId: string) => {
      try {
        await agentosService.deleteSession(sessionId)
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
      await agentosService.deleteAllSessions()
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
      // P0: Load message history from API
      const response = await agentosService.getSessionMessages(sessionId)
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
      }))
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
      toast.error('Failed to load conversation history')
      setMessages([])  // Clear on error
    } finally {
      setMessagesLoading(false)
    }
  }, [])

  // ===================================
  // P0-2: Session Selection Handler
  // ===================================
  const handleSessionSelect = useCallback(
    (sessionId: string) => {
      setCurrentSessionId(sessionId)
      // Messages will be loaded by useEffect watching currentSessionId
    },
    []
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
        return
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
      agentosService.checkChatHealth()
        .then(health => {
          if (!health.is_healthy) {
            // 仅在健康检查失败时显示警告（不阻止消息发送）
            setHealthWarning({
              show: true,
              issues: health.issues,
              hints: health.hints || []
            })
          }
        })
        .catch(error => {
          console.warn('[ChatPage] Background health check failed:', error)
          // 静默失败，不影响用户体验
        })

      // Send via WebSocket with metadata
      const metadata = {
        model_type: mode,
        provider,
        model,
      }
      // console.log('[ChatPage] 📤 Sending message via WebSocket:', { text, metadata })

      // ✅ 错误处理：WebSocket 发送失败时提示
      try {
        wsSendMessage(text, metadata)

        // 🎯 产品级功能：发送成功后清除草稿和输入框
        clearDraft()
        setInputValue('')
      } catch (error) {
        console.error('[ChatPage] Failed to send message via WebSocket:', error)
        toast.error(t(K.page.chat.connectionError))
      }
    },
    [isConnected, wsSendMessage, mode, provider, model, currentSessionId, t, clearDraft]
  )

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.chat.title),
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
      const modelsResp = await agentosService.getProviderModels(targetProvider)
      const loadedModels = modelsResp.models.map(m => m.id)
      setModels(loadedModels)
      // console.log(`[ChatPage] Loaded models for ${targetProvider}:`, modelsResp.models.length)

      // ✅ Auto-select first model if current model is not in the list
      if (loadedModels.length > 0 && !loadedModels.includes(model)) {
        setModel(loadedModels[0])
        // console.log(`[ChatPage] Auto-selected model: ${loadedModels[0]}`)
      }
    } catch (error) {
      console.error(`Failed to load models for ${targetProvider}:`, error)
      // Fallback: load installed models
      try {
        const installedResp = await agentosService.getInstalledModels()
        const providerModels = installedResp.models
          .filter(m => m.provider === targetProvider)
          .map(m => m.name)
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
      // ✅ P0: Trigger provider status probe first (to populate cache for health checks)
      // This ensures ChatHealthChecker can find available providers
      try {
        await agentosService.getAllProvidersStatus()
        // console.log('[ChatPage] ✅ Provider status probed successfully')
      } catch (statusError) {
        console.warn('[ChatPage] ⚠️ Failed to probe provider status:', statusError)
        // Continue anyway - getProviders() will still work
      }

      // P0: Load providers from API
      const providersResp = await agentosService.getProviders()

      // ✅ Layer 1: Filter providers based on mode (v1 logic)
      let filteredProviders: string[]
      if (mode === 'local') {
        // Local providers: ollama, lmstudio, llamacpp
        filteredProviders = providersResp.local.map((p: any) => p.id)
      } else {
        // Cloud providers: openai, anthropic, bedrock, azure
        filteredProviders = providersResp.cloud.map((p: any) => p.id)
      }

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

  // ✅ 初始化时加载提供商和模型
  useEffect(() => {
    // console.log('[ChatPage] 🚀 Initializing providers and models on mount')
    loadProvidersAndModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run once on mount

  // ===================================
  // P2: Startup Health Check
  // ===================================
  useEffect(() => {
    // 启动时执行一次健康检查
    const performStartupHealthCheck = async () => {
      try {
        const health = await agentosService.checkChatHealth()
        if (!health.is_healthy) {
          console.warn('[ChatPage] ⚠️ Startup health check failed:', health.issues)
          setHealthWarning({
            show: true,
            issues: health.issues,
            hints: health.hints || []
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
        const health = await agentosService.checkChatHealth()
        if (!health.is_healthy) {
          console.warn('[ChatPage] ⚠️ Periodic health check failed:', health.issues)
          setHealthWarning({
            show: true,
            issues: health.issues,
            hints: health.hints || []
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

  // ===================================
  // Render: AppChatShell Pattern
  // ===================================
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
        isStreaming={isStreaming}
        onSessionSelect={handleSessionSelect}
        onSessionClear={handleSessionClear}
        onClearAll={() => {
          setClearAllDialogOpen(true)
        }}
        onSearchSessions={handleSearchSessions}
        onSendMessage={handleSendMessage}
        inputPlaceholder={t(K.page.chat.inputPlaceholder)}
        disabled={!isConnected}
        inputValue={inputValue}
        onInputChange={setInputValue}
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
        banner={
          healthWarning && (
            <HealthWarningBanner
              open={healthWarning.show}
              issues={healthWarning.issues}
              hints={healthWarning.hints}
              onClose={() => setHealthWarning(null)}
            />
          )
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
    </>
  )
}
