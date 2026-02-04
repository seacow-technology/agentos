/**
 * UI Layout System - 统一出口
 *
 * 🔒 硬契约：所有 layout 相关必须从此处导入
 *
 * 包含：
 * - Layout Tokens（spacing、constants）
 * - PageHeader System（Provider、Hook、Component）
 * - Layout Primitives（PageSection、FormSurface、ListToolbar、EmptyState）
 */

// ===================================
// Tokens
// ===================================

export * from './tokens'

// ===================================
// PageHeader System
// ===================================

export {
  PageHeaderProvider,
  usePageHeader,
  usePageActions,
  usePageHeaderLegacy,
  PageHeader,
  type PageHeaderConfig,
  type PageHeaderData,
  type PageHeaderAction,
} from './PageHeaderProvider'
export { PageHeaderBar } from './PageHeaderBar'

// ===================================
// Layout Primitives
// ===================================

export { PageSection, type PageSectionProps } from './PageSection'
export { EmptyState, type EmptyStateProps, type EmptyStateAction } from './EmptyState'
export { FormSurface, type FormSurfaceProps } from './FormSurface'
export { ListToolbar, type ListToolbarProps } from './ListToolbar'
export { PageSkeleton, type PageSkeletonProps, type PageSkeletonVariant } from './PageSkeleton'
