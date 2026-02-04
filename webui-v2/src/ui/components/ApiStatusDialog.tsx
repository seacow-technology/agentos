/**
 * ApiStatusDialog - API Status Details Dialog
 *
 * 🎨 Design Principles:
 * - Dialog with status details
 * - Show last check time
 * - Show detailed connection info
 * - i18n support
 * - Manual refresh button
 */

import { useRef, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  IconButton,
  CircularProgress,
} from '@mui/material'
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  HourglassEmpty as CheckingIcon,
} from '@mui/icons-material'
import { t, K } from '@/ui/text'
import type { ApiStatusType } from '@/ui'

export interface ApiStatusDialogProps {
  /**
   * Dialog open state
   */
  open: boolean
  /**
   * Close handler
   */
  onClose: () => void
  /**
   * Current API status
   */
  status: ApiStatusType
  /**
   * Last check timestamp
   */
  lastCheck: Date | null
  /**
   * Detailed status information
   */
  details?: {
    database?: string
    cache?: string
    [key: string]: string | undefined
  } | null
  /**
   * Error information
   */
  error?: Error | null
  /**
   * Refresh handler
   */
  onRefresh?: () => void
}

const STATUS_CONFIG = {
  connected: {
    icon: CheckIcon,
    color: 'success' as const,
    label: () => t(K.appBar.apiConnected),
  },
  disconnected: {
    icon: ErrorIcon,
    color: 'error' as const,
    label: () => t(K.appBar.apiDisconnected),
  },
  checking: {
    icon: CheckingIcon,
    color: 'warning' as const,
    label: () => t(K.appBar.apiChecking),
  },
}

/**
 * ApiStatusDialog Component
 *
 * Displays detailed API connection status information
 */
export function ApiStatusDialog({
  open,
  onClose,
  status,
  lastCheck,
  details,
  error,
  onRefresh,
}: ApiStatusDialogProps) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon

  // ===================================
  // 🔒 焦点管理：显式保存和恢复焦点
  // ===================================
  const lastActiveElementRef = useRef<HTMLElement | null>(null)

  // Dialog打开时保存当前焦点
  useEffect(() => {
    if (open) {
      lastActiveElementRef.current = document.activeElement as HTMLElement
    }
  }, [open])

  // 处理Dialog关闭，显式恢复焦点
  const handleClose = () => {
    // 第1步：立即blur当前焦点元素
    const currentFocus = document.activeElement as HTMLElement
    if (currentFocus && typeof currentFocus.blur === 'function') {
      try {
        currentFocus.blur()
      } catch (e) {
        // ignore
      }
    }

    // 第2步：尝试恢复到触发按钮（AppBar的ApiStatus按钮）
    if (lastActiveElementRef.current && typeof lastActiveElementRef.current.focus === 'function') {
      try {
        lastActiveElementRef.current.focus()
      } catch (e) {
        console.warn('Failed to restore focus to ApiStatus button:', e)
        // 第3步：Fallback到body
        try {
          document.body.focus()
        } catch (e2) {
          // ignore
        }
      }
    } else {
      // 没有保存的焦点元素，fallback到body
      try {
        document.body.focus()
      } catch (e) {
        // ignore
      }
    }

    // 第4步：关闭Dialog
    onClose()
  }

  const formatTime = (date: Date | null) => {
    if (!date) return 'N/A'
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      // ===================================
      // 🔒 焦点管理 - 修复 ARIA 警告
      // ===================================
      disableRestoreFocus={false}  // 保留MUI的自动restore作为fallback
      disableEnforceFocus={false}  // 强制焦点保持在 Dialog 内
      disableAutoFocus={true}      // 🔒 阻止Paper容器自动获得焦点
      // ===================================
      sx={{
        '& .MuiDialog-paper': {
          borderRadius: 1,
        },
      }}
      // ===================================
      // 🔒 让 Paper 容器完全不可聚焦
      // ===================================
      PaperProps={{
        // @ts-ignore - MUI types可能不允许tabIndex为null，但运行时有效
        tabIndex: null,
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Icon color={config.color} />
          <Typography variant="h6">
            {t(K.appBar.apiStatusDetails || 'appBar.apiStatusDetails')}
          </Typography>
        </Box>
        <IconButton
          size="small"
          onClick={handleClose}
          aria-label={t('common.close')}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2 }}>
        {/* Status Overview */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {t(K.appBar.currentStatus || 'appBar.currentStatus')}
            </Typography>
            <Chip
              label={config.label()}
              color={config.color}
              size="small"
              icon={status === 'checking' ? <CircularProgress size={16} /> : <Icon />}
            />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="body2" color="text.secondary">
              {t(K.appBar.lastCheck || 'appBar.lastCheck')}
            </Typography>
            <Typography variant="body2">{formatTime(lastCheck)}</Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Detailed Status */}
        {details && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {t(K.appBar.serviceDetails || 'appBar.serviceDetails')}
            </Typography>
            <List dense>
              {Object.entries(details).map(([key, value]) => (
                <ListItem key={key} sx={{ px: 0 }}>
                  <ListItemText
                    primary={key.charAt(0).toUpperCase() + key.slice(1)}
                    secondary={value || 'N/A'}
                  />
                  <Chip
                    label={value === 'connected' ? 'OK' : value}
                    color={value === 'connected' ? 'success' : 'default'}
                    size="small"
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        )}

        {/* Error Message */}
        {error && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="error" sx={{ mb: 1 }}>
              {t('common.error')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{
              p: 1.5,
              bgcolor: 'error.lighter',
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.875rem',
            }}>
              {error.message}
            </Typography>
          </Box>
        )}

        {/* Info */}
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
          {t(K.appBar.autoRefreshNote || 'appBar.autoRefreshNote')}
        </Typography>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="outlined">
          {t('common.close')}
        </Button>
        <Button
          onClick={onRefresh}
          variant="contained"
          startIcon={status === 'checking' ? <CircularProgress size={16} /> : <RefreshIcon />}
          disabled={status === 'checking'}
        >
          {t('common.refresh')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
