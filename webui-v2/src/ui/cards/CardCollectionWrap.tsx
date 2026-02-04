/**
 * CardCollectionWrap - 卡片集合容器
 *
 * 🔒 Contract 强制规则：
 * - 无边框、无背景的外层容器
 * - 统一 padding/gap/布局
 * - 页面禁止自定义卡片容器
 *
 * 使用示例：
 * ```tsx
 * <CardCollectionWrap loading={loading}>
 *   {items.map(item => (
 *     <ItemCard key={item.id} {...item} />
 *   ))}
 * </CardCollectionWrap>
 * ```
 */

import React from 'react'
import { Box, Card, CardContent, Skeleton } from '@mui/material'
import { SECTION_GAP, CARD_PADDING } from '@/ui/layout/tokens'

// ===================================
// Types
// ===================================

export interface CardCollectionWrapProps {
  /**
   * 卡片内容
   */
  children: React.ReactNode

  /**
   * 是否正在加载
   */
  loading?: boolean

  /**
   * 布局模式
   * - grid: 网格布局（默认）
   * - list: 列表布局
   */
  layout?: 'grid' | 'list'

  /**
   * 网格列数（仅 grid 模式）
   * - 2: 两列
   * - 3: 三列（默认）
   * - 4: 四列
   */
  columns?: 2 | 3 | 4

  /**
   * 卡片间距（默认 16px）
   */
  gap?: number
}

// ===================================
// Component
// ===================================

// ===================================
// Helper Component - Card Skeleton
// ===================================

/**
 * CardSkeleton - 卡片骨架屏
 */
function CardSkeleton() {
  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ p: CARD_PADDING / 8, flex: 1 }}>
        {/* Header: Icon + Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Skeleton variant="text" width="60%" height={28} />
        </Box>

        {/* Description */}
        <Skeleton variant="text" width="100%" height={20} sx={{ mb: 0.5 }} />
        <Skeleton variant="text" width="80%" height={20} sx={{ mb: 2 }} />

        {/* Meta */}
        <Box sx={{ mb: 2 }}>
          <Skeleton variant="text" width="70%" height={16} sx={{ mb: 0.5 }} />
          <Skeleton variant="text" width="60%" height={16} />
        </Box>

        {/* Tags */}
        <Box sx={{ display: 'flex', gap: 0.5, mb: 2 }}>
          <Skeleton variant="rounded" width={60} height={24} />
          <Skeleton variant="rounded" width={80} height={24} />
        </Box>

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Actions */}
        <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
          <Skeleton variant="rounded" width="50%" height={32} />
          <Skeleton variant="rounded" width="50%" height={32} />
        </Box>
      </CardContent>
    </Card>
  )
}

/**
 * CardCollectionWrap 组件
 *
 * 🎨 设计原则：
 * - 无边框、无背景、无 shadow
 * - 统一间距和排列
 * - 响应式布局
 *
 * 🔒 页面禁止自己布局卡片
 */
export function CardCollectionWrap({
  children,
  loading = false,
  layout = 'grid',
  columns = 3,
  gap = 16,
}: CardCollectionWrapProps) {
  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: {
      xs: '1fr',
      sm: columns >= 2 ? 'repeat(2, 1fr)' : '1fr',
      md: columns >= 3 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)',
      lg: `repeat(${columns}, 1fr)`,
    },
    gap: gap / 8, // MUI 使用 8px base
    mb: SECTION_GAP / 8,
  }

  const listStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: gap / 8,
    mb: SECTION_GAP / 8,
  }

  // Loading 状态：显示骨架屏
  if (loading) {
    const skeletonCount = columns * 2 // 显示 2 行骨架卡片
    return (
      <Box sx={layout === 'grid' ? gridStyle : listStyle}>
        {Array.from({ length: skeletonCount }).map((_, index) => (
          <CardSkeleton key={index} />
        ))}
      </Box>
    )
  }

  // Grid 布局
  if (layout === 'grid') {
    return <Box sx={gridStyle}>{children}</Box>
  }

  // List 布局
  return <Box sx={listStyle}>{children}</Box>
}
