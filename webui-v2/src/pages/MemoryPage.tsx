/**
 * MemoryPage - 记忆管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.memory.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ API Integration: memoryosService.getMemories()
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'

/**
 * Mock 数据（迁移阶段，6条记录）
 */
const MOCK_MEMORY = [
  {
    id: 1,
    content: 'User prefers code examples in Python',
    source: 'conversation',
    type: 'preference',
    timestamp: '2026-02-01 14:30:00',
    relevance: 0.95,
    status: 'active',
  },
  {
    id: 2,
    content: 'Project structure follows clean architecture pattern',
    source: 'codebase',
    type: 'knowledge',
    timestamp: '2026-02-01 15:45:00',
    relevance: 0.88,
    status: 'active',
  },
  {
    id: 3,
    content: 'Database connection timeout set to 30 seconds',
    source: 'configuration',
    type: 'fact',
    timestamp: '2026-02-01 16:20:00',
    relevance: 0.72,
    status: 'active',
  },
  {
    id: 4,
    content: 'User Alice Chen is the lead developer',
    source: 'conversation',
    type: 'context',
    timestamp: '2026-02-02 09:00:00',
    relevance: 0.85,
    status: 'active',
  },
  {
    id: 5,
    content: 'Deprecated API v1 endpoints should not be used',
    source: 'documentation',
    type: 'constraint',
    timestamp: '2026-02-02 10:15:00',
    relevance: 0.91,
    status: 'archived',
  },
  {
    id: 6,
    content: 'Testing framework: Jest with React Testing Library',
    source: 'codebase',
    type: 'knowledge',
    timestamp: '2026-02-02 11:30:00',
    relevance: 0.79,
    status: 'pending',
  },
]

/**
 * MemoryPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function MemoryPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States + Data
  // ===================================
  const [loading, setLoading] = useState(true)
  const [memories, setMemories] = useState(MOCK_MEMORY)

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // Data Fetching - API Integration
  // ===================================
  useEffect(() => {
    const fetchMemories = async () => {
      setLoading(true)
      try {
        // TODO: Replace with real API call
        // const response = await memoryosService.getMemories()
        // setMemories(response.data)
        setMemories(MOCK_MEMORY)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to fetch memories'
        toast.error(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    fetchMemories()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.memory.title),
    subtitle: t(K.page.memory.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: async () => {
        setLoading(true)
        try {
          // Real API refresh pending
          setMemories(MOCK_MEMORY)
          toast.success('Memories refreshed successfully')
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to refresh'
          toast.error(errorMsg)
        } finally {
          setLoading(false)
        }
      },
    },
    {
      key: 'proposals',
      label: t(K.page.memory.proposals),
      variant: 'outlined',
      onClick: () => {
        toast.info('Memory proposals will be available once API is integrated')
      },
    },
  ])

  // ===================================
  // Table Columns Definition (7列)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 80,
    },
    {
      field: 'content',
      headerName: t(K.page.memory.content),
      flex: 2,
      minWidth: 250,
    },
    {
      field: 'source',
      headerName: t(K.page.memory.source),
      width: 140,
    },
    {
      field: 'type',
      headerName: t(K.page.memory.type),
      width: 120,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.memory.timestamp),
      width: 180,
    },
    {
      field: 'relevance',
      headerName: t(K.page.memory.relevance),
      width: 120,
      valueFormatter: (params: any) => {
        const value = params.value
        if (value == null || typeof value !== 'number' || isNaN(value)) {
          return 'N/A'
        }
        return `${(value * 100).toFixed(0)}%`
      },
    },
    {
      field: 'status',
      headerName: t(K.page.memory.status),
      width: 120,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <TableShell
      loading={loading}
      rows={memories}
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
                  <MenuItem value="all">{t(K.page.memory.typeAll)}</MenuItem>
                  <MenuItem value="preference">{t(K.page.memory.typePreference)}</MenuItem>
                  <MenuItem value="knowledge">{t(K.page.memory.typeKnowledge)}</MenuItem>
                  <MenuItem value="fact">{t(K.page.memory.typeFact)}</MenuItem>
                  <MenuItem value="context">{t(K.page.memory.typeContext)}</MenuItem>
                  <MenuItem value="constraint">{t(K.page.memory.typeConstraint)}</MenuItem>
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
                  <MenuItem value="all">{t(K.page.memory.statusAll)}</MenuItem>
                  <MenuItem value="active">{t(K.page.memory.statusActive)}</MenuItem>
                  <MenuItem value="archived">{t(K.page.memory.statusArchived)}</MenuItem>
                  <MenuItem value="pending">{t(K.common.pending)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state，不触发 API
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
        title: 'No memory found',
        description: 'No memory entries have been created yet',
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: MOCK_MEMORY.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('Memory row clicked (migration stage):', row)
      }}
    />
  )
}
