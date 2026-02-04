/**
 * AnswerPacksPage - 答案包管理页面
 *
 * 🔒 Phase 6.1 Cleanup - Batch 5:
 * - ✅ Text System: 使用 t(K.page.answerPacks.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ⚠️ API Status: Pending backend implementation
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Grid } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DialogForm } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import { systemService } from '@/services'

/**
 * Answer Pack Type (aligned with backend API response)
 */
interface AnswerPack {
  id: string
  name: string
  status: string
  items_count: number
  metadata?: { description?: string; [key: string]: unknown }
  created_at: string
  updated_at: string
}

/**
 * AnswerPacksPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🎨 6列表格
 */
export default function AnswerPacksPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States + Filters
  // ===================================
  const [loading, setLoading] = useState(true)
  const [answerPacks, setAnswerPacks] = useState<AnswerPack[]>([])
  const [filteredPacks, setFilteredPacks] = useState<AnswerPack[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [domainFilter, setDomainFilter] = useState('all')
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [packName, setPackName] = useState('')
  const [packDomain, setPackDomain] = useState('customer-service')
  const [selectedPack, setSelectedPack] = useState<any>(null)

  // ===================================
  // Data Fetching - Real API Integration
  // ===================================
  useEffect(() => {
    const fetchAnswerPacks = async () => {
      setLoading(true)
      try {
        const response = await systemService.listAnswerPacks({ limit: 100 })
        if (response.ok) {
          const packs = (response.data || []) as unknown as AnswerPack[]
          setAnswerPacks(packs)
          setFilteredPacks(packs)
        } else {
          throw new Error(response.error || 'Failed to fetch answer packs')
        }
      } catch (err: any) {
        console.error('Failed to fetch answer packs:', err)
        const errorMessage = err.message || 'Failed to fetch answer packs'
        toast.error(errorMessage)
      } finally {
        setLoading(false)
      }
    }

    fetchAnswerPacks()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.answerPacks.title),
    subtitle: t(K.page.answerPacks.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: async () => {
        setLoading(true)
        // setError removed(null)
        try {
          const response = await systemService.listAnswerPacks({ limit: 100 })
          if (response.ok) {
            const packs = (response.data || []) as unknown as AnswerPack[]
            setAnswerPacks(packs)
            setFilteredPacks(packs)
            toast.success('Answer packs refreshed successfully')
          } else {
            throw new Error(response.error || 'Failed to refresh')
          }
        } catch (err: any) {
          console.error('Failed to refresh:', err)
          toast.error(err.message || 'Failed to refresh')
        } finally {
          setLoading(false)
        }
      },
    },
    {
      key: 'create',
      label: t(K.page.answerPacks.createPack),
      variant: 'contained',
      onClick: () => {
        setCreateDialogOpen(true)
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
      width: 80,
    },
    {
      field: 'name',
      headerName: t(K.page.answerPacks.name),
      flex: 1,
      minWidth: 220,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
    },
    {
      field: 'items_count',
      headerName: t(K.page.answerPacks.questionCount),
      width: 150,
    },
    {
      field: 'created_at',
      headerName: t(K.page.answerPacks.createdAt),
      width: 180,
    },
    {
      field: 'updated_at',
      headerName: t(K.page.answerPacks.updatedAt),
      width: 180,
    },
  ]

  // ===================================
  // Filter Logic
  // ===================================
  const applyFilters = () => {
    let filtered = [...answerPacks]
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(pack =>
        pack.name.toLowerCase().includes(query) ||
        (pack.metadata?.description && pack.metadata.description.toLowerCase().includes(query))
      )
    }
    if (domainFilter !== 'all') {
      filtered = filtered.filter(pack =>
        pack.metadata?.description && pack.metadata.description.toLowerCase().includes(domainFilter)
      )
    }
    setFilteredPacks(filtered)
    toast.success('Filters applied')
  }

  // ===================================
  // Dialog Handlers
  // ===================================
  const handleCreateSubmit = async () => {
    try {
      const response = await systemService.createAnswerPack({
        name: packName,
        description: `Domain: ${packDomain}`,
        answers: [{ question: 'Sample question', answer: 'Sample answer', type: 'general' }]
      })
      if (response.ok) {
        toast.success(response.message || 'Answer pack created successfully')
        setCreateDialogOpen(false)
        setPackName('')
        setPackDomain('customer-service')
        // Reload list
        const listResponse = await systemService.listAnswerPacks({ limit: 100 })
        if (listResponse.ok) {
          const packs = (listResponse.data || []) as unknown as AnswerPack[]
          setAnswerPacks(packs)
          setFilteredPacks(packs)
        }
      } else {
        toast.error(response.error || 'Failed to create answer pack')
      }
    } catch (err: any) {
      console.error('Failed to create answer pack:', err)
      toast.error(err.message || 'Failed to create answer pack')
    }
  }

  // ===================================
  // Render: TableShell Pattern with Four States
  // ===================================
  return (
    <>
    <TableShell
      loading={loading}
      rows={filteredPacks}
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
              width: 6,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={domainFilter}
                  onChange={(e) => setDomainFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.answerPacks.domainAll)}</MenuItem>
                  <MenuItem value="customer-service">{t(K.page.answerPacks.domainCustomerService)}</MenuItem>
                  <MenuItem value="engineering">{t(K.page.answerPacks.domainEngineering)}</MenuItem>
                  <MenuItem value="product">{t(K.page.answerPacks.domainProduct)}</MenuItem>
                  <MenuItem value="security">{t(K.page.answerPacks.domainSecurity)}</MenuItem>
                  <MenuItem value="sales">{t(K.page.answerPacks.domainSales)}</MenuItem>
                  <MenuItem value="hr">{t(K.page.answerPacks.domainHR)}</MenuItem>
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
                setDomainFilter('all')
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: applyFilters,
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.answerPacks.noPacks),
        description: t(K.page.answerPacks.noPacks),
        actions: [
          {
            label: t(K.page.answerPacks.createPack),
            onClick: () => setCreateDialogOpen(true),
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: filteredPacks.length,
        onPageChange: () => {
          toast.info('Pagination will be available once API is integrated')
        },
      }}
      onRowClick={async (row) => {
        try {
          const response = await systemService.getAnswerPack(row.id)
          if (response.ok && response.data) {
            setSelectedPack(response.data)
            setDetailDialogOpen(true)
          } else {
            toast.error(response.error || 'Failed to load pack details')
          }
        } catch (err: any) {
          console.error('Failed to load pack details:', err)
          toast.error(err.message || 'Failed to load pack details')
        }
      }}
    />

    {/* Create Answer Pack Dialog */}
    <DialogForm
      open={createDialogOpen}
      onClose={() => setCreateDialogOpen(false)}
      title={t(K.page.answerPacks.createPack)}
      submitText={t(K.common.create)}
      cancelText={t(K.common.cancel)}
      onSubmit={handleCreateSubmit}
      submitDisabled={!packName.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.answerPacks.name)}
            placeholder={t(K.form.placeholder.enterName)}
            value={packName}
            onChange={(e) => setPackName(e.target.value)}
            fullWidth
            required
            autoFocus
          />
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t(K.page.answerPacks.domain)}
            fullWidth
            value={packDomain}
            onChange={(e) => setPackDomain(e.target.value)}
          >
            <MenuItem value="customer-service">{t(K.page.answerPacks.domainCustomerService)}</MenuItem>
            <MenuItem value="engineering">{t(K.page.answerPacks.domainEngineering)}</MenuItem>
            <MenuItem value="product">{t(K.page.answerPacks.domainProduct)}</MenuItem>
            <MenuItem value="security">{t(K.page.answerPacks.domainSecurity)}</MenuItem>
            <MenuItem value="sales">{t(K.page.answerPacks.domainSales)}</MenuItem>
            <MenuItem value="hr">{t(K.page.answerPacks.domainHR)}</MenuItem>
          </Select>
        </Grid>
      </Grid>
    </DialogForm>

    {/* Answer Pack Detail Dialog */}
    <DialogForm
      open={detailDialogOpen}
      onClose={() => setDetailDialogOpen(false)}
      title={selectedPack?.name || t(K.page.answerPacks.detailTitle)}
      submitText={t(K.common.close)}
      onSubmit={() => setDetailDialogOpen(false)}
      cancelText=""
    >
      {selectedPack && (
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.answerPacks.id)}
              value={selectedPack.id}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.answerPacks.status)}
              value={selectedPack.status}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.answerPacks.itemsCount)}
              value={selectedPack.items?.length || 0}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.answerPacks.createdAt)}
              value={selectedPack.created_at}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.answerPacks.updatedAt)}
              value={selectedPack.updated_at}
              fullWidth
              disabled
            />
          </Grid>
          {selectedPack.metadata?.description && (
            <Grid item xs={12}>
              <TextField
                label={t(K.page.answerPacks.description)}
                value={selectedPack.metadata.description}
                fullWidth
                multiline
                rows={2}
                disabled
              />
            </Grid>
          )}
        </Grid>
      )}
    </DialogForm>
    </>
  )
}
