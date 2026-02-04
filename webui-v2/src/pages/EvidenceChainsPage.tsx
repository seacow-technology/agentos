/**
 * EvidenceChainsPage - 证据链页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect } from 'react'
import { Box, Typography, Chip } from '@mui/material'
import { TextField, Select, MenuItem, Button } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation } from '@/ui/text'
import { DetailDrawer, DeleteConfirmDialog } from '@/ui/interaction'
import type { GridColDef } from '@/ui'

/**
 * Types
 */
interface EvidenceChainRow {
  id: number
  claim: string
  evidenceCount: number
  confidence: number
  timestamp: string
  status: string
}

/**
 * Mock 数据（迁移阶段）
 */
const MOCK_EVIDENCE_CHAINS: EvidenceChainRow[] = [
  {
    id: 1,
    claim: 'User has admin privileges',
    evidenceCount: 5,
    confidence: 0.95,
    timestamp: '2026-02-02 09:30:15',
    status: 'Verified',
  },
  {
    id: 2,
    claim: 'Code change is safe to deploy',
    evidenceCount: 12,
    confidence: 0.88,
    timestamp: '2026-02-02 09:25:42',
    status: 'Verified',
  },
  {
    id: 3,
    claim: 'API endpoint is rate-limited',
    evidenceCount: 3,
    confidence: 0.72,
    timestamp: '2026-02-02 09:20:18',
    status: 'Pending',
  },
  {
    id: 4,
    claim: 'Database migration is reversible',
    evidenceCount: 8,
    confidence: 0.91,
    timestamp: '2026-02-02 09:15:33',
    status: 'Verified',
  },
  {
    id: 5,
    claim: 'External API is stable',
    evidenceCount: 2,
    confidence: 0.45,
    timestamp: '2026-02-02 09:10:05',
    status: 'Rejected',
  },
  {
    id: 6,
    claim: 'User input is sanitized',
    evidenceCount: 7,
    confidence: 0.96,
    timestamp: '2026-02-02 09:05:47',
    status: 'Verified',
  },
]

/**
 * EvidenceChainsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function EvidenceChainsPage() {
  const [evidenceChains, setEvidenceChains] = useState<any[]>(MOCK_EVIDENCE_CHAINS)

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // Phase 3 Integration - Interaction State
  const [selectedChain, setSelectedChain] = useState<EvidenceChainRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // ===================================
  // Data Fetching - Real API (mock data until backend ready)
  // ===================================
  useEffect(() => {
    const fetchEvidencechains = async () => {
      try {
        // Ready for real API integration
        // const response = await agentosService.getEvidenceChains()
        // setEvidenceChains(response.data)

        // Use mock data for now
        setEvidenceChains(MOCK_EVIDENCE_CHAINS)
      } catch (err) {
        console.error('Failed to fetch evidenceChains:', err)
      } finally {
        // no-op
      }
    }

    fetchEvidencechains()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.evidenceChain.title'),
    subtitle: t('page.evidenceChain.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => console.log('Refresh evidence chains'),
    },
    {
      key: 'export',
      label: t('common.export'),
      variant: 'contained',
      onClick: () => console.log('Export evidence chains'),
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================

  const handleRowClick = (row: EvidenceChainRow) => {
    setSelectedChain(row)
    setDrawerOpen(true)
  }

  const handleDelete = () => {
    console.log('Delete evidence chain:', selectedChain?.id)
    setDeleteDialogOpen(false)
    setDrawerOpen(false)
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 80,
    },
    {
      field: 'claim',
      headerName: t('page.evidenceChain.columnClaim'),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'evidenceCount',
      headerName: t('page.evidenceChain.columnEvidenceCount'),
      width: 160,
      valueFormatter: (params: any) => {
        const value = params?.value ?? params
        const count = typeof value === 'number' ? value : 0
        return `${count} ${t('page.evidenceChain.evidenceCount')}`
      },
    },
    {
      field: 'confidence',
      headerName: t('page.evidenceChain.columnConfidence'),
      width: 120,
      valueFormatter: (params: any) => {
        const value = params?.value ?? params
        const conf = typeof value === 'number' ? value : 0
        return `${(conf * 100).toFixed(0)}%`
      },
    },
    {
      field: 'timestamp',
      headerName: t('page.evidenceChain.columnTimestamp'),
      width: 180,
    },
    {
      field: 'status',
      headerName: t('page.evidenceChain.status'),
      width: 120,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
        loading={false}
        rows={evidenceChains}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t('common.search')}
                    placeholder={t('page.evidenceChain.searchPlaceholder')}
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
                    label={t('page.evidenceChain.status')}
                    fullWidth
                    size="small"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <MenuItem value="all">{t('page.evidenceChain.statusAll')}</MenuItem>
                    <MenuItem value="verified">{t('page.evidenceChain.statusVerified')}</MenuItem>
                    <MenuItem value="rejected">{t('page.evidenceChain.statusRejected')}</MenuItem>
                    <MenuItem value="pending">{t('page.evidenceChain.statusPending')}</MenuItem>
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
                  setStatusFilter('all')
                },
              },
              {
                key: 'apply',
                label: t('common.apply'),
                variant: 'contained',
                onClick: () => console.log('Apply filters'),
              },
            ]}
          />
        }
        emptyState={{
          title: t('page.evidenceChain.noChains'),
          description: t('page.evidenceChain.noChainsDesc'),
          actions: [
            {
              label: t('common.refresh'),
              onClick: () => console.log('Refresh from empty state'),
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page: 0,
          pageSize: 25,
          total: evidenceChains.length,
          onPageChange: () => console.log('Page change'),
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedChain?.claim || ''}
        actions={
          <>
            <Button
              variant="outlined"
              onClick={() => console.log('View evidence details:', selectedChain?.id)}
            >
              {t('page.evidenceChain.viewEvidence')}
            </Button>
            <Button
              variant="outlined"
              onClick={() => console.log('Edit chain:', selectedChain?.id)}
            >
              {t('common.edit')}
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={() => {
                setDrawerOpen(false)
                setDeleteDialogOpen(true)
              }}
            >
              {t('common.delete')}
            </Button>
          </>
        }
      >
        {selectedChain && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                ID
              </Typography>
              <Typography variant="body1">{selectedChain.id}</Typography>
            </Box>

            {/* Claim */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.evidenceChain.columnClaim')}
              </Typography>
              <Typography variant="body1">{selectedChain.claim}</Typography>
            </Box>

            {/* Evidence Count */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.evidenceChain.columnEvidenceCount')}
              </Typography>
              <Typography variant="body1">{selectedChain.evidenceCount} {t('page.evidenceChain.evidenceCount')}</Typography>
            </Box>

            {/* Confidence */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.evidenceChain.columnConfidence')}
              </Typography>
              <Chip
                label={`${(selectedChain.confidence * 100).toFixed(0)}%`}
                color={
                  selectedChain.confidence >= 0.9
                    ? 'success'
                    : selectedChain.confidence >= 0.7
                    ? 'info'
                    : 'warning'
                }
                size="small"
              />
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.evidenceChain.status')}
              </Typography>
              <Chip
                label={selectedChain.status}
                color={
                  selectedChain.status === 'Verified'
                    ? 'success'
                    : selectedChain.status === 'Rejected'
                    ? 'error'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.evidenceChain.columnTimestamp')}
              </Typography>
              <Typography variant="body1">{selectedChain.timestamp}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Delete Confirm Dialog - Phase 3 Integration */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType={t('page.evidenceChain.title')}
        resourceName={selectedChain?.claim}
      />
    </>
  )
}
