/**
 * ChatShell - Chat Interface Pattern Component
 *
 * 🏛️ Pattern Component for chat/messaging interfaces
 * - Provides message list + input bar layout
 * - Supports loading states and empty states
 * - Built-in skeleton screen
 * - No-Interaction friendly (disabled mode)
 */

import React, { useRef, useState, useMemo } from 'react'
import { Box, Paper, Fab, Tooltip, useTheme } from '@mui/material'
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso'
import { ChatMessage } from './ChatMessage'
import { ChatInputBar } from './ChatInputBar'
import { ChatSkeleton } from './ChatSkeleton'
import { ModelSelectionBar, type ModelSelectionBarProps } from './ModelSelectionBar'
import { EmptyState, type EmptyStateProps } from '@/ui'
import { MessageIcon, ArrowDownIcon } from '@/ui/icons'
import { t, K } from '@/ui/text'

export interface ChatMessageType {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  avatar?: string
  metadata?: {
    model?: string
    tokens?: number
  }
}

export interface ChatShellProps {
  messages: ChatMessageType[]
  loading?: boolean
  onSendMessage?: (text: string) => void
  inputPlaceholder?: string
  disabled?: boolean
  emptyState?: EmptyStateProps

  // Model Selection Bar (optional)
  modelSelection?: Omit<ModelSelectionBarProps, 'disabled'>
  showModelSelection?: boolean

  // Streaming message (displayed as temporary assistant message)
  streamingMessage?: string
  isStreaming?: boolean

  // 🎯 受控输入支持（用于 Draft 保护）
  inputValue?: string
  onInputChange?: (value: string) => void
}

/**
 * ChatShell Pattern Component
 *
 * Layout:
 * - Messages Container (scrollable)
 * - Model Selection Bar (optional)
 * - Input Bar (fixed at bottom)
 *
 * States:
 * - loading: shows ChatSkeleton
 * - empty: shows EmptyState
 * - normal: shows messages + model selection + input
 */
export function ChatShell({
  messages,
  loading = false,
  onSendMessage,
  inputPlaceholder = 'Type a message...',
  disabled = false,
  emptyState,
  modelSelection,
  showModelSelection = true,
  streamingMessage = '',
  isStreaming = false,
  inputValue,
  onInputChange,
}: ChatShellProps) {
  const theme = useTheme()
  const agentos = theme.palette.agentos

  // ===================================
  // Virtuoso Ref & Scroll State
  // ===================================
  const virtuosoRef = useRef<VirtuosoHandle>(null)
  const [showScrollFab, setShowScrollFab] = useState(false)
  // ✅ P1 优化：移除 atBottom 状态，Virtuoso 的 followOutput 函数会接收 isAtBottom 参数

  // Prepare display messages (combine messages + streaming message)
  const displayMessages = useMemo(() => {
    const allMessages = [...messages]

    // Add streaming message as temporary assistant message
    if (isStreaming && streamingMessage) {
      allMessages.push({
        id: 'streaming',
        role: 'assistant' as const,
        content: streamingMessage,
        timestamp: new Date().toISOString(),
      })
    }

    return allMessages
  }, [messages, isStreaming, streamingMessage])

  // Scroll to bottom smoothly
  const scrollToBottom = () => {
    virtuosoRef.current?.scrollToIndex({
      index: displayMessages.length - 1,
      behavior: 'smooth',
      align: 'end',
    })
  }

  // ✅ P1 优化：移除手动滚动的 useEffect，避免与 Virtuoso followOutput 冲突
  // followOutput 函数会自动处理滚动逻辑

  // ===================================
  // Loading State
  // ===================================
  // ✅ Only show skeleton when truly loading, not when streaming
  if (loading && !isStreaming) {
    return <ChatSkeleton />
  }

  // ===================================
  // Empty State
  // ===================================
  if (messages.length === 0 && emptyState) {
    return <EmptyState {...emptyState} />
  }

  // ===================================
  // Normal State - Messages + Input
  // ===================================
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        position: 'relative',
      }}
    >
      {/* Messages Container */}
      <Paper
        sx={{
          flex: 1,
          overflow: 'hidden',
          // ✅ 使用 AgentOS tokens 适配暗色主题
          bgcolor: agentos?.bg?.section || 'background.default',
          borderRadius: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {displayMessages.length === 0 ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flex: 1,
              gap: 1.5,
              p: 3,
            }}
          >
            <MessageIcon
              sx={{
                fontSize: 64,
                color: 'text.secondary',
                opacity: 0.3,
              }}
            />
            <Box
              sx={{
                textAlign: 'center',
                color: 'text.secondary',
                opacity: 0.7,
                fontSize: '0.875rem',
              }}
            >
              在下方输入框开始对话
            </Box>
          </Box>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            data={displayMessages}
            followOutput={(isAtBottom) => {
              // ✅ P1 优化：动态控制滚动行为
              // 只有在底部时才自动跟随新消息滚动，避免打断用户查看历史消息
              return isAtBottom ? 'smooth' : false
            }}
            alignToBottom
            atBottomStateChange={(bottom) => {
              // ✅ P1 优化：只控制 FAB 显示/隐藏，滚动行为由 followOutput 函数处理
              // Show FAB if user scrolled up from bottom
              setShowScrollFab(!bottom)
            }}
            itemContent={(_index, message) => (
              <Box sx={{ px: 3, py: 1 }}>
                <ChatMessage key={message.id} message={message} />
              </Box>
            )}
            components={{
              // Custom scroller with hidden scrollbar
              Scroller: React.forwardRef<HTMLDivElement, React.HTMLProps<HTMLDivElement>>((props, ref) => (
                <div
                  {...props}
                  ref={ref}
                  style={{
                    ...(props.style || {}),
                    scrollbarWidth: 'none', // Firefox
                  }}
                  className="custom-scroller"
                />
              )),
            }}
            style={{
              height: '100%',
              width: '100%',
            }}
          />
        )}
      </Paper>

      {/* Scroll to Bottom FAB */}
      {showScrollFab && (
        <Tooltip title={t(K.page.chat.scrollToBottom) || '跳到底部'} placement="left">
          <Fab
            color="primary"
            size="small"
            onClick={scrollToBottom}
            sx={{
              position: 'absolute',
              bottom: showModelSelection && modelSelection ? 180 : 100,  // ✅ 增加间距，避免重叠
              right: 24,
              zIndex: 10,
              boxShadow: theme.shadows[4],
            }}
          >
            <ArrowDownIcon />
          </Fab>
        </Tooltip>
      )}

      {/* Model Selection Bar */}
      {showModelSelection && modelSelection && (
        <ModelSelectionBar {...modelSelection} disabled={disabled} />
      )}

      {/* Input Bar */}
      <ChatInputBar
        onSend={onSendMessage}
        placeholder={inputPlaceholder}
        disabled={disabled}
        value={inputValue}
        onChange={onInputChange}
      />
    </Box>
  )
}
