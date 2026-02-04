/**
 * PageSkeleton - 通用页面骨架屏
 *
 * 用于简单页面的 loading 状态，提供多种预设布局
 *
 * 使用示例：
 * ```tsx
 * if (loading) {
 *   return <PageSkeleton variant="content" />
 * }
 * ```
 */

import { Box, Card, CardContent, Skeleton } from '@mui/material'
import { SECTION_GAP, CARD_PADDING } from './tokens'

// ===================================
// Types
// ===================================

export type PageSkeletonVariant = 'content' | 'form' | 'detail' | 'console'

export interface PageSkeletonProps {
  /**
   * 骨架屏变体
   * - content: 通用内容页（默认）
   * - form: 表单页
   * - detail: 详情页
   * - console: 控制台页
   */
  variant?: PageSkeletonVariant
}

// ===================================
// Component
// ===================================

/**
 * PageSkeleton - 通用页面骨架屏
 *
 * 🎨 自动匹配页面布局，提供流畅的加载体验
 */
export function PageSkeleton({ variant = 'content' }: PageSkeletonProps) {
  // Content 变体：通用内容页
  if (variant === 'content') {
    return (
      <Box>
        {/* Section 1 */}
        <Card sx={{ mb: SECTION_GAP / 8 }}>
          <CardContent sx={{ p: CARD_PADDING / 8 }}>
            <Skeleton variant="text" width="30%" height={32} sx={{ mb: 2 }} />
            <Skeleton variant="text" width="100%" height={20} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="95%" height={20} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="85%" height={20} />
          </CardContent>
        </Card>

        {/* Section 2 */}
        <Card sx={{ mb: SECTION_GAP / 8 }}>
          <CardContent sx={{ p: CARD_PADDING / 8 }}>
            <Skeleton variant="text" width="25%" height={28} sx={{ mb: 2 }} />
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Skeleton variant="rectangular" width="48%" height={80} sx={{ borderRadius: 1 }} />
              <Skeleton variant="rectangular" width="48%" height={80} sx={{ borderRadius: 1 }} />
            </Box>
            <Skeleton variant="text" width="100%" height={20} sx={{ mb: 1 }} />
            <Skeleton variant="text" width="90%" height={20} />
          </CardContent>
        </Card>

        {/* Section 3 */}
        <Card>
          <CardContent sx={{ p: CARD_PADDING / 8 }}>
            <Skeleton variant="text" width="35%" height={28} sx={{ mb: 2 }} />
            <Skeleton variant="rectangular" width="100%" height={120} sx={{ borderRadius: 1 }} />
          </CardContent>
        </Card>
      </Box>
    )
  }

  // Form 变体：表单页
  if (variant === 'form') {
    return (
      <Card>
        <CardContent sx={{ p: CARD_PADDING / 8 }}>
          <Skeleton variant="text" width="40%" height={32} sx={{ mb: 3 }} />

          {/* Form Fields */}
          {Array.from({ length: 4 }).map((_, index) => (
            <Box key={index} sx={{ mb: 3 }}>
              <Skeleton variant="text" width="20%" height={20} sx={{ mb: 1 }} />
              <Skeleton variant="rectangular" width="100%" height={56} sx={{ borderRadius: 1 }} />
            </Box>
          ))}

          {/* Actions */}
          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 4 }}>
            <Skeleton variant="rectangular" width={100} height={40} sx={{ borderRadius: 1 }} />
            <Skeleton variant="rectangular" width={100} height={40} sx={{ borderRadius: 1 }} />
          </Box>
        </CardContent>
      </Card>
    )
  }

  // Detail 变体：详情页
  if (variant === 'detail') {
    return (
      <Box>
        {/* Header */}
        <Card sx={{ mb: SECTION_GAP / 8 }}>
          <CardContent sx={{ p: CARD_PADDING / 8 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
              <Skeleton variant="circular" width={56} height={56} />
              <Box sx={{ flex: 1 }}>
                <Skeleton variant="text" width="40%" height={32} sx={{ mb: 1 }} />
                <Skeleton variant="text" width="60%" height={20} />
              </Box>
            </Box>
          </CardContent>
        </Card>

        {/* Details */}
        <Card>
          <CardContent sx={{ p: CARD_PADDING / 8 }}>
            {Array.from({ length: 6 }).map((_, index) => (
              <Box key={index} sx={{ display: 'flex', mb: 2 }}>
                <Skeleton variant="text" width="30%" height={20} sx={{ mr: 2 }} />
                <Skeleton variant="text" width="50%" height={20} />
              </Box>
            ))}
          </CardContent>
        </Card>
      </Box>
    )
  }

  // Console 变体：控制台页
  if (variant === 'console') {
    return (
      <Card sx={{ height: '60vh' }}>
        <CardContent sx={{ p: CARD_PADDING / 8, height: '100%' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Skeleton variant="text" width="25%" height={28} sx={{ mr: 2 }} />
            <Skeleton variant="rectangular" width={100} height={32} sx={{ borderRadius: 1 }} />
          </Box>

          {/* Console Content */}
          <Skeleton variant="rectangular" width="100%" height="calc(100% - 80px)" sx={{ borderRadius: 1, bgcolor: 'action.hover' }} />

          {/* Input Area */}
          <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
            <Skeleton variant="rectangular" width="calc(100% - 100px)" height={48} sx={{ borderRadius: 1 }} />
            <Skeleton variant="rectangular" width={90} height={48} sx={{ borderRadius: 1 }} />
          </Box>
        </CardContent>
      </Card>
    )
  }

  return null
}
