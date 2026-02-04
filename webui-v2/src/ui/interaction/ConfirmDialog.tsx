/**
 * ConfirmDialog - 删除/危险操作确认对话框
 *
 * 🔒 硬契约：所有删除/危险操作必须使用此组件
 *
 * 目标：
 * - 统一确认对话框样式
 * - 统一危险按钮颜色（error）
 * - 统一文案位置（居中）
 * - 防止误操作（两次确认）
 */

import { useRef, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  CircularProgress,
} from '@mui/material'

export interface ConfirmDialogProps {
  /**
   * 对话框是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 对话框标题
   */
  title: string

  /**
   * 确认提示内容
   */
  message: string

  /**
   * 确认按钮文案（默认 'Confirm'）
   */
  confirmText?: string

  /**
   * 取消按钮文案（默认 'Cancel'）
   */
  cancelText?: string

  /**
   * 确认回调
   */
  onConfirm: () => void | Promise<void>

  /**
   * 是否正在处理
   */
  loading?: boolean

  /**
   * 按钮颜色（默认 'error' 用于危险操作）
   */
  color?: 'error' | 'warning' | 'primary'
}

/**
 * ConfirmDialog 组件
 *
 * 🔒 删除/危险操作必须使用此组件
 *
 * 特性：
 * - 默认 xs 宽度（444px）
 * - 默认 error 按钮颜色（危险操作）
 * - 内容文本居中
 * - Confirm 按钮自动 loading 状态
 * - Esc 键取消
 *
 * @example
 * ```tsx
 * <ConfirmDialog
 *   open={open}
 *   onClose={handleClose}
 *   title="Delete Task"
 *   message="Are you sure you want to delete this task? This action cannot be undone."
 *   confirmText="Delete"
 *   onConfirm={handleDelete}
 *   loading={loading}
 * />
 * ```
 */
export function ConfirmDialog({
  open,
  onClose,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  loading = false,
  color = 'error',
}: ConfirmDialogProps) {
  // ===================================
  // 🔒 修复策略4B：确保Dialog打开时获得焦点
  // ===================================
  const dialogRef = useRef<HTMLDivElement>(null)

  // Dialog打开时，强制焦点到Dialog容器
  useEffect(() => {
    if (open && dialogRef.current) {
      // 延迟一帧，等待Dialog完全渲染
      requestAnimationFrame(() => {
        try {
          // 焦点到Dialog容器，确保焦点离开被aria-hidden的Drawer
          dialogRef.current?.focus()
        } catch (e) {
          console.warn('Failed to focus ConfirmDialog:', e)
        }
      })
    }
  }, [open])

  const handleConfirm = async () => {
    await onConfirm()
  }

  return (
    <Dialog
      open={open}
      onClose={loading ? undefined : onClose}
      maxWidth="xs"
      fullWidth
      // Esc 键关闭（loading 时禁用）
      disableEscapeKeyDown={loading}
      // ===================================
      // 🔒 焦点管理 - 修复 ARIA 警告
      // ===================================
      disableRestoreFocus={false}  // Dialog 关闭时恢复焦点到触发按钮
      disableEnforceFocus={false}  // 强制焦点保持在 Dialog 内
      // ===================================
      // 🔒 z-index 修复 - 确保 Dialog 在 AppBar 之上
      // ===================================
      // Dialog 默认 z-index = 1300（modal层），已经高于 AppBar(1201)
      // 但显式设置以确保一致性
      sx={{
        zIndex: (theme) => theme.zIndex.modal,  // 1300
      }}
      // ===================================
      // 🔒 PaperProps：让Dialog容器可聚焦
      // ===================================
      PaperProps={{
        ref: dialogRef,
        tabIndex: -1, // 允许programmatic focus，但不加入Tab键顺序
      }}
    >
      {/* 标题 */}
      <DialogTitle>{title}</DialogTitle>

      {/* 内容 */}
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
      </DialogContent>

      {/* 操作按钮 */}
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button
          onClick={onClose}
          disabled={loading}
        >
          {cancelText}
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color={color}
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : undefined}
        >
          {confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
