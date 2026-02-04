/**
 * StatCard - 统计数字卡片
 *
 * 🔒 Contract 强制规则：
 * - 统一卡片外观（大数字 + 趋势）
 * - 页面禁止自定义统计卡片样式
 *
 * 使用示例：
 * ```tsx
 * <StatCard
 *   title="Total Users"
 *   value="1,234"
 *   change="+12%"
 *   changeType="increase"
 *   icon={<UsersIcon />}
 *   onClick={() => {}}
 * />
 * ```
 */

import React from 'react'
import { Box, Card, CardContent, Typography } from '@mui/material'
import { CARD_PADDING } from '@/ui/layout/tokens'
import { TrendingUpIcon, TrendingDownIcon } from '@/ui/icons'

// ===================================
// Types
// ===================================

export interface StatCardProps {
  /**
   * 卡片标题
   */
  title: React.ReactNode

  /**
   * 主要数值（大字）
   */
  value: React.ReactNode

  /**
   * 变化值（可选，如 "+12%" 或 "-5%"）
   */
  change?: React.ReactNode

  /**
   * 变化类型（影响颜色）
   */
  changeType?: 'increase' | 'decrease'

  /**
   * 图标（可选）
   */
  icon?: React.ReactNode

  /**
   * 点击回调（可选）
   */
  onClick?: () => void
}

// ===================================
// Component
// ===================================

/**
 * StatCard 组件
 *
 * 🎨 结构（强制）：
 * - Header: icon + title
 * - Value: 大数字
 * - Change: 趋势箭头 + 变化值
 *
 * 🔒 页面禁止自定义统计卡片
 */
export function StatCard({
  title,
  value,
  change,
  changeType,
  icon,
  onClick,
}: StatCardProps) {
  const isClickable = !!onClick

  // 变化类型对应的颜色
  const changeColor = changeType === 'increase' ? 'success.main' : changeType === 'decrease' ? 'error.main' : 'text.secondary'

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
        {/* Header: Icon + Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
          {icon && (
            <Box sx={{ flexShrink: 0, color: 'primary.main', fontSize: 28 }}>
              {icon}
            </Box>
          )}
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
            {title}
          </Typography>
        </Box>

        {/* Value: 大数字 */}
        <Typography variant="h3" sx={{ fontWeight: 700, mb: 1.5 }}>
          {value}
        </Typography>

        {/* Change: 趋势 */}
        {change && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {changeType === 'increase' && (
              <TrendingUpIcon sx={{ fontSize: 18, color: changeColor }} />
            )}
            {changeType === 'decrease' && (
              <TrendingDownIcon sx={{ fontSize: 18, color: changeColor }} />
            )}
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                color: changeColor,
              }}
            >
              {change}
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
