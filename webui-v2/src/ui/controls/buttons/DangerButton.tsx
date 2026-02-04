import { Button, CircularProgress } from '@mui/material'
import { ReactNode } from 'react'

export interface DangerButtonProps {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
  startIcon?: ReactNode
  endIcon?: ReactNode
  size?: 'small' | 'medium' | 'large'
  fullWidth?: boolean
  type?: 'button' | 'submit' | 'reset'
}

/**
 * DangerButton - 危险操作按钮
 *
 * Material Design 3 风格的危险操作按钮，使用 contained variant 和 error color。
 * 用于破坏性操作（如删除、清空、重置等需要用户谨慎确认的操作）。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 只暴露必要的功能性 props
 *
 * 建议：
 * - 通常与 ConfirmDialog 配合使用
 * - 避免在页面中使用过多，保持视觉层次
 *
 * @example
 * <DangerButton onClick={handleDelete}>
 *   Delete
 * </DangerButton>
 *
 * @example
 * <DangerButton loading startIcon={<DeleteIcon />}>
 *   Deleting...
 * </DangerButton>
 */
export function DangerButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  startIcon,
  endIcon,
  size = 'medium',
  fullWidth = false,
  type = 'button',
}: DangerButtonProps) {
  return (
    <Button
      variant="contained"
      color="error"
      onClick={onClick}
      disabled={disabled || loading}
      startIcon={loading ? <CircularProgress size={16} color="inherit" /> : startIcon}
      endIcon={endIcon}
      size={size}
      fullWidth={fullWidth}
      type={type}
    >
      {children}
    </Button>
  )
}
