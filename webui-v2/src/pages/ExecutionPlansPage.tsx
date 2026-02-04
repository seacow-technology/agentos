/**
 * ExecutionPlansPage - 执行计划页面
 *
 * Phase 6: 真实API接入
 * - ✅ Text System: 使用 t(K.page.executionPlans.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Real API: executionPlansApi 真实数据交互
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ Read-only Mode: Write operations disabled (backend API not implemented)
 *   - Create button: disabled with tooltip
 *   - Edit button: disabled with tooltip
 *   - Delete button: disabled with tooltip
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Box, Typography, Chip, Button, Tooltip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DetailDrawer, DeleteConfirmDialog } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import { executionPlansApi, type ExecutionPlan } from '@/api/execution-plans'

// ===================================
// Types
// ===================================

interface ExecutionPlanRow {
  id: string
  name: string
  description: string
  status: string
  priority: string
  steps: number
  createdAt: string
  estimatedTime: string
  executedAt: string | null
}

/**
 * 将后端执行计划数据转换为表格行格式
 */
function planToRow(plan: ExecutionPlan): ExecutionPlanRow {
  return {
    id: plan.id,
    name: plan.name,
    description: plan.description || '-',
    status: plan.status,
    priority: plan.priority,
    steps: plan.steps,
    createdAt: plan.created_at,
    estimatedTime: plan.estimated_time || '-',
    executedAt: plan.executed_at || null,
  }
}

/**
 * ExecutionPlansPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🎨 7列表格
 */
export default function ExecutionPlansPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Data & Loading)
  // ===================================
  const [loading, setLoading] = useState(true)
  const [plans, setPlans] = useState<ExecutionPlan[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)

  // ===================================
  // State (Filter)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')

  // ===================================
  // Interaction State
  // ===================================
  const [selectedPlan, setSelectedPlan] = useState<ExecutionPlanRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.executionPlans.title),
    subtitle: t(K.page.executionPlans.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => loadPlans(),
    },
    {
      key: 'create',
      label: t(K.page.executionPlans.createPlan),
      variant: 'contained',
      disabled: true,
      onClick: () => {},
    },
  ])

  // ===================================
  // Load Execution Plans (with filters & pagination)
  // ===================================
  const loadPlans = async () => {
    setLoading(true)
    try {
      const filters: any = {
        limit: pageSize,
        offset: page * pageSize,
        sort: 'created_at:desc',
      }

      // Apply status filter if not "all"
      if (statusFilter !== 'all') {
        filters.status = statusFilter
      }

      // Apply priority filter if not "all"
      if (priorityFilter !== 'all') {
        filters.priority = priorityFilter
      }

      const response = await executionPlansApi.listPlans(filters)
      setPlans(response?.plans || [])
      setTotal(response?.total || 0)
      toast.success(t(K.page.executionPlans.loadSuccess))
    } catch (error) {
      console.error('Failed to load execution plans:', error)
      toast.error(t(K.page.executionPlans.loadFailed))
      setPlans([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  // ===================================
  // Effect: Load plans on mount & when filters/pagination change
  // ===================================
  useEffect(() => {
    loadPlans()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, statusFilter, priorityFilter])

  // ===================================
  // Apply Filters Handler
  // ===================================
  const handleApplyFilters = () => {
    setPage(0) // Reset to first page
    loadPlans()
  }

  // ===================================
  // Interaction Handlers
  // ===================================
  const handleRowClick = (row: ExecutionPlanRow) => {
    setSelectedPlan(row)
    setDrawerOpen(true)
  }

  const handleDelete = () => {
    // Delete functionality not implemented - backend API missing
    setDeleteDialogOpen(false)
    setDrawerOpen(false)
  }

  // ===================================
  // Table Columns Definition (8列)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.executionPlans.executionId),
      width: 100,
    },
    {
      field: 'name',
      headerName: t(K.page.executionPlans.name),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'status',
      headerName: t(K.page.executionPlans.status),
      width: 120,
    },
    {
      field: 'priority',
      headerName: t(K.page.executionPlans.priority),
      width: 100,
    },
    {
      field: 'steps',
      headerName: t(K.page.executionPlans.steps),
      width: 80,
    },
    {
      field: 'createdAt',
      headerName: t(K.page.executionPlans.createdAt),
      width: 180,
    },
    {
      field: 'estimatedTime',
      headerName: t(K.page.executionPlans.estimatedTime),
      width: 150,
    },
    {
      field: 'executedAt',
      headerName: t(K.page.executionPlans.executedAt),
      width: 180,
    },
  ]

  // ===================================
  // Convert plans to table rows
  // ===================================
  const rows = plans.map(planToRow)

  // ===================================
  // Render: TableShell Pattern + Real API Integration
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={rows}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.executionPlans.searchPlaceholder)}
                  fullWidth
                  size="small"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.executionPlans.status)} - All</MenuItem>
                  <MenuItem value="draft">{t(K.page.executionPlans.statusDraft)}</MenuItem>
                  <MenuItem value="pending">{t(K.page.executionPlans.statusPending)}</MenuItem>
                  <MenuItem value="active">{t(K.page.executionPlans.statusActive)}</MenuItem>
                  <MenuItem value="running">{t(K.page.executionPlans.statusRunning)}</MenuItem>
                  <MenuItem value="completed">{t(K.page.executionPlans.statusCompleted)}</MenuItem>
                  <MenuItem value="failed">{t(K.page.executionPlans.statusFailed)}</MenuItem>
                  <MenuItem value="cancelled">{t(K.page.executionPlans.statusCancelled)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.executionPlans.priority)} - All</MenuItem>
                  <MenuItem value="high">{t(K.page.executionPlans.priorityHigh)}</MenuItem>
                  <MenuItem value="medium">{t(K.page.executionPlans.priorityMedium)}</MenuItem>
                  <MenuItem value="low">{t(K.page.executionPlans.priorityLow)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                setSearchQuery('')
                setStatusFilter('all')
                setPriorityFilter('all')
                setPage(0)
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: handleApplyFilters,
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.executionPlans.emptyTitle),
        description: t(K.page.executionPlans.emptyDescription),
        actions: [],
      }}
      pagination={{
        page,
        pageSize,
        total,
        onPageChange: (newPage) => setPage(newPage),
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedPlan?.name || ''}
        actions={
          <>
            <Tooltip title={t(K.page.executionPlans.notImplemented)}>
              <span>
                <Button
                  variant="outlined"
                  disabled
                >
                  {t(K.common.edit)}
                </Button>
              </span>
            </Tooltip>
            <Tooltip title={t(K.page.executionPlans.notImplemented)}>
              <span>
                <Button
                  variant="outlined"
                  color="error"
                  disabled
                >
                  {t(K.common.delete)}
                </Button>
              </span>
            </Tooltip>
          </>
        }
      >
        {selectedPlan && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.executionId)}
              </Typography>
              <Typography variant="body1">{selectedPlan.id}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.description)}
              </Typography>
              <Typography variant="body1">{selectedPlan.description}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.status)}
              </Typography>
              <Chip
                label={selectedPlan.status}
                color={
                  selectedPlan.status === 'completed'
                    ? 'success'
                    : selectedPlan.status === 'running' || selectedPlan.status === 'active'
                    ? 'primary'
                    : selectedPlan.status === 'failed'
                    ? 'error'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Priority */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.priority)}
              </Typography>
              <Chip
                label={selectedPlan.priority}
                color={
                  selectedPlan.priority === 'high'
                    ? 'error'
                    : selectedPlan.priority === 'medium'
                    ? 'warning'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Steps */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.steps)}
              </Typography>
              <Typography variant="body1">{selectedPlan.steps}</Typography>
            </Box>

            {/* Created At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.createdAt)}
              </Typography>
              <Typography variant="body1">{selectedPlan.createdAt}</Typography>
            </Box>

            {/* Estimated Time */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.estimatedTime)}
              </Typography>
              <Typography variant="body1">{selectedPlan.estimatedTime}</Typography>
            </Box>

            {/* Executed At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.executionPlans.executedAt)}
              </Typography>
              <Typography variant="body1">{selectedPlan.executedAt || '-'}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Delete Confirm Dialog - Phase 3 Integration */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType="Execution Plan"
        resourceName={selectedPlan?.name}
      />
    </>
  )
}
