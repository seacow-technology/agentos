/**
 * ToolsPage - MCP 工具管理
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getTools()
 * ✅ States: loading, error, empty, success
 * 
 * 🔒 No-Interaction Contract:
 * - 所有 onClick 为空函数
 * - 使用 API 数据
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Chip } from '@mui/material'
import type { GridColDef } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui/table'
import { AddIcon, RefreshIcon } from '@/ui/icons'
import { agentosService } from '@/services'
import { useTextTranslation, K } from '@/ui/text'

// ===================================
// Types
// ===================================

interface ToolRow {
  id: string
  name: string
  type: 'builtin' | 'mcp' | 'custom'
  status: 'active' | 'inactive' | 'error'
  provider: string
  description: string
  lastUsed: string
}

// ===================================
// Component
// ===================================

export default function ToolsPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================

  // API State
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<any[]>([])

  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await agentosService.getTools()
        setData(response.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch tools')
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
    title: t(K.page.tools.title),
    subtitle: t(K.page.tools.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.page.tools.refresh),
      icon: <RefreshIcon />,
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'add',
      label: t(K.page.tools.addTool),
      icon: <AddIcon />,
      variant: 'contained',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns
  // ===================================

  const columns: GridColDef<ToolRow>[] = [
    {
      field: 'name',
      headerName: t(K.page.tools.columnName),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'type',
      headerName: t(K.page.tools.columnType),
      width: 100,
      renderCell: (params) => {
        const colorMap: Record<ToolRow['type'], 'primary' | 'info' | 'secondary'> = {
          builtin: 'primary',
          mcp: 'info',
          custom: 'secondary',
        }
        return (
          <Chip
            label={params.value}
            color={colorMap[params.value as ToolRow['type']]}
            size="small"
            variant="outlined"
          />
        )
      },
    },
    {
      field: 'status',
      headerName: t(K.page.tools.columnStatus),
      width: 100,
      renderCell: (params) => {
        const colorMap: Record<ToolRow['status'], 'success' | 'default' | 'error'> = {
          active: 'success',
          inactive: 'default',
          error: 'error',
        }
        return (
          <Chip
            label={params.value}
            color={colorMap[params.value as ToolRow['status']]}
            size="small"
          />
        )
      },
    },
    {
      field: 'provider',
      headerName: t(K.page.tools.columnProvider),
      width: 150,
    },
    {
      field: 'description',
      headerName: t(K.page.tools.columnDescription),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'lastUsed',
      headerName: t(K.page.tools.columnLastUsed),
      width: 160,
    },
  ]

  // ===================================
  // FilterBar
  // ===================================

  const filterBar = (
    <FilterBar
      filters={[
        {
          width: 4,
          component: (
            <TextField
              label={t(K.page.tools.filterSearch)}
              placeholder={t(K.page.tools.filterSearch)}
              size="small"
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          ),
        },
        {
          width: 4,
          component: (
            <Select
              label={t(K.page.tools.filterType)}
              size="small"
              fullWidth
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.common.all)}</MenuItem>
              <MenuItem value="builtin">{t(K.page.tools.typeBuiltIn)}</MenuItem>
              <MenuItem value="mcp">{t(K.page.tools.typeMcp)}</MenuItem>
              <MenuItem value="custom">{t(K.page.tools.typeCustom)}</MenuItem>
            </Select>
          ),
        },
        {
          width: 4,
          component: (
            <Select
              label={t(K.page.tools.filterStatus)}
              size="small"
              fullWidth
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.common.all)}</MenuItem>
              <MenuItem value="active">{t(K.common.active)}</MenuItem>
              <MenuItem value="inactive">{t(K.common.inactive)}</MenuItem>
              <MenuItem value="error">{t(K.common.error)}</MenuItem>
            </Select>
          ),
        },
      ]}
    />
  )

  // ===================================
  // Render
  // ===================================

  return (
    <TableShell
      loading={loading}
      rows={data}
      columns={columns}
      filterBar={filterBar}
      onRowClick={() => {}} // 🔒 No-Interaction: 空函数
      emptyState={{
        title: error ? t(K.common.error) : t(K.page.tools.noTools),
        description: error ? error : t(K.page.tools.noToolsDesc),
      }}
    />
  )
}
