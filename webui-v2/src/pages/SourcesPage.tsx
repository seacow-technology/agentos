/**
 * SourcesPage - 知识源页面
 *
 * Phase 6: Real API Integration
 * - ✅ Text System: 使用 t('xxx')
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Real API: brainosService integration
 * - ✅ Loading/Success/Error/Empty states
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Grid } from '@/ui'
import { DialogForm } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { brainosService } from '@/services/brainos.service'

/**
 * UI Row Type (mapped from backend)
 */
interface SourceRow {
  id: string
  name: string
  type: string
  url: string
  status: string
  lastSync: string
  itemCount: number
}

// Constants for filter values
const FILTER_ALL = 'all'
const TYPE_FILE = 'file'
const TYPE_GIT = 'git'
const TYPE_DIRECTORY = 'directory'

const STATUS_ACTIVE = 'active'
const STATUS_SYNCING = 'syncing'
const STATUS_INACTIVE = 'inactive'
const STATUS_ERROR = 'error'

/**
 * SourcesPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function SourcesPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Data)
  // ===================================
  const [loading, setLoading] = useState(true)
  const [sources, setSources] = useState<SourceRow[]>([])


  // ===================================
  // State (Filter)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState(FILTER_ALL)
  const [statusFilter, setStatusFilter] = useState(FILTER_ALL)

  // ===================================
  // State (Add Source Dialog)
  // ===================================
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [sourceName, setSourceName] = useState('')
  const [sourceType, setSourceType] = useState(TYPE_DIRECTORY)
  const [sourceUrl, setSourceUrl] = useState('')

  // ===================================
  // Data Fetching
  // ===================================
  const fetchSources = async () => {
    try {
      setLoading(true)
      const response = await brainosService.listKnowledgeSources()

      // Map backend data to UI format
      const mappedSources: SourceRow[] = (response.sources || []).map((source) => ({
        id: source.id,
        name: source.name || 'Unnamed Source',
        type: source.type || 'Unknown',
        url: source.id,
        status: source.status || 'unknown',
        lastSync: source.created_at || '-',
        itemCount: 0,
      }))

      setSources(mappedSources)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load sources'
      toast.error(errorMessage)
      setSources([])
    } finally {
      setLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    fetchSources()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.sources.title'),
    subtitle: t('page.sources.subtitle'),
  })

  usePageActions([
    {
      key: 'create',
      label: t(K.page.sources.addSource),
      variant: 'contained',
      onClick: () => setAddDialogOpen(true),
    },
    {
      key: 'refresh',
      label: t(K.page.knowledgeSources.syncAll),
      variant: 'outlined',
      onClick: fetchSources,
    },
  ])

  // ===================================
  // Add Source Handler
  // ===================================
  const handleAddSource = async () => {
    if (!sourceName.trim() || !sourceUrl.trim()) {
      toast.error(t('common.requiredFields'))
      return
    }

    try {
      setSubmitting(true)
      await brainosService.createKnowledgeSource({
        name: sourceName.trim(),
        type: sourceType,
        config: {
          path: sourceUrl.trim(),
        },
      })

      setAddDialogOpen(false)

      // Reset form
      setSourceName('')
      setSourceType(TYPE_DIRECTORY)
      setSourceUrl('')

      // Refresh the list
      await fetchSources()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create source'
      toast.error(errorMessage)
    } finally {
      setSubmitting(false)
    }
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 70,
    },
    {
      field: 'name',
      headerName: t(K.page.sources.name),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'type',
      headerName: t(K.page.sources.type),
      width: 130,
    },
    {
      field: 'url',
      headerName: t(K.page.sources.url),
      flex: 1,
      minWidth: 220,
    },
    {
      field: 'status',
      headerName: t(K.page.sources.status),
      width: 110,
    },
    {
      field: 'lastSync',
      headerName: t(K.page.sources.lastSync),
      width: 180,
    },
    {
      field: 'itemCount',
      headerName: t(K.page.sources.itemCount),
      width: 120,
    },
  ]

  // ===================================
  // Client-side Filtering
  // ===================================
  const filteredSources = sources.filter((source) => {
    // Search query filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      const matchesName = source.name.toLowerCase().includes(query)
      const matchesUrl = source.url.toLowerCase().includes(query)
      if (!matchesName && !matchesUrl) return false
    }

    // Type filter
    if (typeFilter !== FILTER_ALL && source.type.toLowerCase() !== typeFilter.toLowerCase()) {
      return false
    }

    // Status filter
    if (statusFilter !== FILTER_ALL && source.status.toLowerCase() !== statusFilter.toLowerCase()) {
      return false
    }

    return true
  })

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredSources}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t('common.search')}
                  fullWidth
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
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as string)}
                >
                  <MenuItem value={FILTER_ALL}>{t('common.allTypes')}</MenuItem>
                  <MenuItem value={TYPE_GIT}>{t('common.git')}</MenuItem>
                  <MenuItem value={TYPE_FILE}>{t('common.fileUpload')}</MenuItem>
                  <MenuItem value={TYPE_DIRECTORY}>{t('common.directory')}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as string)}
                >
                  <MenuItem value={FILTER_ALL}>{t('common.allStatus')}</MenuItem>
                  <MenuItem value={STATUS_ACTIVE}>{t('common.active')}</MenuItem>
                  <MenuItem value={STATUS_SYNCING}>{t('common.syncing')}</MenuItem>
                  <MenuItem value={STATUS_INACTIVE}>{t('common.inactive')}</MenuItem>
                  <MenuItem value={STATUS_ERROR}>{t('common.error')}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                setSearchQuery('')
                setTypeFilter(FILTER_ALL)
                setStatusFilter(FILTER_ALL)
              },
            },
          ]}
        />
      }
      emptyState={{
        title: t('page.sources.noSources'),
        description: filteredSources.length === 0 && sources.length > 0
          ? t('page.sources.noSourcesFiltered')
          : t('page.sources.noSourcesYet'),
        actions: [
          {
            label: t('common.add'),
            onClick: () => setAddDialogOpen(true),
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: filteredSources.length,
        onPageChange: () => {}, // Client-side pagination not needed for small datasets
      }}
      onRowClick={(row) => {
        console.log('Source row clicked:', row)
        // TODO: Open detail drawer in future phase
      }}
    />

      {/* Add Source Dialog */}
      <DialogForm
        open={addDialogOpen}
        onClose={() => {
          if (!submitting) {
            setAddDialogOpen(false)
            setSourceName('')
            setSourceType(TYPE_DIRECTORY)
            setSourceUrl('')
          }
        }}
        title={t(K.page.sources.addSource)}
        submitText={t(K.common.create)}
        cancelText={t(K.common.cancel)}
        onSubmit={handleAddSource}
        submitDisabled={submitting || !sourceName.trim() || !sourceUrl.trim()}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.sources.name)}
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              fullWidth
              required
              autoFocus
              disabled={submitting}
            />
          </Grid>
          <Grid item xs={12}>
            <Select
              label={t(K.page.sources.type)}
              fullWidth
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as string)}
              disabled={submitting}
            >
              <MenuItem value={TYPE_DIRECTORY}>{t('common.directory')}</MenuItem>
              <MenuItem value={TYPE_FILE}>{t('common.file')}</MenuItem>
              <MenuItem value={TYPE_GIT}>{t('common.gitRepository')}</MenuItem>
            </Select>
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.sources.url)}
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              fullWidth
              required
              disabled={submitting}
            />
          </Grid>
        </Grid>
      </DialogForm>
    </>
  )
}
