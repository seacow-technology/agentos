/**
 * DialogForm - 新增/编辑统一对话框
 *
 * 🔒 硬契约：所有新增/编辑操作必须使用此组件
 *
 * 目标：
 * - 统一对话框样式（宽度、padding、按钮位置）
 * - 统一表单布局（Grid spacing=2）
 * - 统一按钮文案（Submit/Cancel）
 * - 统一 loading/error 状态
 */

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Box,
  CircularProgress,
} from '@mui/material'
import { CloseIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'

export interface DialogFormProps {
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
   * 提交按钮文案（默认 'Submit'）
   */
  submitText?: string

  /**
   * 取消按钮文案（默认 'Cancel'）
   */
  cancelText?: string

  /**
   * 提交回调
   */
  onSubmit: () => void | Promise<void>

  /**
   * 是否正在提交
   */
  loading?: boolean

  /**
   * 提交按钮是否禁用
   */
  submitDisabled?: boolean

  /**
   * 对话框最大宽度（默认 'sm'）
   */
  maxWidth?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'

  /**
   * 表单内容
   */
  children: React.ReactNode
}

/**
 * DialogForm 组件
 *
 * 🔒 新增/编辑操作必须使用此组件
 *
 * 特性：
 * - 默认 sm 宽度（600px）
 * - 标题右侧自动带关闭按钮
 * - 底部统一按钮布局（Cancel + Submit）
 * - Submit 按钮自动 loading 状态
 * - Esc 键关闭
 *
 * @example
 * ```tsx
 * <DialogForm
 *   open={open}
 *   onClose={handleClose}
 *   title="Create Task"
 *   submitText="Create"
 *   onSubmit={handleSubmit}
 *   loading={loading}
 * >
 *   <Grid container spacing={2}>
 *     <Grid item xs={12}>
 *       <TextField label="Name" fullWidth />
 *     </Grid>
 *     <Grid item xs={12} md={6}>
 *       <TextField label="Priority" fullWidth />
 *     </Grid>
 *   </Grid>
 * </DialogForm>
 * ```
 */
export function DialogForm({
  open,
  onClose,
  title,
  submitText,
  cancelText,
  onSubmit,
  loading = false,
  submitDisabled = false,
  maxWidth = 'sm',
  children,
}: DialogFormProps) {
  const { t } = useTextTranslation()
  const submitLabel = submitText ?? t(K.common.submit)
  const cancelLabel = cancelText ?? t(K.common.cancel)
  const handleSubmit = async () => {
    await onSubmit()
  }

  return (
    <Dialog
      open={open}
      onClose={loading ? undefined : onClose}
      maxWidth={maxWidth}
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
      sx={{
        zIndex: (theme) => theme.zIndex.modal,  // 1300
      }}
    >
      {/* 标题栏 */}
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        <Box component="span">{title}</Box>
        {/* 关闭按钮 */}
        <IconButton
          aria-label={t(K.common.close)}
          onClick={onClose}
          disabled={loading}
          size="small"
          sx={{ ml: 1 }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      {/* 内容区 */}
      <DialogContent dividers sx={{ pt: 2 }}>
        {children}
      </DialogContent>

      {/* 操作按钮 */}
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading || submitDisabled}
          startIcon={loading ? <CircularProgress size={16} /> : undefined}
        >
          {submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
