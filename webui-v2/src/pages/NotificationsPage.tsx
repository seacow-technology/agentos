/**
 * NotificationsPage - 通知管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: TableShell 封装
 *
 * ⚠️ 待补充 i18n keys:
 * - page.notifications.*
 * - form.field.notificationType
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'

/**
 * Mock 数据（迁移阶段）
 */
const MOCK_NOTIFICATIONS = [
  {
    id: 1,
    type: 'Info',
    title: 'System Update Available',
    message: 'AgentOS v2.5.0 is ready to install',
    timestamp: '2026-02-02 10:30:00',
    read: false,
    priority: 'Medium',
  },
  {
    id: 2,
    type: 'Warning',
    title: 'High Memory Usage',
    message: 'Brain cache using 85% of allocated memory',
    timestamp: '2026-02-02 09:45:00',
    read: false,
    priority: 'High',
  },
  {
    id: 3,
    type: 'Success',
    title: 'Deployment Completed',
    message: 'Project "WebUI v2" deployed successfully',
    timestamp: '2026-02-02 08:15:00',
    read: true,
    priority: 'Low',
  },
  {
    id: 4,
    type: 'Error',
    title: 'Task Execution Failed',
    message: 'Task #42 failed with timeout error',
    timestamp: '2026-02-02 07:30:00',
    read: false,
    priority: 'Critical',
  },
  {
    id: 5,
    type: 'Info',
    title: 'New Skill Available',
    message: 'Skill "pdf-analyzer" added to marketplace',
    timestamp: '2026-02-01 16:20:00',
    read: true,
    priority: 'Low',
  },
]

/**
 * NotificationsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */

interface NotificationRow {
  id: string | number
  title: string
  message: string
  type: string
  timestamp: string
  read: boolean
}

export default function NotificationsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [priorityFilter, setPriorityFilter] = useState('all')

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  // ===================================
  // State Management
  // ===================================
  const [notifications, setNotifications] = useState<NotificationRow[]>(MOCK_NOTIFICATIONS)
  const [loading, setLoading] = useState(false)

  // ===================================
  // Data Fetching
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        // API skeleton
        // const response = await notificationsService.getNotifications()  // Uncommented for Phase 6.1
        // setNotifications(response.data)
        setNotifications(MOCK_NOTIFICATIONS)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  usePageHeader({
    title: t(K.page.notifications.title),
    subtitle: t(K.page.notifications.subtitle),
  })

  usePageActions([
    {
      key: 'markAllRead',
      label: t(K.page.notifications.markAllRead),
      variant: 'outlined',
      onClick: () => {
        toast.info(t(K.page.notifications.markAllRead))
      },
    },
    {
      key: 'clear',
      label: t(K.page.notifications.clearAll),
      variant: 'outlined',
      onClick: () => {
        toast.info(t(K.page.notifications.clearAll))
      },
    },
  ])

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.notifications.columnId),
      width: 70,
    },
    {
      field: 'type',
      headerName: t(K.page.notifications.columnType),
      width: 100,
    },
    {
      field: 'title',
      headerName: t(K.page.notifications.columnTitle),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'message',
      headerName: t(K.page.notifications.columnMessage),
      flex: 2,
      minWidth: 300,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.notifications.columnTimestamp),
      width: 180,
    },
    {
      field: 'priority',
      headerName: t('form.field.priority'),
      width: 100,
    },
    {
      field: 'read',
      headerName: t(K.page.notifications.columnRead),
      width: 80,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <TableShell
      loading={loading}
      rows={notifications}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.notifications.searchPlaceholder)}
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
                >
                  <MenuItem value="all">{t(K.page.notifications.allTypes)}</MenuItem>
                  <MenuItem value="info">{t(K.page.notifications.typeInfo)}</MenuItem>
                  <MenuItem value="success">{t(K.page.notifications.typeSuccess)}</MenuItem>
                  <MenuItem value="warning">{t(K.page.notifications.typeWarning)}</MenuItem>
                  <MenuItem value="error">{t(K.page.notifications.typeError)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.notifications.allPriority)}</MenuItem>
                  <MenuItem value="critical">{t(K.page.notifications.priorityCritical)}</MenuItem>
                  <MenuItem value="high">{t(K.page.notifications.priorityHigh)}</MenuItem>
                  <MenuItem value="medium">{t(K.page.notifications.priorityMedium)}</MenuItem>
                  <MenuItem value="low">{t(K.page.notifications.priorityLow)}</MenuItem>
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
                setTypeFilter('all')
                setPriorityFilter('all')
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
        title: t(K.page.notifications.noNotifications),
        description: t(K.page.notifications.noNotificationsDescription),
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
        total: MOCK_NOTIFICATIONS.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('Notification row clicked (migration stage):', row)
      }}
    />
  )
}
