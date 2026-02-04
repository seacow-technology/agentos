/**
 * PluginsPage - 插件管理页面
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getPlugins()
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
import { useTextTranslation, K } from '@/ui/text'
import { agentosService } from '@/services'
import type { GridColDef } from '@/ui'

/**
 * PluginsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function PluginsPage() {
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
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')


  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await agentosService.getPlugins()
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch plugins:', err)
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
    title: t(K.page.plugins.title),
    subtitle: t(K.page.plugins.subtitle),
  })

  usePageActions([
    {
      key: 'marketplace',
      label: t(K.page.plugins.browseMarketplace),
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'install',
      label: t(K.page.plugins.installPlugin),
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
      headerName: t(K.page.plugins.columnId),
      width: 70,
    },
    {
      field: 'name',
      headerName: t(K.page.plugins.columnName),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'version',
      headerName: t(K.page.plugins.columnVersion),
      width: 100,
    },
    {
      field: 'category',
      headerName: t(K.page.plugins.columnCategory),
      width: 140,
    },
    {
      field: 'status',
      headerName: t(K.page.plugins.columnStatus),
      width: 100,
    },
    {
      field: 'author',
      headerName: t(K.page.plugins.columnAuthor),
      width: 150,
    },
    {
      field: 'description',
      headerName: t(K.page.plugins.columnDescription),
      flex: 2,
      minWidth: 250,
    },
    {
      field: 'installedAt',
      headerName: t(K.page.plugins.columnInstalledAt),
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
                  label={t(K.common.search)}
                  placeholder={t(K.page.plugins.searchPlaceholder)}
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
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.plugins.filterAllCategories)}</MenuItem>
                  <MenuItem value="document">{t(K.page.plugins.filterDocument)}</MenuItem>
                  <MenuItem value="communication">{t(K.page.plugins.filterCommunication)}</MenuItem>
                  <MenuItem value="development">{t(K.page.plugins.filterDevelopment)}</MenuItem>
                  <MenuItem value="visualization">{t(K.page.plugins.filterVisualization)}</MenuItem>
                  <MenuItem value="database">{t(K.page.plugins.filterDatabase)}</MenuItem>
                  <MenuItem value="language">{t(K.page.plugins.filterLanguage)}</MenuItem>
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
                  <MenuItem value="all">{t(K.page.plugins.filterAllStatus)}</MenuItem>
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
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setCategoryFilter('all')
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
        title: t(K.page.plugins.noPlugins),
        description: t(K.page.plugins.noPluginsDesc),
        actions: [
          {
            label: t(K.page.plugins.browseMarketplace),
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
        console.log('Plugin row clicked (migration stage):', row)
      }}
    />
  )
}
