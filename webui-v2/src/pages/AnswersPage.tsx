/**
 * AnswersPage - 答案库页面
 *
 * 🔒 Phase 6.1 Cleanup - Group C:
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ✅ API Integration: Real API structure
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import type { GridColDef } from '@/ui'
import { agentosService } from '@/services'
import type { AnswerPack } from '@/services/agentos.service'

/**
 * Answer Pack Type (aligned with API response)
 */
type AnswerPackRow = AnswerPack

/**
 * AnswersPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function AnswersPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States + Filters + Pagination
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [answers, setAnswers] = useState<AnswerPackRow[]>([])
  const [total, setTotal] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)

  // ===================================
  // Data Fetching - Real API
  // ===================================
  const fetchAnswers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await agentosService.getAnswerPacks({
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        limit: pageSize,
        offset: page * pageSize,
      })

      if (response.ok) {
        setAnswers(response.data)
        setTotal(response.total)
      } else {
        setError('Failed to fetch answer packs')
      }
    } catch (err) {
      console.error('Failed to fetch answers:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnswers()
  }, [page, pageSize])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.answers.title),
    subtitle: t(K.page.answers.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'contained',
      onClick: () => {
        fetchAnswers()
      },
    },
  ])

  // ===================================
  // Table Columns Definition (aligned with API response)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 100,
    },
    {
      field: 'name',
      headerName: t(K.page.answers.name),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'status',
      headerName: t(K.page.answers.status),
      width: 120,
    },
    {
      field: 'items_count',
      headerName: t(K.page.answers.items_count),
      width: 120,
    },
    {
      field: 'updated_at',
      headerName: t(K.page.answers.updated_at),
      width: 180,
    },
  ]

  // ===================================
  // Render: TableShell Pattern with Four States
  // ===================================
  if (error) {
    return (
      <TableShell
        loading={false}
        rows={[]}
        columns={columns}
        />
    )
  }

  return (
    <TableShell
      loading={loading}
      rows={answers}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.answers.name)}
                  fullWidth
                  size="small"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 6,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.common.all)}</MenuItem>
                  <MenuItem value="draft">{t(K.page.answers.status_draft)}</MenuItem>
                  <MenuItem value="validated">{t(K.page.answers.status_validated)}</MenuItem>
                  <MenuItem value="deprecated">{t(K.page.answers.status_deprecated)}</MenuItem>
                  <MenuItem value="frozen">{t(K.page.answers.status_frozen)}</MenuItem>
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
                setStatusFilter('all')
                setPage(0)
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: () => {
                setPage(0)
                fetchAnswers()
              },
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.answers.empty_title),
        description: t(K.page.answers.empty_description),
        actions: [
          {
            label: t(K.common.reset),
            onClick: () => {
              setSearchQuery('')
              setStatusFilter('all')
              setPage(0)
              fetchAnswers()
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
        console.log('Answer row clicked:', row)
      }}
    />
  )
}
