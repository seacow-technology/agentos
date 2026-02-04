/**
 * ApiStatus - API Connection Status Indicator
 *
 * 🎨 Design Principles:
 * - IconButton with Badge
 * - Color-coded status (green/yellow/red)
 * - Tooltip shows status text
 * - i18n support
 * - Click to show details (optional)
 */

import { IconButton, Tooltip, Badge } from '@mui/material'
import { CloudDone as ConnectedIcon, CloudOff as DisconnectedIcon, Cloud as CheckingIcon } from '@mui/icons-material'
import { t, K } from '@/ui/text'

export type ApiStatusType = 'connected' | 'disconnected' | 'checking'

export interface ApiStatusProps {
  /**
   * Current API status
   */
  status: ApiStatusType
  /**
   * Optional click handler (e.g., show details dialog)
   */
  onClick?: () => void
}

const STATUS_CONFIG = {
  connected: {
    icon: ConnectedIcon,
    color: 'success.main' as const,
    badgeColor: 'success' as const,
    getLabel: () => t(K.appBar.apiConnected),
  },
  disconnected: {
    icon: DisconnectedIcon,
    color: 'error.main' as const,
    badgeColor: 'error' as const,
    getLabel: () => t(K.appBar.apiDisconnected),
  },
  checking: {
    icon: CheckingIcon,
    color: 'warning.main' as const,
    badgeColor: 'warning' as const,
    getLabel: () => t(K.appBar.apiChecking),
  },
}

/**
 * ApiStatus Component
 *
 * Displays current API connection status with visual indicator
 */
export function ApiStatus({ status, onClick }: ApiStatusProps) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon

  return (
    <Tooltip title={config.getLabel()}>
      <IconButton
        onClick={(event) => {
          // ✅ 主动 blur 按钮，防止打开 Dialog 后焦点滞留
          if (event.currentTarget instanceof HTMLElement) {
            event.currentTarget.blur()
          }
          onClick?.()
        }}
        color="inherit"
        aria-label={config.getLabel()}
        sx={{
          position: 'relative',
        }}
      >
        <Badge
          overlap="circular"
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          variant="dot"
          color={config.badgeColor}
          sx={{
            '& .MuiBadge-badge': {
              boxShadow: (theme) => `0 0 0 2px ${theme.palette.background.paper}`,
            },
          }}
        >
          <Icon sx={{ color: config.color }} />
        </Badge>
      </IconButton>
    </Tooltip>
  )
}
