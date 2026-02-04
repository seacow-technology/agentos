/**
 * SessionItem - Individual Chat Session Item
 *
 * Displays:
 * - Checkbox for selection
 * - Session title
 * - Last message preview
 * - Timestamp
 * - Unread badge
 */

import { Box, Checkbox, ListItem, ListItemButton, Typography, Badge } from '@mui/material'
import type { ChatSession } from './AppChatShell'
import { useTextTranslation } from '@/ui/text'

export interface SessionItemProps {
  session: ChatSession
  isActive: boolean
  isSelected: boolean
  onSelect: () => void
  onToggle: () => void
}

export function SessionItem({
  session,
  isActive,
  isSelected,
  onSelect,
  onToggle,
}: SessionItemProps) {
  const { t } = useTextTranslation()

  return (
    <ListItem
      disablePadding
      sx={{
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: isActive ? 'action.selected' : 'transparent',
        pr: 2, // ✅ 右内边距 16px，给 Badge 足够的间距
        '&:hover': {
          bgcolor: isActive ? 'action.selected' : 'action.hover',
        },
      }}
    >
      {/* Checkbox for selection */}
      <Checkbox
        checked={isSelected}
        onChange={(e) => {
          e.stopPropagation()
          onToggle()
        }}
        sx={{ ml: 1 }}
      />

      {/* Session Content */}
      <ListItemButton
        onClick={onSelect}
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          py: 1.5,
          px: 1, // 恢复原来的 padding
        }}
      >
        {/* Title and Timestamp */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            mb: 0.5,
          }}
        >
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: isActive ? 600 : 500,
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {session.title}
          </Typography>

          {/* Unread Badge */}
          {session.unreadCount && session.unreadCount > 0 && (
            <Badge
              badgeContent={session.unreadCount}
              color="primary"
              sx={{ ml: 1 }}
            />
          )}
        </Box>

        {/* Last Message and Timestamp */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
          }}
        >
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {session.lastMessage || t('page.chat.noMessage')}
          </Typography>

          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ ml: 1, flexShrink: 0 }}
          >
            {formatTimestamp(session.timestamp, t)}
          </Typography>
        </Box>
      </ListItemButton>
    </ListItem>
  )
}

/**
 * Format timestamp to relative time
 */
function formatTimestamp(timestamp: string, t: (key: string) => string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return t('page.chat.justNow')
  if (diffMins < 60) return `${diffMins} ${t('page.chat.minutesAgo')}`
  if (diffHours < 24) return `${diffHours} ${t('page.chat.hoursAgo')}`
  if (diffDays < 7) return `${diffDays} ${t('page.chat.daysAgo')}`

  // Format as MM-DD
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}-${day}`
}
