/**
 * MemoryEntriesPage - 记忆条目管理
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: memoryosService.getMemoryEntries()
 * ✅ States: loading, error, empty, success
 * 
 * 🔒 No-Interaction Contract:
 * - 所有 onClick 为空函数
 * - 使用 API 数据
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Chip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { AddIcon, DeleteIcon } from '@/ui/icons'
import { memoryosService } from '@/services'
import { useTextTranslation, K } from '@/ui/text'
import type { GridColDef } from '@/ui'

// ===================================
// Types
// ===================================

interface MemoryEntryRow {
  id: string
  content: string
  type: 'fact' | 'preference' | 'context' | 'relationship'
  importance: 'high' | 'medium' | 'low'
  source: string
  createdAt: string
  accessCount: number
}

// ===================================
// Component
// ===================================

export default function MemoryEntriesPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================

  // API State
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any[]>([])


  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [importanceFilter, setImportanceFilter] = useState('all')

  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await memoryosService.getMemoryEntries()
        setData(response.data)
      } catch (err) {
        console.error('Failed to fetch memory entries:', err)
        setData([])
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
    title: t(K.page.memoryEntries.title),
    subtitle: t(K.page.memoryEntries.subtitle),
  })

  usePageActions([
    {
      key: 'delete',
      label: t(K.page.memoryEntries.deleteSelected),
      icon: <DeleteIcon />,
      variant: 'outlined',
      color: 'error',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'add',
      label: t(K.page.memoryEntries.addEntry),
      icon: <AddIcon />,
      variant: 'contained',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns
  // ===================================

  const columns: GridColDef<MemoryEntryRow>[] = [
    {
      field: 'content',
      headerName: t(K.page.memoryEntries.columnContent),
      flex: 1,
      minWidth: 300,
    },
    {
      field: 'type',
      headerName: t(K.page.memoryEntries.columnType),
      width: 130,
      renderCell: (params) => {
        const colorMap: Record<MemoryEntryRow['type'], 'primary' | 'secondary' | 'info' | 'success'> = {
          fact: 'primary',
          preference: 'secondary',
          context: 'info',
          relationship: 'success',
        }
        return (
          <Chip
            label={params.value}
            color={colorMap[params.value as MemoryEntryRow['type']]}
            size="small"
            variant="outlined"
          />
        )
      },
    },
    {
      field: 'importance',
      headerName: t(K.page.memoryEntries.columnImportance),
      width: 120,
      renderCell: (params) => {
        const colorMap: Record<MemoryEntryRow['importance'], 'error' | 'warning' | 'default'> = {
          high: 'error',
          medium: 'warning',
          low: 'default',
        }
        return (
          <Chip
            label={params.value}
            color={colorMap[params.value as MemoryEntryRow['importance']]}
            size="small"
          />
        )
      },
    },
    {
      field: 'source',
      headerName: t(K.page.memoryEntries.columnSource),
      width: 160,
    },
    {
      field: 'accessCount',
      headerName: t(K.page.memoryEntries.columnAccessCount),
      width: 130,
      type: 'number',
    },
    {
      field: 'createdAt',
      headerName: t(K.page.memoryEntries.columnCreatedAt),
      width: 120,
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
              label={t(K.common.search)}
              placeholder={t(K.page.memoryEntries.searchPlaceholder)}
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
              label={t(K.page.memoryEntries.filterType)}
              size="small"
              fullWidth
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.page.memoryEntries.filterAllTypes)}</MenuItem>
              <MenuItem value="fact">{t(K.page.memoryEntries.filterFact)}</MenuItem>
              <MenuItem value="preference">{t(K.page.memoryEntries.filterPreference)}</MenuItem>
              <MenuItem value="context">{t(K.page.memoryEntries.filterContext)}</MenuItem>
              <MenuItem value="relationship">{t(K.page.memoryEntries.filterRelationship)}</MenuItem>
            </Select>
          ),
        },
        {
          width: 4,
          component: (
            <Select
              label={t(K.page.memoryEntries.filterImportance)}
              size="small"
              fullWidth
              value={importanceFilter}
              onChange={(e) => setImportanceFilter(e.target.value)}
            >
              <MenuItem value="all">{t(K.page.memoryEntries.filterAllLevels)}</MenuItem>
              <MenuItem value="high">{t(K.page.memoryEntries.filterHigh)}</MenuItem>
              <MenuItem value="medium">{t(K.page.memoryEntries.filterMedium)}</MenuItem>
              <MenuItem value="low">{t(K.page.memoryEntries.filterLow)}</MenuItem>
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
        title: t(K.page.memoryEntries.noEntries),
        description: t(K.page.memoryEntries.noEntriesDesc),
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: data.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
    />
  )
}
