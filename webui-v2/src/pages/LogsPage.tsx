/**
 * LogsPage - 系统日志页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 3 Integration: 添加 DetailDrawer (无删除)
 * - ✅ Unified Exit: TableShell 封装
 *
 * ⚠️ 待补充 i18n keys:
 * - page.logs.*
 * - form.field.level
 */

import { useState } from 'react'
import { TextField, Select, MenuItem, Box, Typography, Chip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'

// ===================================
// Types
// ===================================

interface LogRow {
  id: number
  timestamp: string
  level: string
  source: string
  message: string
  duration: string
}

/**
 * Mock 数据（迁移阶段）
 */
const MOCK_LOGS: LogRow[] = [
  {
    id: 1,
    timestamp: '2026-02-02 11:30:15',
    level: 'INFO',
    source: 'agentos.core.brain',
    message: 'Brain cache refreshed successfully',
    duration: '45ms',
  },
  {
    id: 2,
    timestamp: '2026-02-02 11:28:32',
    level: 'WARN',
    source: 'agentos.webui.api',
    message: 'Rate limit approaching for API endpoint /api/chat',
    duration: '12ms',
  },
  {
    id: 3,
    timestamp: '2026-02-02 11:25:08',
    level: 'ERROR',
    source: 'agentos.core.runner',
    message: 'Failed to execute task: Connection timeout',
    duration: '5002ms',
  },
  {
    id: 4,
    timestamp: '2026-02-02 11:20:00',
    level: 'INFO',
    source: 'agentos.store.migrations',
    message: 'Database migration v75 completed',
    duration: '128ms',
  },
  {
    id: 5,
    timestamp: '2026-02-02 11:15:45',
    level: 'DEBUG',
    source: 'agentos.core.memory',
    message: 'Memory proposal generated for session sess_abc123',
    duration: '8ms',
  },
  {
    id: 6,
    timestamp: '2026-02-02 11:10:22',
    level: 'INFO',
    source: 'agentos.webui.middleware',
    message: 'Demo mode enabled for session',
    duration: '3ms',
  },
]

/**
 * LogsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function LogsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [levelFilter, setLevelFilter] = useState('all')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [logs, setLogs] = useState<LogRow[]>(MOCK_LOGS)
  const [loading, setLoading] = useState(false)

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedLog, setSelectedLog] = useState<LogRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.logs.title),
    subtitle: t(K.page.logs.subtitle),
  })

  usePageActions([
    {
      key: 'export',
      label: t(K.common.download),
      variant: 'outlined',
      onClick: async () => {
        // API skeleton for export
        // await logsService.exportLogs()  // Placeholder for Phase 6.1
        console.log('Export logs (API not implemented)')
      },
    },
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'contained',
      onClick: async () => {
        setLoading(true)
        try {
          // API skeleton
          // const response = await logsService.getLogs()  // Placeholder for Phase 6.1
          // setLogs(response.data)
          setLogs(MOCK_LOGS)
          console.log('Refresh logs (API not implemented)')
        } finally {
          setLoading(false)
        }
      },
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: LogRow) => {
    setSelectedLog(row)
    setDrawerOpen(true)
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.logs.columnId),
      width: 70,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.logs.columnTimestamp),
      width: 180,
    },
    {
      field: 'level',
      headerName: t(K.page.logs.columnLevel),
      width: 100,
    },
    {
      field: 'source',
      headerName: t(K.page.logs.columnSource),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'message',
      headerName: t(K.page.logs.columnMessage),
      flex: 2,
      minWidth: 300,
    },
    {
      field: 'duration',
      headerName: t(K.page.logs.columnDuration),
      width: 100,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={logs}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.logs.searchPlaceholder)}
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
                  value={levelFilter}
                  onChange={(e) => setLevelFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.logs.allLevels)}</MenuItem>
                  <MenuItem value="debug">{t(K.page.logs.levelDebug)}</MenuItem>
                  <MenuItem value="info">{t(K.page.logs.levelInfo)}</MenuItem>
                  <MenuItem value="warn">{t(K.page.logs.levelWarn)}</MenuItem>
                  <MenuItem value="error">{t(K.page.logs.levelError)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.logs.allSources)}</MenuItem>
                  <MenuItem value="core">{t(K.page.logs.sourceCore)}</MenuItem>
                  <MenuItem value="webui">{t(K.page.logs.sourceWebui)}</MenuItem>
                  <MenuItem value="store">{t(K.page.logs.sourceStore)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setLevelFilter('all')
                setSourceFilter('all')
              },
            },
            {
              key: 'apply',
              label: t('common.apply'),
              variant: 'contained',
              onClick: () => {}, // 🔒 No-Interaction: 空函数
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.logs.noLogs),
        description: t(K.page.logs.noLogsDesc),
        actions: [
          {
            label: t('common.reset'),
            onClick: () => {
              setSearchQuery('')
              setLevelFilter('all')
              setSourceFilter('all')
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: MOCK_LOGS.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={`${t(K.page.logs.logEntry)} #${selectedLog?.id || ''}`}
      >
        {selectedLog && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.logs.columnTimestamp)}
              </Typography>
              <Typography variant="body1">{selectedLog.timestamp}</Typography>
            </Box>

            {/* Level */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.logs.columnLevel)}
              </Typography>
              <Chip
                label={selectedLog.level}
                color={
                  selectedLog.level === 'ERROR'
                    ? 'error'
                    : selectedLog.level === 'WARN'
                    ? 'warning'
                    : selectedLog.level === 'INFO'
                    ? 'success'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Source */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.logs.columnSource)}
              </Typography>
              <Typography variant="body1">{selectedLog.source}</Typography>
            </Box>

            {/* Message */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.logs.columnMessage)}
              </Typography>
              <Typography variant="body1">{selectedLog.message}</Typography>
            </Box>

            {/* Duration */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.logs.columnDuration)}
              </Typography>
              <Typography variant="body1">{selectedLog.duration}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
