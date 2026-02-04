/**
 * MetricCard - 多指标卡片
 *
 * 🔒 Contract 强制规则：
 * - 统一卡片外观（key-value 列表）
 * - 页面禁止自定义指标卡片样式
 *
 * 使用示例：
 * ```tsx
 * <MetricCard
 *   title="System Metrics"
 *   description="Current system performance indicators"
 *   metrics={[
 *     { key: 'cpu', label: 'CPU Usage', value: '45%' },
 *     { key: 'memory', label: 'Memory', value: '2.1 GB' },
 *   ]}
 *   actions={[
 *     { key: 'view', label: 'View Details', onClick: () => {} },
 *   ]}
 * />
 * ```
 */

import React from 'react'
import { Box, Card, CardContent, Typography, Button } from '@mui/material'
import { CARD_PADDING } from '@/ui/layout/tokens'

// ===================================
// Types
// ===================================

export interface MetricItem {
  key: string
  label: React.ReactNode
  value: React.ReactNode
  /**
   * 可选的值颜色（如 'success.main', 'error.main'）
   */
  valueColor?: string
}

export interface MetricCardAction {
  key: string
  label: React.ReactNode
  onClick: () => void
  variant?: 'text' | 'outlined' | 'contained'
  disabled?: boolean
}

export interface MetricCardProps {
  /**
   * 卡片标题
   */
  title: React.ReactNode

  /**
   * 指标列表（key-value 对）
   */
  metrics: MetricItem[]

  /**
   * 卡片描述（可选）
   */
  description?: React.ReactNode

  /**
   * 操作按钮（可选）
   */
  actions?: MetricCardAction[]

  /**
   * 点击卡片回调（可选）
   */
  onClick?: () => void
}

// ===================================
// Component
// ===================================

/**
 * MetricCard 组件
 *
 * 🎨 结构（强制）：
 * - Header: title + description
 * - Body: metrics（key-value 列表）
 * - Footer: actions
 *
 * 🔒 页面禁止自定义指标卡片
 */
export function MetricCard({
  title,
  metrics,
  description,
  actions,
  onClick,
}: MetricCardProps) {
  const isClickable = !!onClick

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: isClickable ? 'pointer' : 'default',
        transition: 'all 0.2s',
        '&:hover': isClickable ? {
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
        {/* Header: Title */}
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
          {title}
        </Typography>

        {/* Description */}
        {description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: 2 }}
          >
            {description}
          </Typography>
        )}

        {/* Metrics: key-value 列表 */}
        <Box sx={{ flex: 1 }}>
          {metrics.map((metric) => (
            <Box
              key={metric.key}
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                py: 1,
                borderBottom: (theme) => `1px solid ${theme.palette.divider}`,
                '&:last-child': {
                  borderBottom: 'none',
                },
              }}
            >
              <Typography variant="body2" color="text.secondary">
                {metric.label}
              </Typography>
              <Typography
                variant="body1"
                sx={{
                  fontWeight: 600,
                  color: metric.valueColor || 'text.primary',
                }}
              >
                {metric.value}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Actions */}
        {actions && actions.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            {actions.map((action) => (
              <Button
                key={action.key}
                variant={action.variant ?? 'text'}
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
