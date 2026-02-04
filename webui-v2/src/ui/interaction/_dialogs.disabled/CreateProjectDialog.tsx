/**
 * CreateProjectDialog - 创建项目对话框
 *
 * 基于 DialogForm 封装的项目创建对话框
 * 遵循 G7-G17 规范，使用 t(K.xxx) 多语言
 */

import { useState } from 'react'
import { Grid, TextField } from '@mui/material'
import { DialogForm } from '../DialogForm'
import { K, t } from '@/ui/text'
import type { CreateProjectRequest } from '@/modules/agentos/dto'

export interface CreateProjectDialogProps {
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
  onSubmit: (data: CreateProjectRequest) => void | Promise<void>

  /**
   * 是否正在提交
   */
  loading?: boolean
}

/**
 * CreateProjectDialog 组件
 *
 * 功能：
 * - 项目名称（必填）
 * - 项目描述（可选）
 * - 默认工作目录（可选）
 * - 标签（可选，逗号分隔）
 *
 * @example
 * ```tsx
 * <CreateProjectDialog
 *   open={open}
 *   onClose={handleClose}
 *   onSubmit={handleCreate}
 *   loading={loading}
 * />
 * ```
 */
export function CreateProjectDialog({
  open,
  onClose,
  onSubmit,
  loading = false,
}: CreateProjectDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [defaultWorkdir, setDefaultWorkdir] = useState('')
  const [tags, setTags] = useState('')

  const handleSubmit = async () => {
    const data: CreateProjectRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      default_workdir: defaultWorkdir.trim() || undefined,
      tags: tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
    }

    await onSubmit(data)

    // Reset form
    setName('')
    setDescription('')
    setDefaultWorkdir('')
    setTags('')
  }

  const handleClose = () => {
    if (!loading) {
      setName('')
      setDescription('')
      setDefaultWorkdir('')
      setTags('')
      onClose()
    }
  }

  const isValid = name.trim().length > 0

  return (
    <DialogForm
      open={open}
      onClose={handleClose}
      title={t(K.page.projects.createProject)}
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
            label={t(K.component.dialog.projectName)}
            placeholder={t(K.component.dialog.projectNamePlaceholder)}
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
            required
            autoFocus
            disabled={loading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            label={t(K.component.dialog.projectDescription)}
            placeholder={t(K.component.dialog.projectDescriptionPlaceholder)}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={3}
            disabled={loading}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            label={t(K.component.dialog.defaultWorkdir)}
            placeholder={t(K.component.dialog.defaultWorkdirPlaceholder)}
            value={defaultWorkdir}
            onChange={(e) => setDefaultWorkdir(e.target.value)}
            fullWidth
            disabled={loading}
            helperText={t(K.component.dialog.defaultWorkdirHelper)}
          />
        </Grid>

        <Grid item xs={12}>
          <TextField
            label={t(K.component.dialog.tags)}
            placeholder={t(K.component.dialog.tagsPlaceholder)}
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            fullWidth
            disabled={loading}
            helperText={t(K.component.dialog.tagsHelper)}
          />
        </Grid>
      </Grid>
    </DialogForm>
  )
}
