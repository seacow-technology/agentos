/**
 * TasksPage - 任务管理页面
 *
 * Phase 6: 真实API接入
 * - ✅ Text System: 使用 T.xxx（G7-G8）
 * - ✅ Layout: usePageHeader only（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Real API: tasksApi 真实数据交互
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { DialogForm } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import type { GridColDef } from '@/ui'
import { Grid } from '@mui/material'
import { tasksApi, type TaskSummary, type TaskCreateRequest } from '@/api/tasks'

/**
 * 将后端任务数据转换为表格行格式
 */
interface TaskRow {
  id: string
  name: string
  status: string
  priority: string
  assignee: string
  dueDate: string
}

function taskToRow(task: TaskSummary): TaskRow {
  return {
    id: task.task_id,
    name: task.title,
    status: task.status,
    priority: task.metadata?.priority || 'Medium',
    assignee: task.metadata?.assignee || '-',
    dueDate: task.metadata?.dueDate || '-',
  }
}

/**
 * TasksPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function TasksPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Data & Loading)
  // ===================================
  const [loading, setLoading] = useState(true)
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  // ===================================
  // State (Filter)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')

  // ===================================
  // State (Create Task Dialog)
  // ===================================
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [taskName, setTaskName] = useState('')
  const [taskDescription, setTaskDescription] = useState('')
  const [taskStatus, setTaskStatus] = useState('draft')
  const [taskPriority, setTaskPriority] = useState('Medium')
  const [taskAssignee, setTaskAssignee] = useState('')
  const [taskDueDate, setTaskDueDate] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.tasks.title'),
    subtitle: t('page.tasks.subtitle'),
  })

  usePageActions([
    {
      key: 'create',
      label: t('page.tasks.createTask'),
      variant: 'contained',
      onClick: () => setCreateDialogOpen(true),
    },
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => loadTasks(),
    },
  ])

  // ===================================
  // Load Tasks (with filters & pagination)
  // ===================================
  const loadTasks = async () => {
    setLoading(true)
    try {
      const filters: any = {
        limit: pageSize,
        offset: page * pageSize,
        sort: 'updated_at:desc',
      }

      // 仅在非"all"时应用状态筛选
      if (statusFilter !== 'all') {
        filters.status = statusFilter
      }

      // Real API call: await agentosService.listTasks()
      const response = await tasksApi.listTasks(filters)
      setTasks(response.tasks)
      setTotal(response.total)
    } catch (error) {
      console.error('Failed to load tasks:', error)
      setTasks([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  // ===================================
  // Effect: Load tasks on mount & when filters/pagination change
  // ===================================
  useEffect(() => {
    loadTasks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, statusFilter])

  // ===================================
  // Apply Filters Handler
  // ===================================
  const handleApplyFilters = () => {
    setPage(0) // 重置到第一页
    loadTasks()
  }

  // ===================================
  // Create Task Handler
  // ===================================
  const handleCreateTask = async () => {
    if (!taskName.trim() || !taskDescription.trim()) {
      console.error('Required fields missing')
      return
    }

    setIsCreating(true)
    try {
      const request: TaskCreateRequest = {
        title: taskName.trim(),
        metadata: {
          description: taskDescription.trim(),
          status: taskStatus,
          priority: taskPriority,
          assignee: taskAssignee.trim() || undefined,
          dueDate: taskDueDate || undefined,
        },
      }

      await tasksApi.createTask(request)
      setCreateDialogOpen(false)

      // Reset form
      setTaskName('')
      setTaskDescription('')
      setTaskStatus('draft')
      setTaskPriority('Medium')
      setTaskAssignee('')
      setTaskDueDate('')

      // Reload tasks
      loadTasks()
    } catch (error) {
      console.error('Failed to create task:', error)
    } finally {
      setIsCreating(false)
    }
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.tasks.columnId),
      width: 80,
    },
    {
      field: 'name',
      headerName: t(K.page.tasks.columnName),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'status',
      headerName: t('form.field.status'),
      width: 140,
    },
    {
      field: 'priority',
      headerName: t('form.field.priority'),
      width: 120,
    },
    {
      field: 'assignee',
      headerName: t(K.page.tasks.columnAssignee),
      width: 150,
    },
    {
      field: 'dueDate',
      headerName: t(K.page.tasks.columnDueDate),
      width: 120,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  const rows = tasks.map(taskToRow)
  const isEmpty = tasks.length === 0 && !loading // Empty state marker
  const isSuccess = tasks.length > 0 // Success state marker

  return (
    <>
      <TableShell
        loading={loading}
        rows={rows}
        columns={columns}
        data-empty={isEmpty}
        data-success={isSuccess}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t('common.search')}
                    placeholder={t('form.placeholder.search')}
                    fullWidth
                    size="small"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    label={t('form.field.status')}
                    fullWidth
                    size="small"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <MenuItem value="all">{t(K.page.tasks.statusAll)}</MenuItem>
                    <MenuItem value="draft">{t(K.page.tasks.statusDraft)}</MenuItem>
                    <MenuItem value="approved">{t(K.page.tasks.statusApproved)}</MenuItem>
                    <MenuItem value="queued">{t(K.page.tasks.statusQueued)}</MenuItem>
                    <MenuItem value="running">{t(K.page.tasks.statusRunning)}</MenuItem>
                    <MenuItem value="completed">{t(K.page.tasks.statusCompleted)}</MenuItem>
                    <MenuItem value="failed">{t(K.page.tasks.statusFailed)}</MenuItem>
                    <MenuItem value="cancelled">{t(K.page.tasks.statusCancelled)}</MenuItem>
                  </Select>
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    label={t('form.field.priority')}
                    fullWidth
                    size="small"
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                  >
                    <MenuItem value="all">{t('page.tasks.priorityAll')}</MenuItem>
                    <MenuItem value="critical">{t(K.page.tasks.priorityCritical)}</MenuItem>
                    <MenuItem value="high">{t(K.page.tasks.priorityHigh)}</MenuItem>
                    <MenuItem value="medium">{t(K.page.tasks.priorityMedium)}</MenuItem>
                    <MenuItem value="low">{t(K.page.tasks.priorityLow)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t('common.reset'),
                onClick: () => {
                  setSearchQuery('')
                  setStatusFilter('all')
                  setPriorityFilter('all')
                  setPage(0)
                  loadTasks()
                },
              },
              {
                key: 'apply',
                label: t('common.apply'),
                variant: 'contained',
                onClick: handleApplyFilters,
              },
            ]}
          />
        }
        emptyState={{
          title: t('page.tasks.noTasks'),
          description: t('page.tasks.createFirstTask'),
          actions: [
            {
              label: t('page.tasks.createTask'),
              onClick: () => setCreateDialogOpen(true),
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page,
          pageSize,
          total,
          onPageChange: (newPage: number) => {
            setPage(newPage)
          },
          onPageSizeChange: (newPageSize: number) => {
            setPageSize(newPageSize)
            setPage(0) // 重置到第一页
          },
        }}
        onRowClick={(row) => {
          console.log('Task row clicked:', row)
          // Phase 7 - 打开详情抽屉
        }}
      />

      {/* Create Task Dialog */}
      <DialogForm
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        title={t('page.tasks.createTask')}
        submitText={t('common.create')}
        cancelText={t('common.cancel')}
        onSubmit={handleCreateTask}
        submitDisabled={!taskName.trim() || !taskDescription.trim() || isCreating}
        loading={isCreating}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t('form.field.name')}
              placeholder={t('form.placeholder.taskName')}
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              fullWidth
              required
              autoFocus
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t('form.field.description')}
              placeholder={t('form.placeholder.taskDescription')}
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              fullWidth
              required
              multiline
              rows={3}
            />
          </Grid>
          <Grid item xs={6}>
            <Select
              label={t('form.field.status')}
              fullWidth
              value={taskStatus}
              onChange={(e) => setTaskStatus(e.target.value)}
            >
              <MenuItem value="draft">{t(K.page.tasks.statusDraft)}</MenuItem>
              <MenuItem value="approved">{t(K.page.tasks.statusApproved)}</MenuItem>
              <MenuItem value="queued">{t(K.page.tasks.statusQueued)}</MenuItem>
              <MenuItem value="running">{t(K.page.tasks.statusRunning)}</MenuItem>
              <MenuItem value="completed">{t(K.page.tasks.statusCompleted)}</MenuItem>
            </Select>
          </Grid>
          <Grid item xs={6}>
            <Select
              label={t('form.field.priority')}
              fullWidth
              value={taskPriority}
              onChange={(e) => setTaskPriority(e.target.value)}
            >
              <MenuItem value="Critical">{t(K.page.tasks.priorityCritical)}</MenuItem>
              <MenuItem value="High">{t(K.page.tasks.priorityHigh)}</MenuItem>
              <MenuItem value="Medium">{t(K.page.tasks.priorityMedium)}</MenuItem>
              <MenuItem value="Low">{t(K.page.tasks.priorityLow)}</MenuItem>
            </Select>
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t(K.page.tasks.columnAssignee)}
              placeholder={t(K.page.tasks.assigneePlaceholder)}
              value={taskAssignee}
              onChange={(e) => setTaskAssignee(e.target.value)}
              fullWidth
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t(K.page.tasks.columnDueDate)}
              type="date"
              value={taskDueDate}
              onChange={(e) => setTaskDueDate(e.target.value)}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
        </Grid>
      </DialogForm>
    </>
  )
}
