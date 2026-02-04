/**
 * SessionList - Chat Session List Component
 *
 * Features:
 * - Search sessions by keyword
 * - Select multiple sessions
 * - Clear selected or all sessions
 * - Display session info (title, last message, timestamp, unread count)
 */

import { Box, TextField, Button, Typography, List, useTheme } from '@mui/material'
import { Search as SearchIcon, DeleteSweep as DeleteSweepIcon, Delete as DeleteIcon } from '@mui/icons-material'
import { SessionItem } from './SessionItem'
import type { ChatSession } from './AppChatShell'
import { useTextTranslation } from '@/ui/text'

export interface SessionListProps {
  sessions: ChatSession[]
  currentSessionId?: string
  selectedSessions: string[]
  searchKeyword: string
  onSessionSelect: (sessionId: string) => void
  onSessionToggle: (sessionId: string) => void
  onClearSelected: () => void
  onClearAll: () => void
  onSearch: (keyword: string) => void
}

export function SessionList({
  sessions,
  currentSessionId,
  selectedSessions,
  searchKeyword,
  onSessionSelect,
  onSessionToggle,
  onClearSelected,
  onClearAll,
  onSearch,
}: SessionListProps) {
  const { t } = useTextTranslation()
  const theme = useTheme()
  const agentos = (theme.palette as any).agentos
  const hasSelection = selectedSessions.length > 0

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Search Bar */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <TextField
          fullWidth
          size="small"
          placeholder={t('page.chat.searchPlaceholder')}
          value={searchKeyword}
          onChange={(e) => onSearch(e.target.value)}
          InputProps={{
            startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
          }}
        />
      </Box>

      {/* Action Bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 1,
          borderBottom: 1,
          borderColor: 'divider',
          // ✅ 使用 AgentOS tokens 适配暗色主题
          bgcolor: agentos?.bg?.section || 'background.default',
          gap: 0.5,
          flexWrap: 'nowrap', // 防止换行
        }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 1, minWidth: 0 }}>
          {sessions.length} {t('page.chat.conversationCount')}
          {hasSelection && ` · ${t('page.chat.selectedCount')} ${selectedSessions.length}`}
        </Typography>

        <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0 }}>
          {/* Clear Selected Button - 只显示图标 */}
          <Button
            size="small"
            disabled={!hasSelection}
            onClick={onClearSelected}
            sx={{ minWidth: 'auto', px: 1 }}
            title={t('page.chat.clearSelected')}
          >
            <DeleteIcon fontSize="small" />
          </Button>

          {/* Clear All Button - 只显示图标 */}
          <Button
            size="small"
            disabled={sessions.length === 0}
            onClick={onClearAll}
            sx={{ minWidth: 'auto', px: 1 }}
            color="error"
            title={t('page.chat.clearAll')}
          >
            <DeleteSweepIcon fontSize="small" />
          </Button>
        </Box>
      </Box>

      {/* Session List */}
      <List
        sx={{
          flex: 1,
          overflowY: 'auto', // ✅ 垂直滚动
          overflowX: 'hidden', // ✅ 隐藏水平滚动条
          p: 0,
          // 隐藏滚动条但保留滚动功能
          '&::-webkit-scrollbar': {
            display: 'none', // Chrome/Safari/Edge
          },
          scrollbarWidth: 'none', // Firefox
          msOverflowStyle: 'none', // IE/Edge
        }}
      >
        {sessions.map((session) => (
          <SessionItem
            key={session.id}
            session={session}
            isActive={session.id === currentSessionId}
            isSelected={selectedSessions.includes(session.id)}
            onSelect={() => onSessionSelect(session.id)}
            onToggle={() => onSessionToggle(session.id)}
          />
        ))}

        {sessions.length === 0 && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: 3,
            }}
          >
            <Typography variant="body2" color="text.secondary" align="center">
              {searchKeyword ? t('page.chat.noMatchingConversations') : t('page.chat.noConversations')}
            </Typography>
          </Box>
        )}
      </List>
    </Box>
  )
}
