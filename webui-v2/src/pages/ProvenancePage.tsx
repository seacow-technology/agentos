/**
 * ProvenancePage - 数据来源追溯页面
 *
 * Phase 6: Mock data with proper state management
 * - Note: Waiting for networkosService.getProvenance() API
 * - States: Loading/Success/Empty properly handled
 * - i18n: Full translation support
 */

import { useState, useMemo, useEffect } from 'react'
import { TextField, Select, MenuItem, Box, Typography, Chip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'

/**
 * Mock 数据（迁移阶段，6条记录）
 */
interface ProvenanceRow {
  id: number
  source: string
  timestamp: string
  hash: string
  verified: string
  chainLength: number
  description: string
}

const MOCK_PROVENANCE: ProvenanceRow[] = [
  {
    id: 1,
    source: 'Local Repository',
    timestamp: '2026-02-03 08:00:00',
    hash: 'a3f9d2e1c8b7',
    verified: 'verified',
    chainLength: 5,
    description: 'Source code from main repository commit #42abc',
  },
  {
    id: 2,
    source: 'GitHub API',
    timestamp: '2026-02-03 08:15:30',
    hash: 'b7c4e5f2a1d9',
    verified: 'verified',
    chainLength: 3,
    description: 'Issue metadata retrieved via GitHub REST API',
  },
  {
    id: 3,
    source: 'User Upload',
    timestamp: '2026-02-03 08:45:12',
    hash: 'c1d8e9f3b2a4',
    verified: 'pending',
    chainLength: 1,
    description: 'Document uploaded by user admin@example.com',
  },
  {
    id: 4,
    source: 'External API',
    timestamp: '2026-02-03 09:12:45',
    hash: 'd5e6f7a8b9c0',
    verified: 'verified',
    chainLength: 7,
    description: 'Weather data from OpenWeatherMap API',
  },
  {
    id: 5,
    source: 'Knowledge Base',
    timestamp: '2026-02-03 09:30:22',
    hash: 'e2f3g4h5i6j7',
    verified: 'verified',
    chainLength: 4,
    description: 'Documentation extracted from knowledge graph',
  },
  {
    id: 6,
    source: 'ML Model Output',
    timestamp: '2026-02-03 09:50:00',
    hash: 'f9g8h7i6j5k4',
    verified: 'unverified',
    chainLength: 2,
    description: 'Generated content from llama2:7b model',
  },
]

/**
 * ProvenancePage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function ProvenancePage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter + Pagination)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [appliedSearchQuery, setAppliedSearchQuery] = useState('')
  const [appliedStatusFilter, setAppliedStatusFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [provenanceData, setProvenanceData] = useState(MOCK_PROVENANCE)

  // Pagination state
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25) // setPageSize not needed - fixed page size

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedProvenance, setSelectedProvenance] = useState<ProvenanceRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.provenance.title),
    subtitle: t(K.page.provenance.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: async () => {
        setLoading(true)
        try {
          // API skeleton
          // const response = await networkosService.getProvenance()
          // setProvenanceData(response.data)
          
          setProvenanceData(MOCK_PROVENANCE)
        } catch (error) {
          console.error('Failed to refresh provenance data:', error)
        } finally {
          setLoading(false)
        }
      },
    },
  ])

  // Data fetching with API skeleton
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        // API skeleton - ready for real implementation
        // const response = await networkosService.getProvenance()
        // setProvenanceData(response.data)

        // Fallback to mock data until API is available
        
        setProvenanceData(MOCK_PROVENANCE)
      } catch (error) {
        console.error('Failed to load provenance data:', error)
        setProvenanceData([])
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // ===================================
  // P1-18: Filter Apply Logic
  // ===================================
  const handleApplyFilters = () => {
    setAppliedSearchQuery(searchQuery)
    setAppliedStatusFilter(statusFilter)
    setPage(0) // Reset to first page when filters change
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setStatusFilter('all')
    setAppliedSearchQuery('')
    setAppliedStatusFilter('all')
    setPage(0)
  }

  // ===================================
  // P1-18 & P1-19: Filtered & Paginated Data
  // ===================================
  const filteredData = useMemo(() => {
    let result = [...provenanceData]

    // Apply search filter
    if (appliedSearchQuery) {
      const query = appliedSearchQuery.toLowerCase()
      result = result.filter(
        (item) =>
          item.source.toLowerCase().includes(query) ||
          item.hash.toLowerCase().includes(query) ||
          item.description.toLowerCase().includes(query)
      )
    }

    // Apply status filter
    if (appliedStatusFilter !== 'all') {
      result = result.filter((item) => item.verified === appliedStatusFilter)
    }

    return result
  }, [appliedSearchQuery, appliedStatusFilter])

  const paginatedData = useMemo(() => {
    const startIndex = page * pageSize
    const endIndex = startIndex + pageSize
    return filteredData.slice(startIndex, endIndex)
  }, [filteredData, page, pageSize])

  // ===================================
  // P1-19: Pagination Handlers
  // ===================================
  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: ProvenanceRow) => {
    setSelectedProvenance(row)
    setDrawerOpen(true)
  }

  // ===================================
  // Table Columns Definition (6列)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.provenance.columnId),
      width: 80,
    },
    {
      field: 'source',
      headerName: t(K.page.provenance.columnSource),
      flex: 1,
      minWidth: 150,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.provenance.columnTimestamp),
      width: 180,
    },
    {
      field: 'hash',
      headerName: t(K.page.provenance.columnHash),
      width: 130,
    },
    {
      field: 'verified',
      headerName: t(K.page.provenance.columnVerified),
      width: 120,
    },
    {
      field: 'chainLength',
      headerName: t(K.page.provenance.columnChainLength),
      width: 130,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={paginatedData}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t(K.common.search)}
                    placeholder={t(K.page.provenance.searchPlaceholder)}
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
                    displayEmpty
                  >
                    <MenuItem value="all">{t(K.page.provenance.statusAll)}</MenuItem>
                    <MenuItem value="verified">{t(K.page.provenance.statusVerified)}</MenuItem>
                    <MenuItem value="pending">{t(K.page.provenance.statusPending)}</MenuItem>
                    <MenuItem value="unverified">{t(K.page.provenance.statusUnverified)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t(K.common.reset),
                onClick: handleResetFilters,
              },
              {
                key: 'apply',
                label: t(K.common.apply),
                variant: 'contained',
                onClick: handleApplyFilters,
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.provenance.noProvenance),
          description: t(K.page.provenance.noProvenanceDesc),
        }}
        pagination={{
          page: page,
          pageSize: pageSize,
          total: filteredData.length,
          onPageChange: handlePageChange,
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={t(K.page.provenance.detailTitle)}
      >
        {selectedProvenance && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnId)}
              </Typography>
              <Typography variant="body1">{selectedProvenance.id}</Typography>
            </Box>

            {/* Source */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnSource)}
              </Typography>
              <Typography variant="body1">{selectedProvenance.source}</Typography>
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnTimestamp)}
              </Typography>
              <Typography variant="body1">{selectedProvenance.timestamp}</Typography>
            </Box>

            {/* Hash */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnHash)}
              </Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                {selectedProvenance.hash}
              </Typography>
            </Box>

            {/* Verified Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnVerified)}
              </Typography>
              <Chip
                label={selectedProvenance.verified}
                color={
                  selectedProvenance.verified === 'verified'
                    ? 'success'
                    : selectedProvenance.verified === 'pending'
                    ? 'warning'
                    : 'error'
                }
                size="small"
              />
            </Box>

            {/* Chain Length */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.columnChainLength)}
              </Typography>
              <Typography variant="body1">{selectedProvenance.chainLength}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.provenance.description)}
              </Typography>
              <Typography variant="body1">{selectedProvenance.description}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
