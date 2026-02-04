/**
 * StatusCard - 状态卡片
 *
 * 🔒 Contract 强制规则：
 * - 统一状态样式（badge/颜色）
 * - 页面禁止自定义状态卡片
 *
 * 使用示例：
 * ```tsx
 * <StatusCard
 *   title="Provider Instance"
 *   status="running"
 *   statusLabel={T.status.running}
 *   description="Ollama local instance"
 *   meta={[
 *     { key: 'cpu', label: T.metric.cpu, value: '45%' },
 *     { key: 'memory', label: T.metric.memory, value: '2.1 GB' },
 *   ]}
 *   actions={[
 *     { key: 'stop', label: T.action.stop, variant: 'outlined', onClick: handleStop },
 *   ]}
 * />
 * ```
 */

import React from 'react'
import { Box, Card, CardContent, Typography, Button, Chip } from '@mui/material'
import { CARD_PADDING } from '@/ui/layout/tokens'

// ===================================
// Types
// ===================================

export type StatusColor = 'success' | 'warning' | 'error' | 'info' | 'default'

export interface StatusCardMeta {
  key: string
  label: string
  value: string | React.ReactNode
}

export interface StatusCardAction {
  key: string
  label: React.ReactNode
  onClick: () => void
  variant?: 'text' | 'outlined' | 'contained'
  color?: 'primary' | 'secondary' | 'error'
  disabled?: boolean
}

export interface StatusCardProps {
  /**
   * 卡片标题
   */
  title: string

  /**
   * 状态值（用于颜色映射）
   */
  status: string

  /**
   * 状态显示文案
   */
  statusLabel: React.ReactNode

  /**
   * 状态颜色（可选，默认根据 status 推断）
   */
  statusColor?: StatusColor

  /**
   * 卡片描述（可选）
   */
  description?: string

  /**
   * Meta 信息列表（key-value 对）
   */
  meta?: StatusCardMeta[]

  /**
   * 操作按钮
   */
  actions?: StatusCardAction[]

  /**
   * 点击卡片回调（可选）
   */
  onClick?: () => void

  /**
   * 图标/Logo（可选）
   */
  icon?: React.ReactNode
}

// ===================================
// Helper
// ===================================

function inferStatusColor(status: string | undefined): StatusColor {
  // Defensive check: handle undefined or null status
  if (!status || typeof status !== 'string') {
    return 'default'
  }

  const lowerStatus = status.toLowerCase()

  // Success
  if (['running', 'active', 'success', 'healthy', 'online', 'enabled'].includes(lowerStatus)) {
    return 'success'
  }

  // Warning
  if (['pending', 'warning', 'degraded', 'starting', 'stopping'].includes(lowerStatus)) {
    return 'warning'
  }

  // Error
  if (['error', 'failed', 'stopped', 'offline', 'disabled', 'unhealthy'].includes(lowerStatus)) {
    return 'error'
  }

  // Info
  if (['info', 'unknown', 'idle'].includes(lowerStatus)) {
    return 'info'
  }

  return 'default'
}

// ===================================
// Component
// ===================================

/**
 * StatusCard 组件
 *
 * 🎨 结构（强制）：
 * - Header: icon + title + status badge
 * - Body: description
 * - Meta: key-value 列表
 * - Actions: 按钮组
 *
 * 🔒 页面禁止自定义状态卡片
 */
export function StatusCard({
  title,
  status,
  statusLabel,
  statusColor,
  description,
  meta,
  actions,
  onClick,
  icon,
}: StatusCardProps) {
  const chipColor = statusColor || inferStatusColor(status)

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s',
        '&:hover': onClick ? {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        } : {},
      }}
      onClick={onClick}
    >
      <CardContent
        sx={{
          p: CARD_PADDING / 8,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header: Icon + Title + Status Badge */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          {icon && (
            <Box sx={{ flexShrink: 0, color: 'primary.main' }}>
              {icon}
            </Box>
          )}
          <Typography variant="h6" sx={{ fontWeight: 600, flex: 1 }}>
            {title}
          </Typography>
          <Chip
            label={statusLabel}
            color={chipColor}
            size="small"
            sx={{ fontWeight: 500 }}
          />
        </Box>

        {/* Description */}
        {description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mb: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {description}
          </Typography>
        )}

        {/* Meta */}
        {meta && meta.length > 0 && (
          <Box sx={{ mb: 2 }}>
            {meta.map((item) => (
              <Box
                key={item.key}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  mb: 0.5,
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {item.label}:
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 500 }}>
                  {item.value}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Actions */}
        {actions && actions.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            {actions.map((action) => (
              <Button
                key={action.key}
                variant={action.variant ?? 'text'}
                color={action.color}
                onClick={(e) => {
                  e.stopPropagation()
                  action.onClick()
                }}
                disabled={action.disabled}
                size="small"
                sx={{ flex: 1 }}
              >
                {action.label}
              </Button>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
