/**
 * UI Layout Tokens
 *
 * 🔒 硬契约：所有 spacing 只能引用这些 token
 *
 * 目标：
 * - 统一间距体系
 * - 防止魔法数字
 * - 确保视觉一致性
 */

// ===================================
// Spacing Scale (8px base)
// ===================================

export const spacing = {
  s0: 0,
  s1: 4,
  s2: 8,
  s3: 12,
  s4: 16,
  s5: 24,
  s6: 32,
  s7: 40,
  s8: 48,
} as const

// ===================================
// Shell Constants
// ===================================

/**
 * 🎨 SHELL_GAP - 壳子统一外边距
 *
 * 用于 AppBar、Footer 的外边距，营造"悬浮卡片"感
 * 12px 比 8px 悬浮感更强
 */
export const SHELL_GAP = 12

/**
 * 🎨 SURFACE_RADIUS - 悬浮表面圆角
 *
 * 用于 AppBar、Footer、Card 等悬浮表面
 */
export const SURFACE_RADIUS = 8  // Unified to 8px

/**
 * 🎨 DRAWER_WIDTH - Sidebar 宽度
 */
export const DRAWER_WIDTH = 360

/**
 * 🎨 APPBAR_HEIGHT - AppBar 高度
 *
 * MUI 默认 Toolbar 高度
 */
export const APPBAR_HEIGHT = 64

/**
 * 🔒 SHELL_SURFACE - 壳子悬浮表面统一样式
 *
 * 用于 AppBar、PageHeaderBar、FooterBar 的统一悬浮效果
 * 🔒 禁止局部覆写，必须整体引用
 *
 * 包含：
 * - gap: SHELL_GAP (12px)
 * - borderRadius: SURFACE_RADIUS / 8 (1.5 for MUI)
 * - elevation: 2
 */
export const SHELL_SURFACE = {
  /**
   * 外边距（用于 mx/mb/mt）
   */
  gap: SHELL_GAP,

  /**
   * 圆角（MUI 单位，需要除以 8）
   */
  borderRadius: SURFACE_RADIUS / 8,

  /**
   * 阴影等级
   */
  elevation: 2,
} as const

/**
 * 🔒 SHELL_SURFACE_SX - 壳子悬浮表面统一 sx 样式
 *
 * 用于 AppBar、PageHeaderBar、FooterBar 的 Paper 组件
 * 🔒 三处必须完全复用此对象，禁止散写
 *
 * 包含：
 * - borderRadius: SURFACE_RADIUS / 8 (1.0 MUI 单位 = 8px, unified)
 * - overflow: 'hidden' (让圆角生效)
 * - border: 1px solid divider (缓解"下边阴影更重"的视觉错觉)
 */
export const SHELL_SURFACE_SX = {
  borderRadius: SURFACE_RADIUS / 8,  // MUI 单位：8 / 8 = 1.0 (unified to 8px)
  overflow: 'hidden',
  border: (theme: any) => `1px solid ${theme.palette.divider}`,
} as const

// ===================================
// Content Layout Constants
// ===================================

/**
 * 🔒 CONTENT_MAX_WIDTH - 内容区最大宽度
 *
 * 固定值，页面无法改变
 */
export const CONTENT_MAX_WIDTH = 1200

/**
 * 🔒 PAGE_GUTTER - 页面左右 padding
 *
 * 全局 gutter，页面不允许自定义
 */
export const PAGE_GUTTER = spacing.s5 // 24px

/**
 * 🔒 SECTION_GAP - Section 间距
 *
 * 同一页内容块之间的间距
 */
export const SECTION_GAP = spacing.s6 // 32px

/**
 * 🔒 CARD_PADDING - Card 内边距
 *
 * 默认卡片内边距
 */
export const CARD_PADDING = spacing.s5 // 24px

/**
 * 🔒 CARD_PADDING_DENSE - 紧凑卡片内边距
 */
export const CARD_PADDING_DENSE = spacing.s4 // 16px

/**
 * 🔒 FIELD_SPACING - 表单字段垂直间距
 */
export const FIELD_SPACING = spacing.s4 // 16px

/**
 * 🔒 TOOLBAR_GAP - Toolbar 与内容之间的间距
 */
export const TOOLBAR_GAP = spacing.s4 // 16px

// ===================================
// Page Specific Constants
// ===================================

/**
 * 🔒 FORM_SURFACE_MAX_WIDTH - 表单表面最大宽度
 *
 * 表单建议宽度：720px-860px（居中）
 */
export const FORM_SURFACE_MAX_WIDTH = 860

/**
 * 🔒 EMPTY_STATE_MAX_WIDTH - 空态最大宽度
 */
export const EMPTY_STATE_MAX_WIDTH = 560

/**
 * 🔒 EMPTY_STATE_OFFSET_TOP - 空态顶部偏移
 *
 * 不完全垂直居中，留出顶部空间
 */
export const EMPTY_STATE_OFFSET_TOP = spacing.s7 // 40px

// ===================================
// Responsive Breakpoints Adjustments
// ===================================

/**
 * 移动端调整
 */
export const mobile = {
  SHELL_GAP: spacing.s3, // 12px -> 减少为移动端留空间
  PAGE_GUTTER: spacing.s4, // 24px -> 16px
} as const

// ===================================
// Export All
// ===================================

export const layoutTokens = {
  spacing,
  SHELL_GAP,
  SURFACE_RADIUS,
  DRAWER_WIDTH,
  APPBAR_HEIGHT,
  CONTENT_MAX_WIDTH,
  PAGE_GUTTER,
  SECTION_GAP,
  CARD_PADDING,
  CARD_PADDING_DENSE,
  FIELD_SPACING,
  TOOLBAR_GAP,
  FORM_SURFACE_MAX_WIDTH,
  EMPTY_STATE_MAX_WIDTH,
  EMPTY_STATE_OFFSET_TOP,
  mobile,
} as const

export type LayoutTokens = typeof layoutTokens
