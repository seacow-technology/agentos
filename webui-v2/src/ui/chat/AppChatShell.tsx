/**
 * AppChatShell - Application-level Chat Interface Pattern
 *
 * 🏛️ Pattern Component for complete chat application
 * Layout:
 * - Left: Session List (search, clear actions)
 * - Right: Chat conversation (ChatShell)
 */

import { Box, Paper } from '@mui/material'
import { useState } from 'react'
import { SessionList } from './SessionList'
import { ChatShell, type ChatMessageType, type ChatShellProps } from './ChatShell'
import type { EmptyStateProps } from '@/ui'

export interface ChatSession {
  id: string
  title: string
  lastMessage?: string
  timestamp: string
  unreadCount?: number
}

export interface AppChatShellProps {
  sessions: ChatSession[]
  currentSessionId?: string
  messages: ChatMessageType[]
  loading?: boolean
  onSessionSelect?: (sessionId: string) => void
  onSessionClear?: (sessionId: string) => void
  onClearAll?: () => void
  onSearchSessions?: (keyword: string) => void
  onSendMessage?: (text: string) => void
  inputPlaceholder?: string
  disabled?: boolean
  emptyState?: EmptyStateProps

  // Model Selection (pass through to ChatShell)
  modelSelection?: ChatShellProps['modelSelection']
  showModelSelection?: boolean

  // Streaming message (pass through to ChatShell)
  streamingMessage?: string
  isStreaming?: boolean

  // Banner (displayed at top of chat area)
  banner?: React.ReactNode

  // 🎯 受控输入支持（用于 Draft 保护）
  inputValue?: string
  onInputChange?: (value: string) => void
}

/**
 * AppChatShell Pattern Component
 *
 * Two-column layout:
 * - Left: Session list with search and actions
 * - Right: Chat conversation
 */
export function AppChatShell({
  sessions,
  currentSessionId,
  messages,
  loading = false,
  onSessionSelect,
  onSessionClear,
  onClearAll,
  onSearchSessions,
  onSendMessage,
  inputPlaceholder = 'Type a message...',
  disabled = false,
  emptyState,
  modelSelection,
  showModelSelection = true,
  streamingMessage = '',
  isStreaming = false,
  banner,
  inputValue,
  onInputChange,
}: AppChatShellProps) {
  const [selectedSessions, setSelectedSessions] = useState<string[]>([])
  const [searchKeyword, setSearchKeyword] = useState('')

  // ===================================
  // Handlers
  // ===================================
  const handleSessionSelect = (sessionId: string) => {
    if (onSessionSelect) {
      onSessionSelect(sessionId)
    }
  }

  const handleSessionToggle = (sessionId: string) => {
    setSelectedSessions((prev) =>
      prev.includes(sessionId)
        ? prev.filter((id) => id !== sessionId)
        : [...prev, sessionId]
    )
  }

  const handleClearSelected = () => {
    selectedSessions.forEach((id) => {
      if (onSessionClear) {
        onSessionClear(id)
      }
    })
    setSelectedSessions([])
  }

  const handleClearAll = () => {
    if (onClearAll) {
      onClearAll()
    }
    setSelectedSessions([])
  }

  const handleSearch = (keyword: string) => {
    setSearchKeyword(keyword)
    if (onSearchSessions) {
      onSearchSessions(keyword)
    }
  }

  // ===================================
  // Render: Two-column layout
  // ===================================
  return (
    <Box
      sx={{
        display: 'flex',
        height: '100%',
        gap: 2,
        // ✅ 去掉 px: 2，防止 flex 容器 + padding 导致宽度溢出
        // 边距由子元素自己处理
        pb: 2, // 底部边距
      }}
    >
      {/* Left Column - Session List */}
      <Paper
        sx={{
          width: '360px', // 固定宽度，不参与缩放
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minWidth: 0, // ✅ 防止子元素撑破
          ml: 2, // ✅ 左边距
        }}
      >
        <SessionList
          sessions={sessions}
          currentSessionId={currentSessionId}
          selectedSessions={selectedSessions}
          searchKeyword={searchKeyword}
          onSessionSelect={handleSessionSelect}
          onSessionToggle={handleSessionToggle}
          onClearSelected={handleClearSelected}
          onClearAll={handleClearAll}
          onSearch={handleSearch}
        />
      </Paper>

      {/* Right Column - Chat Conversation */}
      <Box sx={{ flex: 1, minWidth: 0, mr: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Banner (if provided) */}
        {banner}

        {/* Chat Shell */}
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <ChatShell
            messages={messages}
            loading={loading}
            onSendMessage={onSendMessage}
            inputPlaceholder={inputPlaceholder}
            disabled={disabled}
            emptyState={emptyState}
            modelSelection={modelSelection}
            showModelSelection={showModelSelection}
            streamingMessage={streamingMessage}
            isStreaming={isStreaming}
            inputValue={inputValue}
            onInputChange={onInputChange}
          />
        </Box>
      </Box>
    </Box>
  )
}
