/**
 * PageHeader System v2.4
 *
 * 🔒 硬契约：页面标题必须由 Layout 统一控制
 *
 * 🎯 v2.4 改进：分离 actions API，避免引用抖动
 *
 * 目标：
 * - 页面只传参数（title、subtitle）
 * - actions 独立注册，避免引用不稳定导致的更新
 * - Layout 统一渲染（高度、间距、按钮位置固定）
 * - 防止页面自定义 header 布局
 *
 * 使用方式：
 * ```tsx
 * // 在页面中
 * usePageHeader({
 *   title: 'Task List',
 *   subtitle: 'Manage and track all tasks',
 * })
 *
 * // actions 独立注册（可选）
 * usePageActions([
 *   { key: 'export', label: 'Export', onClick: handleExport },
 *   { key: 'new', label: 'New', variant: 'contained', onClick: handleNew },
 * ])
 * ```
 */

import React from 'react'
import { Box, Typography, Button } from '@mui/material'

// ===================================
// Types
// ===================================

/**
 * PageHeaderAction - 页面操作按钮（声明式）
 *
 * 🔒 G18 硬契约：页面不能传 ReactNode，只能传声明式结构
 *
 * 目标：
 * - Layout 统一渲染按钮（variant/spacing/icon 位置）
 * - 页面只能传 label/onClick/intent，无法传 sx/style
 * - label 支持 T.xxx 或 t() 结果（ReactNode），禁止直接传 string
 */
export interface PageHeaderAction {
  /**
   * 唯一标识
   */
  key: string

  /**
   * 按钮文案（ReactNode，支持 T.xxx）
   * 🔒 禁止直接传 string，必须用 T.xxx 或 t(K.xxx)
   */
  label: React.ReactNode

  /**
   * 图标（可选）
   */
  icon?: React.ReactNode

  /**
   * 点击回调
   */
  onClick: () => void

  /**
   * 按钮变体（默认 'text'）
   */
  variant?: 'text' | 'outlined' | 'contained'

  /**
   * 按钮颜色（默认 'primary'）
   */
  color?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'

  /**
   * 是否禁用
   */
  disabled?: boolean

  /**
   * 是否正在加载
   */
  loading?: boolean
}

/**
 * 🎯 v2.4: PageHeaderData - 只包含纯数据字段
 *
 * 不包含 actions，actions 用 usePageActions 独立注册
 */
export interface PageHeaderData {
  /**
   * 页面标题（ReactNode，支持 T.xxx）
   * 🔒 禁止直接传 string，必须用 T.xxx 或 t(K.xxx)
   */
  title?: React.ReactNode

  /**
   * 页面副标题（ReactNode，支持 T.xxx）
   * 🔒 禁止直接传 string，必须用 T.xxx 或 t(K.xxx)
   */
  subtitle?: React.ReactNode
}

/**
 * 向后兼容：旧版 API（包含 actions）
 * @deprecated 建议使用 usePageHeader + usePageActions 分离 API
 */
export interface PageHeaderConfig extends PageHeaderData {
  actions?: PageHeaderAction[]
}

interface PageHeaderContextValue {
  // 数据字段（title/subtitle）
  headerData: PageHeaderData
  setHeaderData: (data: PageHeaderData) => void

  // actions 字段（独立管理）
  actions: PageHeaderAction[]
  setActions: (actions: PageHeaderAction[]) => void
}

// ===================================
// Context
// ===================================

export const PageHeaderContext = React.createContext<PageHeaderContextValue | null>(null)

// ===================================
// Provider
// ===================================

/**
 * Shallow compare 辅助函数（只比较 title/subtitle）
 */
function shallowEqualHeaderData(a: PageHeaderData, b: PageHeaderData): boolean {
  return a.title === b.title && a.subtitle === b.subtitle
}

export function PageHeaderProvider({ children }: { children: React.ReactNode }) {
  // 状态 1: 数据字段（title/subtitle）
  const [headerData, setHeaderDataState] = React.useState<PageHeaderData>({})

  // 状态 2: actions（使用 ref + state 组合，避免引用比较）
  const actionsRef = React.useRef<PageHeaderAction[]>([])
  const [actionsVersion, setActionsVersion] = React.useState(0)

  const setHeaderData = React.useCallback((data: PageHeaderData) => {
    setHeaderDataState(prev => {
      // 只比较 title/subtitle
      if (shallowEqualHeaderData(prev, data)) {
        return prev
      }
      return data
    })
  }, [])

  const setActions = React.useCallback((actions: PageHeaderAction[]) => {
    actionsRef.current = actions
    // 触发更新（用版本号，不用 actions 本身）
    setActionsVersion(v => v + 1)
  }, [])

  // 🔒 用 useMemo 包裹 value，避免每次 render 都创建新对象
  const value = React.useMemo(() => ({
    headerData,
    setHeaderData,
    actions: actionsRef.current,
    setActions,
  }), [headerData, setHeaderData, actionsVersion, setActions])

  return (
    <PageHeaderContext.Provider value={value}>
      {children}
    </PageHeaderContext.Provider>
  )
}

// ===================================
// Hook - usePageHeader (v2.4 新 API)
// ===================================

/**
 * 🎯 v2.4 新 API：只设置 title/subtitle
 *
 * 页面使用此 hook 设置 header 数据
 *
 * @example
 * ```tsx
 * import { T } from '@/ui/text'
 *
 * usePageHeader({
 *   title: T.page.tasks.title,
 *   subtitle: T.page.tasks.subtitle,
 * })
 * ```
 */
export function usePageHeader(data: PageHeaderData) {
  const context = React.useContext(PageHeaderContext)

  if (!context) {
    throw new Error('usePageHeader must be used within PageHeaderProvider')
  }

  React.useEffect(() => {
    context.setHeaderData(data)
  }, [data.title, data.subtitle, context.setHeaderData])
}

// ===================================
// Hook - usePageActions (v2.4 新 API)
// ===================================

/**
 * 🎯 v2.4 新 API：独立注册 actions
 *
 * actions 独立管理，不会因为引用变化导致 headerData 更新
 *
 * @example
 * ```tsx
 * import { T } from '@/ui/text'
 *
 * usePageActions([
 *   {
 *     key: 'export',
 *     label: T.common.export,
 *     variant: 'outlined',
 *     onClick: handleExport,
 *   },
 *   {
 *     key: 'new',
 *     label: T.common.create,
 *     variant: 'contained',
 *     onClick: handleNew,
 *   },
 * ])
 * ```
 */
export function usePageActions(actions: PageHeaderAction[]) {
  const context = React.useContext(PageHeaderContext)

  if (!context) {
    throw new Error('usePageActions must be used within PageHeaderProvider')
  }

  // 🔒 使用 ref 存储最新值
  const actionsRef = React.useRef(actions)
  actionsRef.current = actions

  // 🎯 v2.5: 依赖 keys + labels（支持 i18n 切换）
  // 当 label 变化时（如语言切换），需要触发更新
  const actionsSignature = React.useMemo(
    () => actions.map(a => `${a.key}:${typeof a.label === 'string' ? a.label : ''}`).join('|'),
    [actions]
  )

  React.useEffect(() => {
    context.setActions(actionsRef.current)
    // 🔒 不在 cleanup 中清理，让下一个页面覆盖即可
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionsSignature])  // ← 只依赖 signature，不依赖 context
}

// ===================================
// Hook - usePageHeaderLegacy (向后兼容)
// ===================================

/**
 * 向后兼容：旧版 API（包含 actions）
 *
 * @deprecated 建议使用 usePageHeader + usePageActions 分离 API
 */
export function usePageHeaderLegacy(config: PageHeaderConfig) {
  usePageHeader({
    title: config.title,
    subtitle: config.subtitle,
  })

  if (config.actions) {
    usePageActions(config.actions)
  }
}

// ===================================
// Component - PageHeader
// ===================================

/**
 * PageHeader 组件
 *
 * 🔒 v2.3: 无皮肤组件，必须被 AppBar HeaderSurface 包住
 *
 * 特性：
 * - 禁止使用 Paper / Container / elevation / boxShadow / borderRadius
 * - 只负责排版，不负责悬浮
 * - 宽度跟随 Layout token (CONTENT_MAX_WIDTH)
 * - 页面只传 title/subtitle/actions，不传 spacing/layout props
 */
export function PageHeader() {
  const context = React.useContext(PageHeaderContext)
  const headerData = context?.headerData ?? {}
  const actions = context?.actions ?? []

  // 没设置就不显示（Home landing 这种页面）
  if (!headerData.title && !headerData.subtitle && actions.length === 0) {
    return null
  }

  return (
    <Box
      sx={{
        // 🎨 v2.3: 移除 mt，spacing 由 AppBar Paper 控制
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      {/* 标题区 */}
      <Box sx={{ minWidth: 0, flex: 1 }}>
        {headerData.title && (
          <Typography
            variant="h5"
            sx={{
              fontWeight: 700,
              lineHeight: 1.2,
              color: 'text.primary',
            }}
          >
            {headerData.title}
          </Typography>
        )}
        {headerData.subtitle && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 0.5 }}
          >
            {headerData.subtitle}
          </Typography>
        )}
      </Box>

      {/* 操作区 */}
      {actions.length > 0 && (
        <Box
          sx={{
            flexShrink: 0,
            display: 'flex',
            gap: 1.5,
            alignItems: 'center',
          }}
        >
          {actions.map((action) => (
            <Button
              key={action.key}
              variant={action.variant ?? 'text'}
              color={action.color ?? 'primary'}
              onClick={(event) => {
                // ✅ 在调用用户 onClick 前，主动 blur 当前按钮
                // 防止按钮在打开 Dialog/Drawer 后仍持有焦点，触发 ARIA 警告
                if (event.currentTarget instanceof HTMLElement) {
                  event.currentTarget.blur()
                }
                action.onClick?.()
              }}
              disabled={action.disabled || action.loading}
              startIcon={action.icon}
            >
              {action.label}
            </Button>
          ))}
        </Box>
      )}
    </Box>
  )
}
