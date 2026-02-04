/**
 * UI Interaction System - 统一出口
 *
 * 🔒 硬契约：所有用户交互必须从此处导入
 *
 * 包含：
 * - DialogForm（新增/编辑统一对话框）
 * - ConfirmDialog（删除/危险操作确认对话框）
 * - DeleteConfirmDialog（删除确认对话框的便捷包装）
 * - DetailDrawer（详情统一抽屉）
 * - CreateTaskDialog（创建任务对话框）
 */

export { DialogForm, type DialogFormProps } from './DialogForm'
export { ConfirmDialog, type ConfirmDialogProps } from './ConfirmDialog'
export { DeleteConfirmDialog, type DeleteConfirmDialogProps } from './DeleteConfirmDialog'
export { DetailDrawer, type DetailDrawerProps } from './DetailDrawer'
export { CreateTaskDialog, type CreateTaskDialogProps, type CreateTaskRequest } from './CreateTaskDialog'
