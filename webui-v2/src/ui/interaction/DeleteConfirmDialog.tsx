/**
 * DeleteConfirmDialog - 删除确认对话框（ConfirmDialog的便捷包装）
 *
 * 专门用于删除操作的确认对话框，自动生成标准化的删除确认文案。
 */

import { ConfirmDialog } from './ConfirmDialog'

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
   * 确认回调
   */
  onConfirm: () => void | Promise<void>

  /**
   * 资源类型（如 "Task", "Project", "User"）
   */
  resourceType: string

  /**
   * 资源名称（可选，用于显示在确认消息中）
   */
  resourceName?: string

  /**
   * 是否正在处理
   */
  loading?: boolean

  /**
   * 确认按钮文案（默认 'Delete'）
   */
  confirmText?: string

  /**
   * 取消按钮文案（默认 'Cancel'）
   */
  cancelText?: string
}

/**
 * DeleteConfirmDialog 组件
 *
 * 删除操作的便捷包装，自动生成标准化文案：
 * - 有资源名称: "Delete {type} - Are you sure you want to delete {type} "{name}"?"
 * - 无资源名称: "Delete {type} - Are you sure you want to delete this {type}?"
 *
 * @example
 * ```tsx
 * <DeleteConfirmDialog
 *   open={open}
 *   onClose={handleClose}
 *   onConfirm={handleDelete}
 *   resourceType="Task"
 *   resourceName="Complete Phase 3"
 *   loading={loading}
 * />
 * ```
 */
export function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  resourceType,
  resourceName,
  loading = false,
  confirmText = 'Delete',
  cancelText = 'Cancel',
}: DeleteConfirmDialogProps) {
  // 生成标题
  const title = `Delete ${resourceType}`

  // 生成消息
  const message = resourceName
    ? `Are you sure you want to delete ${resourceType} "${resourceName}"? This action cannot be undone.`
    : `Are you sure you want to delete this ${resourceType}? This action cannot be undone.`

  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      title={title}
      message={message}
      confirmText={confirmText}
      cancelText={cancelText}
      onConfirm={onConfirm}
      loading={loading}
      color="error"
    />
  )
}
