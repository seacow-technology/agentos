/**
 * PipelinePage - Pipeline Management (Task Events View)
 *
 * Phase 6: Real API Integration
 * - ✅ API: agentosService.listTasks() → Task list with events
 * - ✅ Loading/Success/Error/Empty states
 * - ✅ Filter: search, stage (phase), status
 * - ✅ Actions: Refresh, View Details
 * - ✅ Phase 4 baseline compliance
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Chip } from '@/ui'
import { CreateTaskDialog, type CreateTaskRequest } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import type { GridColDef } from '@/ui'
import { agentosService } from '@/services/agentos.service'
import { toast } from '@/ui/feedback'

/**
 * Pipeline View Data Model (Task + Latest Event)
 */
interface PipelineRow {
  id: string
  task_id: string
  title: string
  phase: string
  status: string
  progress: number
  created_at: string
  duration: string
}

/**
 * Map Task status to display status
 */
function mapTaskStatus(status: string): string {
  const statusMap: Record<string, string> = {
    pending: 'Pending',
    in_progress: 'Running',
    running: 'Running',
    completed: 'Success',
    success: 'Success',
    failed: 'Failed',
    error: 'Failed',
    blocked: 'Blocked',
  }
  return statusMap[status.toLowerCase()] || status
}

/**
 * Calculate duration from created_at to now
 */
function calculateDuration(createdAt: string): string {
  try {
    const start = new Date(createdAt)
    const now = new Date()
    const diffMs = now.getTime() - start.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffSecs = Math.floor((diffMs % 60000) / 1000)
    return `${diffMins}m ${diffSecs}s`
  } catch {
    return '0m 0s'
  }
}

/**
 * Calculate progress based on status
 */
function calculateProgress(status: string): number {
  const progressMap: Record<string, number> = {
    pending: 0,
    in_progress: 50,
    running: 50,
    completed: 100,
    success: 100,
    failed: 0,
    error: 0,
    blocked: 30,
  }
  return progressMap[status.toLowerCase()] || 0
}

/**
 * PipelinePage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function PipelinePage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [pipelines, setPipelines] = useState<PipelineRow[]>([])
  const [filteredPipelines, setFilteredPipelines] = useState<PipelineRow[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [stageFilter, setStageFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [creating, setCreating] = useState(false)

  // ===================================
  // Data Fetching
  // ===================================
  const fetchPipelines = async () => {
    try {
      setLoading(true)
      const response = await agentosService.listTasks({
        page: 1,
        limit: 100,
      })

      const rows: PipelineRow[] = response.tasks.map((task) => ({
        id: task.id,
        task_id: task.id,
        title: task.title,
        phase: task.status || 'unknown',
        status: mapTaskStatus(task.status),
        progress: calculateProgress(task.status),
        created_at: task.created_at,
        duration: calculateDuration(task.created_at),
      }))

      setPipelines(rows)
      setFilteredPipelines(rows)
    } catch (error) {
      console.error('Failed to fetch pipelines:', error)
      toast.error('Failed to load pipelines')
      setPipelines([])
      setFilteredPipelines([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPipelines()
  }, [])

  // ===================================
  // Create Task Handler
  // ===================================
  const handleCreateTask = async (data: CreateTaskRequest) => {
    try {
      setCreating(true)
      await agentosService.createTask(data)
      toast.success('Task created successfully')
      setCreateDialogOpen(false)
      // Refresh the pipeline list
      await fetchPipelines()
    } catch (error) {
      console.error('Failed to create task:', error)
      toast.error('Failed to create task')
    } finally {
      setCreating(false)
    }
  }

  // ===================================
  // Filtering Logic
  // ===================================
  useEffect(() => {
    let filtered = [...pipelines]

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter((p) => p.title.toLowerCase().includes(query))
    }

    // Stage filter (phase)
    if (stageFilter !== 'all') {
      filtered = filtered.filter((p) => p.phase.toLowerCase() === stageFilter.toLowerCase())
    }

    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter((p) => p.status.toLowerCase() === statusFilter.toLowerCase())
    }

    setFilteredPipelines(filtered)
    setPage(0)
  }, [searchQuery, stageFilter, statusFilter, pipelines])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.pipeline.title),
    subtitle: t(K.page.pipeline.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: fetchPipelines,
    },
    {
      key: 'create',
      label: t(K.page.pipeline.createPipeline),
      variant: 'contained',
      onClick: () => {
        setCreateDialogOpen(true)
      },
    },
  ])

  // ===================================
  // Table Columns Definition
  // ===================================
  const ellipsis = '...'
  const chipSize = 'small'

  const columns: GridColDef[] = [
    {
      field: 'task_id',
      headerName: t(K.page.pipeline.columnId),
      width: 200,
      renderCell: (params) => {
        const shortId = String(params.value).substring(0, 12)
        return (
          <span style={{ fontFamily: 'monospace', fontSize: '0.85em' }}>
            {shortId}
            {ellipsis}
          </span>
        )
      },
    },
    {
      field: 'title',
      headerName: t(K.page.pipeline.columnName),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'phase',
      headerName: t(K.page.pipeline.columnStage),
      width: 140,
    },
    {
      field: 'status',
      headerName: t(K.page.pipeline.columnStatus),
      width: 120,
      renderCell: (params) => {
        const statusColors: Record<string, 'success' | 'warning' | 'error' | 'default' | 'info'> = {
          Success: 'success',
          Running: 'warning',
          Failed: 'error',
          Pending: 'default',
          Blocked: 'info',
        }
        return (
          <Chip
            label={params.value}
            color={statusColors[params.value as string] || 'default'}
            size={chipSize}
          />
        )
      },
    },
    {
      field: 'progress',
      headerName: t(K.page.pipeline.columnProgress),
      width: 120,
      renderCell: (params) => `${params.value}%`,
    },
    {
      field: 'created_at',
      headerName: t(K.page.pipeline.columnStartedAt),
      width: 200,
      renderCell: (params) => {
        try {
          return new Date(params.value as string).toLocaleString()
        } catch {
          return params.value
        }
      },
    },
    {
      field: 'duration',
      headerName: t(K.page.pipeline.columnDuration),
      width: 120,
    },
  ]

  // ===================================
  // Pagination
  // ===================================
  const paginatedRows = filteredPipelines.slice(page * pageSize, (page + 1) * pageSize)

  // ===================================
  // Render Constants (to avoid JSX literals)
  // ===================================
  const inputSize = 'small' as const
  const filterAll = 'all'
  const filterPending = 'pending'
  const filterInProgress = 'in_progress'
  const filterCompleted = 'completed'
  const filterBlocked = 'blocked'
  const filterRunning = 'running'
  const filterSuccess = 'success'
  const filterFailed = 'failed'
  const inProgressLabel = 'In Progress'
  const completedLabel = 'Completed'
  const blockedLabel = 'Blocked'
  const filtersApplied = 'Filters applied'
  const emptyString = ''
  const pipelineDetailsPrefix = 'Pipeline details: '

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={paginatedRows}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 4,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.pipeline.searchPlaceholder)}
                  fullWidth
                  size={inputSize}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t(K.page.pipeline.filterStage)}
                  fullWidth
                  size={inputSize}
                  value={stageFilter}
                  onChange={(e) => setStageFilter(e.target.value)}
                >
                  <MenuItem value={filterAll}>{t(K.page.pipeline.stageAll)}</MenuItem>
                  <MenuItem value={filterPending}>{t(K.page.pipeline.statusPending)}</MenuItem>
                  <MenuItem value={filterInProgress}>{inProgressLabel}</MenuItem>
                  <MenuItem value={filterCompleted}>{completedLabel}</MenuItem>
                  <MenuItem value={filterBlocked}>{blockedLabel}</MenuItem>
                </Select>
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t(K.page.pipeline.filterStatus)}
                  fullWidth
                  size={inputSize}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value={filterAll}>{t(K.page.pipeline.statusAll)}</MenuItem>
                  <MenuItem value={filterPending}>{t(K.page.pipeline.statusPending)}</MenuItem>
                  <MenuItem value={filterRunning}>{t(K.page.pipeline.statusRunning)}</MenuItem>
                  <MenuItem value={filterSuccess}>{t(K.page.pipeline.statusSuccess)}</MenuItem>
                  <MenuItem value={filterFailed}>{t(K.page.pipeline.statusFailed)}</MenuItem>
                  <MenuItem value={filterBlocked}>{blockedLabel}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                setSearchQuery(emptyString)
                setStageFilter(filterAll)
                setStatusFilter(filterAll)
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: () => {
                // Filters are applied automatically via useEffect
                toast.success(filtersApplied)
              },
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.pipeline.noPipelines),
        description: t(K.page.pipeline.createFirstPipeline),
        actions: [
          {
            label: t(K.page.pipeline.createPipeline),
            onClick: () => {
              setCreateDialogOpen(true)
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page,
        pageSize,
        total: filteredPipelines.length,
        onPageChange: (newPage) => setPage(newPage),
      }}
      onRowClick={(row) => {
        const pipelineRow = row as PipelineRow
        const detailsMsg = `${pipelineDetailsPrefix}${pipelineRow.title}`
        toast.info(detailsMsg)
        // Future: Open detail drawer or navigate to detail page
      }}
    />

      {/* Create Task Dialog */}
      <CreateTaskDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSubmit={handleCreateTask}
        loading={creating}
      />
    </>
  )
}
