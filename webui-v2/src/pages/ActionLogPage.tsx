/**
 * ActionLogPage - 行动日志页面
 *
 * 🔒 Phase 6.1 Cleanup - Batch 5:
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ⚠️ API Status: Pending backend implementation
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation, K } from '@/ui/text'
import type { GridColDef } from '@/ui'

/**
 * Action Type - Aligned with v1 API response
 */
interface ActionLog {
  execution_id: string
  action_type: string
  agent_id: string
  decision_id: string | null
  input_params_json: string
  output_json: string
  status: 'success' | 'failure' | 'rolled_back'
  error_message: string | null
  execution_time_ms: number
  executed_at_ms: number
  rollback_id: string | null
  rollback_info?: {
    status: string
    rolled_back_by: string
    rolled_back_at_ms: number
  }
  side_effects: Array<{
    type: string
    severity: string
    description: string
  }>
}

/**
 * ActionLogPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function ActionLogPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States + Filters + Pagination
  // ===================================
  const [loading, setLoading] = useState(true)
  const [actions, setActions] = useState<ActionLog[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [decisionFilter, setDecisionFilter] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize] = useState(50)
  const [total, setTotal] = useState(0)

  // ===================================
  // Data Fetching - Real API call to v1 endpoint
  // ===================================
  const fetchActions = async () => {
    setLoading(true)
    try {
      // Build query params (aligned with v1 API contract)
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: (page * pageSize).toString()
      })

      if (statusFilter && statusFilter !== '') {
        params.append('status', statusFilter)
      }

      if (agentFilter && agentFilter.trim() !== '') {
        params.append('agent_id', agentFilter.trim())
      }

      if (decisionFilter && decisionFilter.trim() !== '') {
        params.append('decision_id', decisionFilter.trim())
      }

      // Note: v1 endpoint has doubled prefix: /api/capability/api/capability/actions/log
      const response = await fetch(`/api/capability/api/capability/actions/log?${params}`)
      const result = await response.json()

      if (result.ok && result.data) {
        setActions(result.data.actions || [])
        setTotal(result.data.pagination?.total || 0)
      } else {
        console.error('API error:', result.error || 'Unknown error')
        setActions([])
        setTotal(0)
      }
    } catch (err) {
      console.error('Failed to fetch action logs:', err)
      setActions([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchActions()
  }, [page])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.actionLog.title'),
    subtitle: t('page.actionLog.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        await fetchActions()
      },
    },
    {
      key: 'export',
      label: t('common.export'),
      variant: 'contained',
      onClick: () => {
        console.log('Export action logs')
      },
    },
  ])

  // ===================================
  // Table Columns Definition (aligned with v1)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'execution_id',
      headerName: 'Execution ID',
      width: 120,
      renderCell: (params) => {
        const id = params.value as string
        return <code>{id ? id.substring(0, 12) + '...' : 'N/A'}</code>
      },
    },
    {
      field: 'action_type',
      headerName: t('page.actionLog.columnAction'),
      width: 150,
    },
    {
      field: 'agent_id',
      headerName: t('page.actionLog.columnAgent'),
      width: 140,
    },
    {
      field: 'decision_id',
      headerName: 'Decision',
      width: 120,
      renderCell: (params) => {
        const id = params.value as string | null
        return id ? <code>{id.substring(0, 12)}...</code> : <span style={{ color: '#9ca3af' }}>N/A</span>
      },
    },
    {
      field: 'status',
      headerName: t('form.field.status'),
      width: 120,
    },
    {
      field: 'execution_time_ms',
      headerName: 'Execution Time',
      width: 130,
      renderCell: (params) => `${params.value}ms`,
    },
    {
      field: 'side_effects',
      headerName: 'Side Effects',
      width: 130,
      renderCell: (params) => {
        const effects = params.value as ActionLog['side_effects']
        return effects && effects.length > 0 ? effects.length : <span style={{ color: '#9ca3af' }}>None</span>
      },
    },
    {
      field: 'executed_at_ms',
      headerName: t('page.actionLog.columnTimestamp'),
      width: 180,
      renderCell: (params) => {
        const timestamp = params.value as number
        const date = new Date(timestamp)
        const now = new Date()
        const diffMs = now.getTime() - date.getTime()
        const diffMins = Math.floor(diffMs / 60000)

        if (diffMins < 1) return 'Just now'
        if (diffMins < 60) return `${diffMins}m ago`

        const diffHours = Math.floor(diffMins / 60)
        if (diffHours < 24) return `${diffHours}h ago`

        return date.toLocaleString()
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern with Four States
  // ===================================
  return (
    <TableShell
      loading={loading}
      rows={actions}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 3,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t('page.actionLog.searchPlaceholder')}
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
                <TextField
                  label={t(K.page.actionLog.filterAgent)}
                  placeholder={t(K.page.actionLog.agentIdPlaceholder)}
                  fullWidth
                  size="small"
                  value={agentFilter}
                  onChange={(e) => setAgentFilter(e.target.value)}
                />
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  label={t(K.form.field.status)}
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value="">{t(K.page.actionLog.statusAll)}</MenuItem>
                  <MenuItem value="success">{t(K.page.actionLog.statusSuccess)}</MenuItem>
                  <MenuItem value="failure">{t(K.page.actionLog.statusFailed)}</MenuItem>
                  <MenuItem value="rolled_back">{t(K.page.actionLog.statusRolledBack)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <TextField
                  label={t(K.page.actionLog.decisionIdLabel)}
                  placeholder={t(K.page.actionLog.decisionIdPlaceholder)}
                  fullWidth
                  size="small"
                  value={decisionFilter}
                  onChange={(e) => setDecisionFilter(e.target.value)}
                />
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                setSearchQuery('')
                setAgentFilter('')
                setStatusFilter('')
                setDecisionFilter('')
                setPage(0)
              },
            },
            {
              key: 'apply',
              label: t('common.apply'),
              variant: 'contained',
              onClick: async () => {
                setPage(0)
                await fetchActions()
              },
            },
          ]}
        />
      }
      emptyState={{
        title: t('page.actionLog.noActions'),
        description: t('page.actionLog.noActionsDesc'),
        actions: [
          {
            label: t('common.refresh'),
            onClick: async () => {
              await fetchActions()
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: page,
        pageSize: pageSize,
        total: total,
        onPageChange: (newPage) => {
          setPage(newPage)
        },
      }}
      onRowClick={(row) => {
        console.log('Action row clicked:', row)
      }}
    />
  )
}
