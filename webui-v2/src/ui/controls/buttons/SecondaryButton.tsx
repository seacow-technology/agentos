import { Button, CircularProgress } from '@mui/material'
import { ReactNode } from 'react'

export interface SecondaryButtonProps {
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
 * SecondaryButton - 次要操作按钮
 *
 * Material Design 3 风格的次要操作按钮，使用 outlined variant 和 primary color。
 * 用于页面中的次要操作（如取消、返回、查看详情等）。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 只暴露必要的功能性 props
 *
 * @example
 * <SecondaryButton onClick={handleCancel}>
 *   Cancel
 * </SecondaryButton>
 *
 * @example
 * <SecondaryButton startIcon={<BackIcon />} onClick={handleBack}>
 *   Back to List
 * </SecondaryButton>
 */
export function SecondaryButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  startIcon,
  endIcon,
  size = 'medium',
  fullWidth = false,
  type = 'button',
}: SecondaryButtonProps) {
  return (
    <Button
      variant="outlined"
      color="primary"
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
