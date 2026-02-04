/**
 * EmptyState - 空态统一组件
 *
 * 🔒 硬契约：所有空态必须使用此组件
 *
 * 目标：
 * - 统一空态位置、宽度、样式
 * - 防止页面自定义空态布局
 * - 确保按钮数量和对齐一致
 *
 * 使用场景：
 * - 空列表
 * - 空搜索结果
 * - 初次未配置（setup state）
 */

import { Box, Button, Typography } from '@mui/material'
import { K, useTextTranslation } from '@/ui/text'
import { EMPTY_STATE_MAX_WIDTH, EMPTY_STATE_OFFSET_TOP } from './tokens'

export interface EmptyStateAction {
  label: string
  onClick: () => void
  variant?: 'contained' | 'outlined' | 'text'
  disabled?: boolean
}

export interface EmptyStateProps {
  /**
   * 图标或插图（可选）
   */
  icon?: React.ReactNode

  /**
   * 标题（1行为佳）
   */
  title: string

  /**
   * 描述（最多2行）
   */
  description?: string

  /**
   * 操作按钮（最多2个）
   */
  actions?: EmptyStateAction[]

  /**
   * 链接（Learn more）
   */
  link?: {
    label: string
    href: string
  }
}

/**
 * EmptyState 组件
 *
 * 🔒 强制：空态必须使用此组件，禁止页面自己拼
 *
 * 位置与对齐（强制）：
 * - 在 PageBody 的内容宽度内居中
 * - 纵向位置：顶部下方 40px 起（不完全垂直居中）
 * - 宽度：最大 560px
 * - 按钮：最多 2 个
 *
 * @example
 * ```tsx
 * <EmptyState
 *   icon={<InboxIcon sx={{ fontSize: 64 }} />}
 *   title="No tasks yet"
 *   description="Create your first task to get started"
 *   actions={[
 *     { label: 'Create Task', onClick: handleCreate, variant: 'contained' }
 *   ]}
 * />
 * ```
 */
export function EmptyState({
  icon,
  title,
  description,
  actions = [],
  link,
}: EmptyStateProps) {
  const { t } = useTextTranslation()
  // 🔒 强制：最多2个按钮
  if (actions.length > 2) {
    console.warn(`[EmptyState] ${t(K.component.emptyState.tooManyActions)}`)
  }

  const displayActions = actions.slice(0, 2)

  return (
    <Box
      sx={{
        // 🔒 位置：顶部下方 40px
        mt: EMPTY_STATE_OFFSET_TOP / 8, // MUI 使用 8px base

        // 🔒 宽度：最大 560px，居中
        maxWidth: EMPTY_STATE_MAX_WIDTH,
        mx: 'auto',
        width: '100%',

        // 内边距
        px: 3,
        py: 4,

        // 文本居中
        textAlign: 'center',
      }}
    >
      {/* 图标或插图（可选） */}
      {icon && (
        <Box
          sx={{
            mb: 2,
            color: 'text.secondary',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
      )}

      {/* 标题 */}
      <Typography
        variant="h6"
        sx={{
          fontWeight: 600,
          color: 'text.primary',
          mb: description ? 1 : 0,
        }}
      >
        {title}
      </Typography>

      {/* 描述 */}
      {description && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: displayActions.length > 0 || link ? 3 : 0,
            maxWidth: 480,
            mx: 'auto',
          }}
        >
          {description}
        </Typography>
      )}

      {/* 操作按钮（最多2个） */}
      {displayActions.length > 0 && (
        <Box
          sx={{
            display: 'flex',
            gap: 1.5,
            justifyContent: 'center',
            flexWrap: 'wrap',
            mb: link ? 2 : 0,
          }}
        >
          {displayActions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || 'contained'}
              onClick={action.onClick}
              disabled={action.disabled}
            >
              {action.label}
            </Button>
          ))}
        </Box>
      )}

      {/* 链接（Learn more） */}
      {link && (
        <Typography variant="body2">
          <a
            href={link.href}
            style={{
              color: 'inherit',
              textDecoration: 'underline',
            }}
          >
            {link.label}
          </a>
        </Typography>
      )}
    </Box>
  )
}
