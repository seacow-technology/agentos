/**
 * DeleteConfirmDialog - 通用删除确认对话框
 *
 * 基于 ConfirmDialog 封装的删除确认对话框
 * 遵循 G7-G17 规范，使用 t(K.xxx) 多语言
 */

import { ConfirmDialog } from '../ConfirmDialog'
import { K, t } from '@/ui/text'

export interface DeleteConfirmDialogProps {
  /**
   * 对话框是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 确认删除回调
   */
  onConfirm: () => void | Promise<void>

  /**
   * 是否正在处理
   */
  loading?: boolean

  /**
   * 被删除的资源类型（如 'Project', 'Task', 'Skill'）
   */
  resourceType: string

  /**
   * 被删除的资源名称（可选，用于更友好的提示）
   */
  resourceName?: string
}

/**
 * DeleteConfirmDialog 组件
 *
 * 通用删除确认对话框，适用于各类资源的删除操作
 *
 * 功能：
 * - 统一的删除确认样式
 * - 支持自定义资源类型和名称
 * - 危险操作警告（error 颜色）
 *
 * @example
 * ```tsx
 * <DeleteConfirmDialog
 *   open={open}
 *   onClose={handleClose}
 *   onConfirm={handleDelete}
 *   loading={loading}
 *   resourceType="Project"
 *   resourceName="My Project"
 * />
 * ```
 */
export function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  loading = false,
  resourceType,
  resourceName,
}: DeleteConfirmDialogProps) {
  const title = t(K.component.dialog.deleteTitle).replace('{type}', resourceType)

  const message = resourceName
    ? t(K.component.dialog.deleteMessageWithName)
        .replace('{type}', resourceType)
        .replace('{name}', resourceName)
    : t(K.component.dialog.deleteMessage).replace('{type}', resourceType)

  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      title={title}
      message={message}
      confirmText={t(K.common.delete)}
      cancelText={t(K.common.cancel)}
      onConfirm={onConfirm}
      loading={loading}
      color="error"
    />
  )
}
