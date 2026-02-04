/**
 * DisableConfirmDialog - 禁用/停用确认对话框
 *
 * 基于 ConfirmDialog 封装的禁用确认对话框
 * 遵循 G7-G17 规范，使用 t(K.xxx) 多语言
 */

import { ConfirmDialog } from '../ConfirmDialog'
import { K, t } from '@/ui/text'

export interface DisableConfirmDialogProps {
  /**
   * 对话框是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 确认禁用回调
   */
  onConfirm: () => void | Promise<void>

  /**
   * 是否正在处理
   */
  loading?: boolean

  /**
   * 被禁用的资源类型（如 'Channel', 'Provider', 'Extension'）
   */
  resourceType: string

  /**
   * 被禁用的资源名称（可选）
   */
  resourceName?: string
}

/**
 * DisableConfirmDialog 组件
 *
 * 通用禁用/停用确认对话框
 *
 * 功能：
 * - 统一的禁用确认样式
 * - 支持自定义资源类型和名称
 * - 警告操作（warning 颜色）
 *
 * @example
 * ```tsx
 * <DisableConfirmDialog
 *   open={open}
 *   onClose={handleClose}
 *   onConfirm={handleDisable}
 *   loading={loading}
 *   resourceType="Channel"
 *   resourceName="Slack Integration"
 * />
 * ```
 */
export function DisableConfirmDialog({
  open,
  onClose,
  onConfirm,
  loading = false,
  resourceType,
  resourceName,
}: DisableConfirmDialogProps) {
  const title = t(K.component.dialog.disableTitle).replace('{type}', resourceType)

  const message = resourceName
    ? t(K.component.dialog.disableMessageWithName)
        .replace('{type}', resourceType)
        .replace('{name}', resourceName)
    : t(K.component.dialog.disableMessage).replace('{type}', resourceType)

  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      title={title}
      message={message}
      confirmText={t(K.component.dialog.disable)}
      cancelText={t(K.common.cancel)}
      onConfirm={onConfirm}
      loading={loading}
      color="warning"
    />
  )
}
