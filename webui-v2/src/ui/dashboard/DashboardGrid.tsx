/**
 * DashboardGrid - Dashboard 网格容器
 *
 * 🔒 Contract 强制规则：
 * - 无边框、无背景的外层容器
 * - 统一 padding/gap/布局
 * - 页面禁止自定义网格容器
 *
 * 使用示例：
 * ```tsx
 * <DashboardGrid columns={3} gap={16}>
 *   <StatCard title="Total Users" value="1,234" />
 *   <StatCard title="Active Sessions" value="89" />
 *   <MetricCard title="System Health" metrics={[...]} />
 * </DashboardGrid>
 * ```
 */

import React from 'react'
import { Grid, Skeleton, Card, CardContent, Box } from '@mui/material'
import { SECTION_GAP, CARD_PADDING } from '@/ui/layout/tokens'

// ===================================
// Types
// ===================================

export interface DashboardGridProps {
  /**
   * 子元素（卡片组件）
   */
  children: React.ReactNode

  /**
   * 网格列数（响应式）
   */
  columns?: 2 | 3 | 4

  /**
   * 卡片间距（默认：SECTION_GAP / 2）
   */
  gap?: number

  /**
   * 是否正在加载（显示 Skeleton）
   */
  loading?: boolean
}

// ===================================
// Helper Component - Dashboard Card Skeleton
// ===================================

/**
 * DashboardCardSkeleton - Dashboard 卡片骨架屏
 */
function DashboardCardSkeleton() {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: CARD_PADDING / 8 }}>
        {/* Header: Icon + Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Skeleton variant="text" width="60%" height={24} />
        </Box>

        {/* Main Value */}
        <Skeleton variant="text" width="50%" height={48} sx={{ mb: 1 }} />

        {/* Secondary Info */}
        <Skeleton variant="text" width="40%" height={20} />

        {/* Metrics (if MetricCard) */}
        <Box sx={{ mt: 2 }}>
          <Skeleton variant="text" width="90%" height={16} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width="85%" height={16} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width="80%" height={16} />
        </Box>
      </CardContent>
    </Card>
  )
}

// ===================================
// Component
// ===================================

/**
 * DashboardGrid 组件
 *
 * 🎨 结构（强制）：
 * - 响应式 Grid 布局
 * - 无边框、无背景
 * - 支持 loading 态（Skeleton）
 *
 * 🔒 页面禁止自定义网格容器
 */
export function DashboardGrid({
  children,
  columns = 3,
  gap = SECTION_GAP / 2, // 默认 16px
  loading = false,
}: DashboardGridProps) {
  // 计算响应式列宽
  const getColumnWidth = () => {
    switch (columns) {
      case 2:
        return { xs: 12, sm: 12, md: 6 }
      case 3:
        return { xs: 12, sm: 12, md: 6, lg: 4 }
      case 4:
        return { xs: 12, sm: 6, md: 4, lg: 3 }
      default:
        return { xs: 12, sm: 12, md: 6, lg: 4 }
    }
  }

  const columnWidth = getColumnWidth()

  // Loading 态：显示 Skeleton
  if (loading) {
    return (
      <Grid container spacing={gap / 8}>
        {Array.from({ length: columns * 2 }).map((_, index) => (
          <Grid item key={index} {...columnWidth}>
            <DashboardCardSkeleton />
          </Grid>
        ))}
      </Grid>
    )
  }

  // 正常态：显示内容
  return (
    <Grid container spacing={gap / 8}>
      {React.Children.map(children, (child, index) => (
        <Grid item key={index} {...columnWidth}>
          {child}
        </Grid>
      ))}
    </Grid>
  )
}
