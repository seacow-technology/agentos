/**
 * Toast - 全局通知系统
 *
 * 🔒 硬契约：所有操作提醒必须使用 toast
 *
 * 目标：
 * - 统一成功/失败/警告/信息提示
 * - 统一位置、时长、样式
 * - 禁止使用 alert/confirm/prompt
 * - 禁止页面自己渲染 snackbar
 *
 * 使用方式：
 * ```tsx
 * import { toast } from '@/ui/feedback'
 *
 * toast.success('Task created successfully')
 * toast.error('Failed to delete task')
 * toast.warning('Changes not saved')
 * toast.info('New version available')
 * ```
 */

import { enqueueSnackbar, closeSnackbar } from 'notistack'

// ===================================
// Types
// ===================================

export interface ToastOptions {
  /**
   * 持续时长（毫秒）
   */
  duration?: number
}

// ===================================
// Toast API
// ===================================

/**
 * 显示成功提示
 */
function success(message: string, options?: ToastOptions) {
  return enqueueSnackbar(message, {
    variant: 'success',
    autoHideDuration: options?.duration || 3000,
  })
}

/**
 * 显示错误提示
 */
function error(message: string, options?: ToastOptions) {
  return enqueueSnackbar(message, {
    variant: 'error',
    autoHideDuration: options?.duration || 5000, // 错误提示时间更长
  })
}

/**
 * 显示警告提示
 */
function warning(message: string, options?: ToastOptions) {
  return enqueueSnackbar(message, {
    variant: 'warning',
    autoHideDuration: options?.duration || 4000,
  })
}

/**
 * 显示信息提示
 */
function info(message: string, options?: ToastOptions) {
  return enqueueSnackbar(message, {
    variant: 'info',
    autoHideDuration: options?.duration || 3000,
  })
}

/**
 * 关闭指定 toast
 */
function close(key: string | number) {
  closeSnackbar(key)
}

/**
 * 🔒 Toast 统一出口
 *
 * 禁止项：
 * - ❌ window.alert()
 * - ❌ window.confirm()
 * - ❌ window.prompt()
 * - ❌ 自己渲染 Snackbar
 *
 * 正确用法：
 * - ✅ toast.success('...')
 * - ✅ toast.error('...')
 * - ✅ toast.warning('...')
 * - ✅ toast.info('...')
 */
export const toast = {
  success,
  error,
  warning,
  info,
  close,
}
