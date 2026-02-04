/**
 * CreateTaskDialog - 创建任务对话框
 *
 * 基于 DialogForm 封装的任务创建对话框
 * 遵循 G7-G17 规范，使用 t(K.xxx) 多语言
 */

import { useState } from 'react'
import { Grid, TextField, MenuItem } from '@mui/material'
import { DialogForm } from '../DialogForm'
import { K, t } from '@/ui/text'
import type { TaskCreateRequest } from '@/modules/agentos/dto'

export interface CreateTaskDialogProps {
  /**
   * 对话框是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 提交回调（接收表单数据）
   */
  onSubmit: (data: TaskCreateRequest) => void | Promise<void>

  /**
   * 是否正在提交
   */
  loading?: boolean

  /**
   * 预填充的项目ID（可选）
   */
  defaultProjectId?: string

  /**
   * 可选的项目列表（用于下拉选择）
   */
  projects?: Array<{ project_id: string; name: string }>
}

/**
 * CreateTaskDialog 组件
 *
 * 功能：
 * - 任务标题（必填）
 * - 关联项目（可选）
 * - 会话ID（可选）
 *
 * @example
 * ```tsx
 * <CreateTaskDialog
 *   open={open}
 *   onClose={handleClose}
 *   onSubmit={handleCreate}
 *   loading={loading}
 *   projects={projects}
 * />
 * ```
 */
export function CreateTaskDialog({
  open,
  onClose,
  onSubmit,
  loading = false,
  defaultProjectId,
  projects = [],
}: CreateTaskDialogProps) {
  const [title, setTitle] = useState('')
  const [projectId, setProjectId] = useState(defaultProjectId || '')
  const [sessionId, setSessionId] = useState('')

  const handleSubmit = async () => {
    const data: TaskCreateRequest = {
      title: title.trim(),
      project_id: projectId || undefined,
      session_id: sessionId.trim() || undefined,
    }

    await onSubmit(data)

    // Reset form
    setTitle('')
    setProjectId(defaultProjectId || '')
    setSessionId('')
  }

  const handleClose = () => {
    if (!loading) {
      setTitle('')
      setProjectId(defaultProjectId || '')
      setSessionId('')
      onClose()
    }
  }

  const isValid = title.trim().length > 0

  return (
    <DialogForm
      open={open}
      onClose={handleClose}
      title={t(K.page.tasks.createTask)}
      submitText={t(K.common.create)}
      cancelText={t(K.common.cancel)}
      onSubmit={handleSubmit}
      loading={loading}
      submitDisabled={!isValid}
      maxWidth="sm"
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label={t(K.component.dialog.taskTitle)}
            placeholder={t(K.component.dialog.taskTitlePlaceholder)}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            required
            autoFocus
            disabled={loading}
          />
        </Grid>

        {projects.length > 0 && (
          <Grid item xs={12}>
            <TextField
              select
              label={t(K.component.dialog.project)}
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              fullWidth
              disabled={loading}
              helperText={t(K.component.dialog.projectHelper)}
            >
              <MenuItem value="">
                <em>{t(K.component.dialog.noProject)}</em>
              </MenuItem>
              {projects.map((project) => (
                <MenuItem key={project.project_id} value={project.project_id}>
                  {project.name}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
        )}

        <Grid item xs={12}>
          <TextField
            label={t(K.component.dialog.sessionId)}
            placeholder={t(K.component.dialog.sessionIdPlaceholder)}
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            fullWidth
            disabled={loading}
            helperText={t(K.component.dialog.sessionIdHelper)}
          />
        </Grid>
      </Grid>
    </DialogForm>
  )
}
