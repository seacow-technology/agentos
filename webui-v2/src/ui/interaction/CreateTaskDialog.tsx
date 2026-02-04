/**
 * CreateTaskDialog - Create Task Dialog
 *
 * Based on DialogForm wrapper for task creation
 * Follows G7-G17 standards, uses t(K.xxx) for i18n
 */

import { useState } from 'react'
import { Grid, TextField, MenuItem } from '@mui/material'
import { DialogForm } from './DialogForm'
import { K, useTextTranslation } from '@/ui/text'

export interface CreateTaskRequest {
  title: string
  project_id?: string
  session_id?: string
  description?: string
  priority?: string
}

export interface CreateTaskDialogProps {
  /**
   * Whether the dialog is open
   */
  open: boolean

  /**
   * Close callback
   */
  onClose: () => void

  /**
   * Submit callback (receives form data)
   */
  onSubmit: (data: CreateTaskRequest) => void | Promise<void>

  /**
   * Whether currently submitting
   */
  loading?: boolean

  /**
   * Pre-filled project ID (optional)
   */
  defaultProjectId?: string

  /**
   * Optional project list (for dropdown selection)
   */
  projects?: Array<{ project_id: string; name: string }>
}

/**
 * CreateTaskDialog Component
 *
 * Features:
 * - Task title (required)
 * - Associated project (optional)
 * - Session ID (optional)
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
  const { t } = useTextTranslation()
  const [title, setTitle] = useState('')
  const [projectId, setProjectId] = useState(defaultProjectId || '')
  const [sessionId, setSessionId] = useState('')

  const handleSubmit = async () => {
    const data: CreateTaskRequest = {
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
