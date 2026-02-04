import { Button, CircularProgress } from '@mui/material'
import { ReactNode } from 'react'

export interface PrimaryButtonProps {
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
 * PrimaryButton - 主要操作按钮
 *
 * Material Design 3 风格的主要操作按钮，使用 contained variant 和 primary color。
 * 用于页面中最重要的操作（如保存、提交、创建等）。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 只暴露必要的功能性 props
 *
 * @example
 * <PrimaryButton onClick={handleSave}>
 *   Save Changes
 * </PrimaryButton>
 *
 * @example
 * <PrimaryButton loading startIcon={<SaveIcon />}>
 *   Saving...
 * </PrimaryButton>
 */
export function PrimaryButton({
  children,
  onClick,
  disabled = false,
  loading = false,
  startIcon,
  endIcon,
  size = 'medium',
  fullWidth = false,
  type = 'button',
}: PrimaryButtonProps) {
  return (
    <Button
      variant="contained"
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
