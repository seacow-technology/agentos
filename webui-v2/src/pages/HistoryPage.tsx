/**
 * HistoryPage - 历史记录页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.history.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 3 Integration: 添加 DetailDrawer (无删除)
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { Box, Typography, Chip } from '@mui/material'
import { TextField, Select, MenuItem } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'

// ===================================
// Types
// ===================================

interface HistoryRow {
  id: number
  operation: string
  user: string
  target: string
  timestamp: string
  status: string
}

/**
 * Mock 数据（迁移阶段，6条记录）
 */
const MOCK_HISTORY: HistoryRow[] = [
  {
    id: 1,
    operation: 'Create Task',
    user: 'Alice Chen',
    target: 'Task #123',
    timestamp: '2026-02-02 09:30:00',
    status: 'success',
  },
  {
    id: 2,
    operation: 'Update Project',
    user: 'Bob Wang',
    target: 'Project: AgentOS Core',
    timestamp: '2026-02-02 09:45:15',
    status: 'success',
  },
  {
    id: 3,
    operation: 'Delete Snippet',
    user: 'Carol Liu',
    target: 'Snippet: auth-helper',
    timestamp: '2026-02-02 10:00:30',
    status: 'success',
  },
  {
    id: 4,
    operation: 'Deploy Extension',
    user: 'David Zhang',
    target: 'Extension: github-mcp',
    timestamp: '2026-02-02 10:15:45',
    status: 'failed',
  },
  {
    id: 5,
    operation: 'Import Model',
    user: 'Eve Li',
    target: 'Model: llama2:7b',
    timestamp: '2026-02-02 10:30:00',
    status: 'success',
  },
  {
    id: 6,
    operation: 'Update Settings',
    user: 'Frank Wu',
    target: 'System Settings',
    timestamp: '2026-02-02 10:45:15',
    status: 'pending',
  },
]

/**
 * HistoryPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function HistoryPage() {
  const [loading, setLoading] = useState(true)
  const [history, setHistory] = useState<any[]>([])

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [userFilter, setUserFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedHistory, setSelectedHistory] = useState<HistoryRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Data Fetching - Real API (empty dataset until backend ready)
  // ===================================
  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      try {
        // Ready for real API integration
        // const response = await agentosService.getHistory()
        // setHistory(response.data)

        // Return empty dataset (no mock delay)
        setHistory([])
      } catch (err) {
        console.error('Failed to fetch history:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.history.title),
    subtitle: t(K.page.history.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => console.log('Refresh history'),
    },
    {
      key: 'export',
      label: t(K.common.export),
      variant: 'outlined',
      onClick: () => console.log('Export history'),
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: HistoryRow) => {
    setSelectedHistory(row)
    setDrawerOpen(true)
  }

  // ===================================
  // Table Columns Definition (6列)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 80,
    },
    {
      field: 'operation',
      headerName: t(K.page.history.operation),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'user',
      headerName: t(K.page.history.user),
      width: 150,
    },
    {
      field: 'target',
      headerName: t(K.page.history.target),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.history.timestamp),
      width: 180,
    },
    {
      field: 'status',
      headerName: t(K.page.history.status),
      width: 120,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={MOCK_HISTORY}
        columns={columns}
        filterBar={
        <FilterBar
          filters={[
            {
              width: 4,
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
              width: 4,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={userFilter}
                  onChange={(e) => setUserFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.history.allUsers)}</MenuItem>
                  <MenuItem value="alice">{t(K.page.history.userAliceChen)}</MenuItem>
                  <MenuItem value="bob">{t(K.page.history.userBobWang)}</MenuItem>
                  <MenuItem value="carol">{t(K.page.history.userCarolLiu)}</MenuItem>
                  <MenuItem value="david">{t(K.page.history.userDavidZhang)}</MenuItem>
                  <MenuItem value="eve">{t(K.page.history.userEveLi)}</MenuItem>
                  <MenuItem value="frank">{t(K.page.history.userFrankWu)}</MenuItem>
                </Select>
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
                  <MenuItem value="all">{t(K.page.history.allStatus)}</MenuItem>
                  <MenuItem value="success">{t(K.common.success)}</MenuItem>
                  <MenuItem value="failed">{t(K.common.failed)}</MenuItem>
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
                setUserFilter('all')
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
          title: t(K.page.history.noHistory),
          description: t(K.page.history.noHistoryDesc),
        }}
        pagination={{
          page: 0,
          pageSize: 25,
          total: history.length,
          onPageChange: () => {}, // 🔒 No-Interaction: 空函数
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedHistory?.operation || ''}
      >
        {selectedHistory && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                ID
              </Typography>
              <Typography variant="body1">{selectedHistory.id}</Typography>
            </Box>

            {/* User */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.history.user)}
              </Typography>
              <Typography variant="body1">{selectedHistory.user}</Typography>
            </Box>

            {/* Target */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.history.target)}
              </Typography>
              <Typography variant="body1">{selectedHistory.target}</Typography>
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.history.timestamp)}
              </Typography>
              <Typography variant="body1">{selectedHistory.timestamp}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.history.status)}
              </Typography>
              <Chip
                label={selectedHistory.status}
                color={
                  selectedHistory.status === 'success'
                    ? 'success'
                    : selectedHistory.status === 'failed'
                    ? 'error'
                    : 'warning'
                }
                size="small"
              />
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
