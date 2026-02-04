/**
 * UsersPage - 用户管理页面
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getUsers()
 * ✅ States: loading, error, empty, success
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ No Interaction: onClick 空函数
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation, K } from '@/ui/text'
import { agentosService } from '@/services'
import type { GridColDef } from '@/ui'

/**
 * UsersPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function UsersPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // API State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<any[]>([])

  // ===================================
  // State (Filter)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await agentosService.getUsers()
        setData(response.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch users')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.users.title),
    subtitle: t(K.page.users.subtitle),
  })

  usePageActions([
    {
      key: 'invite',
      label: t(K.page.users.inviteUser),
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'create',
      label: t(K.page.users.createUser),
      variant: 'contained',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.users.columnId),
      width: 70,
    },
    {
      field: 'username',
      headerName: t(K.page.users.columnUsername),
      width: 150,
    },
    {
      field: 'email',
      headerName: t(K.page.users.columnEmail),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'role',
      headerName: t(K.page.users.columnRole),
      width: 120,
    },
    {
      field: 'status',
      headerName: t(K.page.users.columnStatus),
      width: 100,
    },
    {
      field: 'lastLogin',
      headerName: t(K.page.users.columnLastLogin),
      width: 180,
    },
    {
      field: 'createdAt',
      headerName: t(K.page.users.columnCreatedAt),
      width: 130,
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
                  label={t(K.page.users.filterSearch)}
                  placeholder={t(K.page.users.searchPlaceholder)}
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
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.common.all)}</MenuItem>
                  <MenuItem value="admin">{t(K.page.users.roleAdmin)}</MenuItem>
                  <MenuItem value="developer">{t(K.page.users.roleDeveloper)}</MenuItem>
                  <MenuItem value="viewer">{t(K.page.users.roleViewer)}</MenuItem>
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
                >
                  <MenuItem value="all">{t(K.common.all)}</MenuItem>
                  <MenuItem value="active">{t(K.common.active)}</MenuItem>
                  <MenuItem value="inactive">{t(K.common.inactive)}</MenuItem>
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
                setRoleFilter('all')
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
        title: error ? t(K.common.error) : t(K.page.users.noUsers),
        description: error ? error : t(K.page.users.noUsersDesc),
        actions: [
          {
            label: t(K.page.users.createUser),
            onClick: () => {}, // 🔒 No-Interaction: 空函数
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: data.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('User row clicked (migration stage):', row)
      }}
    />
  )
}
