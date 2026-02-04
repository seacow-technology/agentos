import { IconButton, Tooltip } from '@mui/material'
import { ReactNode } from 'react'

export interface IconOnlyButtonProps {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  size?: 'small' | 'medium' | 'large'
  color?: 'default' | 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'
  tooltip?: string
  edge?: 'start' | 'end' | false
}

/**
 * IconOnlyButton - 纯图标按钮
 *
 * Material Design 3 风格的图标按钮，用于仅需图标的操作场景。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 只暴露必要的功能性 props
 *
 * 建议：
 * - 始终提供 tooltip 以提高可访问性
 * - 用于工具栏、列表操作等紧凑场景
 *
 * @example
 * <IconOnlyButton tooltip="Delete" onClick={handleDelete}>
 *   <DeleteIcon />
 * </IconOnlyButton>
 *
 * @example
 * <IconOnlyButton color="primary" tooltip="Edit" onClick={handleEdit}>
 *   <EditIcon />
 * </IconOnlyButton>
 */
export function IconOnlyButton({
  children,
  onClick,
  disabled = false,
  size = 'medium',
  color = 'default',
  tooltip,
  edge = false,
}: IconOnlyButtonProps) {
  const button = (
    <IconButton
      onClick={onClick}
      disabled={disabled}
      size={size}
      color={color}
      edge={edge}
    >
      {children}
    </IconButton>
  )

  // 如果提供了 tooltip，包裹在 Tooltip 组件中
  if (tooltip) {
    return (
      <Tooltip title={tooltip}>
        <span>{button}</span>
      </Tooltip>
    )
  }

  return button
}
