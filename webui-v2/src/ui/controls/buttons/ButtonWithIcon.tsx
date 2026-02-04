import { Button, CircularProgress } from '@mui/material'
import { ReactNode } from 'react'

export interface ButtonWithIconProps {
  children: ReactNode
  icon: ReactNode
  iconPosition?: 'start' | 'end'
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
  variant?: 'contained' | 'outlined' | 'text'
  color?: 'primary' | 'secondary' | 'error' | 'warning' | 'info' | 'success'
  size?: 'small' | 'medium' | 'large'
  fullWidth?: boolean
  type?: 'button' | 'submit' | 'reset'
}

/**
 * ButtonWithIcon - 图标文字按钮
 *
 * Material Design 3 风格的图标文字按钮，统一图标和文字的对齐与间距。
 * 适用于需要同时展示图标和文字的操作场景。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 只暴露必要的功能性 props
 *
 * 特点：
 * - 自动处理图标位置（start/end）
 * - 统一间距和对齐
 * - 支持 loading 状态
 *
 * @example
 * <ButtonWithIcon icon={<AddIcon />} onClick={handleCreate}>
 *   Create New
 * </ButtonWithIcon>
 *
 * @example
 * <ButtonWithIcon
 *   icon={<DownloadIcon />}
 *   iconPosition="end"
 *   variant="outlined"
 *   loading
 * >
 *   Downloading...
 * </ButtonWithIcon>
 */
export function ButtonWithIcon({
  children,
  icon,
  iconPosition = 'start',
  onClick,
  disabled = false,
  loading = false,
  variant = 'contained',
  color = 'primary',
  size = 'medium',
  fullWidth = false,
  type = 'button',
}: ButtonWithIconProps) {
  const loadingIcon = <CircularProgress size={16} color="inherit" />
  const displayIcon = loading ? loadingIcon : icon

  return (
    <Button
      variant={variant}
      color={color}
      onClick={onClick}
      disabled={disabled || loading}
      startIcon={iconPosition === 'start' ? displayIcon : undefined}
      endIcon={iconPosition === 'end' ? displayIcon : undefined}
      size={size}
      fullWidth={fullWidth}
      type={type}
    >
      {children}
    </Button>
  )
}
