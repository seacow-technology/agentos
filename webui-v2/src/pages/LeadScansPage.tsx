/**
 * LeadScansPage - Lead Scan 历史页面
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getLeadScans()
 * ✅ States: loading, error, empty, success
 * 
 * 🔒 No-Interaction Contract:
 * - 所有 onClick 为空函数
 * - 使用 API 数据
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { agentosService } from '@/services'
import type { GridColDef } from '@/ui'

/**
 * LeadScansPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🎨 6列表格
 */
export default function LeadScansPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()


  // ===================================
  // API State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any[]>([])

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')


  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await agentosService.getLeadScans()
        setData(response?.data || [])
      } catch (err) {
        console.error('Failed to fetch lead scans:', err)
        setData([]) // Ensure data is always an array even on error
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.leadScans.title),
    subtitle: t(K.page.leadScans.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns Definition (6列)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.leadScans.columnId),
      width: 80,
    },
    {
      field: 'target',
      headerName: t(K.page.leadScans.target),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'type',
      headerName: t(K.page.leadScans.type),
      width: 140,
    },
    {
      field: 'status',
      headerName: t(K.page.leadScans.status),
      width: 120,
    },
    {
      field: 'startedAt',
      headerName: t(K.page.leadScans.startedAt),
      width: 180,
    },
    {
      field: 'completedAt',
      headerName: t(K.page.leadScans.completedAt),
      width: 180,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <TableShell
      loading={loading}
      rows={data}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.form.placeholder.search)}
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
                  fullWidth
                  size="small"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.leadScans.filterAllTypes)}</MenuItem>
                  <MenuItem value="security">{t(K.page.leadScans.filterSecurity)}</MenuItem>
                  <MenuItem value="performance">{t(K.page.leadScans.filterPerformance)}</MenuItem>
                  <MenuItem value="compliance">{t(K.page.leadScans.filterCompliance)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.leadScans.filterAllStatus)}</MenuItem>
                  <MenuItem value="queued">{t(K.page.leadScans.filterQueued)}</MenuItem>
                  <MenuItem value="running">{t(K.page.leadScans.filterRunning)}</MenuItem>
                  <MenuItem value="completed">{t(K.page.leadScans.filterCompleted)}</MenuItem>
                  <MenuItem value="failed">{t(K.page.leadScans.filterFailed)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setTypeFilter('all')
                setStatusFilter('all')
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: () => {}, // 🔒 No-Interaction: 空函数
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.leadScans.noScans),
        description: t(K.page.leadScans.noScansDesc),
        actions: [
          {
            label: t(K.common.refresh),
            onClick: () => {}, // 🔒 No-Interaction: 空函数
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: data?.length || 0,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('LeadScan row clicked (migration stage):', row)
      }}
    />
  )
}
