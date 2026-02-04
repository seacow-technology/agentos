/**
 * EvolutionDecisionsPage - Evolution Decisions Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 6: 真实API集成（networkosService）
 * - ✅ State Handling: Loading/Success/Error/Empty states
 *
 * Features:
 * - Evolution decision list with filtering
 * - Decision details drawer
 * - Status and type filtering
 * - Real-time data refresh
 */

import { useState, useEffect, useCallback } from 'react'
import { Box, Typography } from '@mui/material'
import { TextField, Select, MenuItem, Chip } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { networkosService } from '@/services/networkos.service'
import type { EvolutionDecision } from '@/services/networkos.service'

// ===================================
// Types
// ===================================

interface DecisionRow {
  id: string
  decisionId: string
  type: string
  description: string
  proposedAt: string
  decidedAt: string
  status: 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'EXECUTED'
  impact: string
}

// ===================================
// Constants
// ===================================

const EMPTY_PLACEHOLDER = '-'
const STATUS_ALL = 'all'
const STATUS_PROPOSED = 'PROPOSED'
const STATUS_APPROVED = 'APPROVED'
const STATUS_REJECTED = 'REJECTED'
const STATUS_EXECUTED = 'EXECUTED'

/**
 * EvolutionDecisionsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🔌 API: GET /api/governance/evolution-decisions → networkosService.listEvolutionDecisions()
 */
export default function EvolutionDecisionsPage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [decisions, setDecisions] = useState<DecisionRow[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)

  // ===================================
  // State - Filters
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>(STATUS_ALL)
  const [typeFilter, setTypeFilter] = useState<string>('all')

  // ===================================
  // State - Interaction
  // ===================================
  const [selectedDecision, setSelectedDecision] = useState<DecisionRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detailedDecision, setDetailedDecision] = useState<EvolutionDecision | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t('page.evolutionDecisions.title'),
    subtitle: t('page.evolutionDecisions.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('page.evolutionDecisions.refresh'),
      variant: 'outlined',
      onClick: () => { void fetchDecisions() },
    },
  ])

  // ===================================
  // API - Fetch Decisions
  // ===================================
  const fetchDecisions = useCallback(async () => {
    setLoading(true)
    try {
      const apiStatus = statusFilter === STATUS_ALL ? undefined : (statusFilter as 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'EXECUTED')
      const apiType = typeFilter === 'all' ? undefined : (typeFilter as 'PROMOTE' | 'FREEZE' | 'REVOKE' | 'NONE')

      const response = await networkosService.listEvolutionDecisions({
        status: apiStatus,
        action: apiType,
        page: page + 1, // API uses 1-based indexing
        limit: pageSize,
      })

      const rows: DecisionRow[] = response.decisions.map((decision) => ({
        id: decision.decision_id,
        decisionId: decision.decision_id,
        type: decision.action,
        description: decision.explanation,
        proposedAt: decision.meta.created_at ? new Date(decision.meta.created_at).toLocaleDateString() : EMPTY_PLACEHOLDER,
        decidedAt: decision.decided_at ? new Date(decision.decided_at).toLocaleDateString() : EMPTY_PLACEHOLDER,
        status: decision.status || STATUS_PROPOSED,
        impact: decision.consequences?.[0] || EMPTY_PLACEHOLDER,
      }))

      setDecisions(rows)
      setTotal(response.total)
      toast.success(t('page.evolutionDecisions.loadSuccess'))
    } catch (error) {
      console.error('Failed to fetch evolution decisions:', error)
      toast.error(t('page.evolutionDecisions.loadFailed'))
      setDecisions([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, statusFilter, typeFilter, t])

  // ===================================
  // API - Load Decision Details
  // ===================================
  const loadDecisionDetails = useCallback(async (decisionId: string) => {
    setDetailLoading(true)
    try {
      const response = await networkosService.getEvolutionDecision(decisionId)
      setDetailedDecision(response.decision)
    } catch (error) {
      console.error('Failed to load decision details:', error)
      toast.error(t('page.evolutionDecisions.loadFailed'))
      setDetailedDecision(null)
    } finally {
      setDetailLoading(false)
    }
  }, [t])

  // ===================================
  // Handlers
  // ===================================
  const handleRowClick = useCallback((row: DecisionRow) => {
    setSelectedDecision(row)
    setDrawerOpen(true)
    void loadDecisionDetails(row.decisionId)
  }, [loadDecisionDetails])

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage)
  }, [])

  const handlePageSizeChange = useCallback((newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0)
  }, [])

  // ===================================
  // Effects
  // ===================================
  useEffect(() => {
    void fetchDecisions()
  }, [fetchDecisions])

  // ===================================
  // Computed - Filtered Decisions (Client-side search)
  // ===================================
  const filteredDecisions = decisions.filter((decision) => {
    const matchesSearch = searchQuery === '' ||
      decision.decisionId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      decision.description.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesSearch
  })

  // ===================================
  // Helper Functions
  // ===================================
  const getStatusColor = (status: string): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (status) {
      case STATUS_PROPOSED:
        return 'warning'
      case STATUS_APPROVED:
        return 'success'
      case STATUS_REJECTED:
        return 'error'
      case STATUS_EXECUTED:
        return 'primary'
      default:
        return 'default'
    }
  }

  const getTypeLabel = (type: string): string => {
    const ACTION_PROMOTE = 'PROMOTE'
    const ACTION_FREEZE = 'FREEZE'
    const ACTION_REVOKE = 'REVOKE'
    const ACTION_NONE = 'NONE'

    switch (type) {
      case ACTION_PROMOTE:
        return t('page.evolutionDecisions.typePolicyAdjustment')
      case ACTION_FREEZE:
        return t('page.evolutionDecisions.typeTrustChange')
      case ACTION_REVOKE:
        return t('page.evolutionDecisions.typeCapabilityToggle')
      case ACTION_NONE:
        return t('page.evolutionDecisions.typePolicyAdjustment')
      default:
        return type
    }
  }

  const getStatusLabel = (status: string): string => {
    switch (status) {
      case STATUS_PROPOSED:
        return t('page.evolutionDecisions.statusPending')
      case STATUS_APPROVED:
        return t('page.evolutionDecisions.statusApproved')
      case STATUS_REJECTED:
        return t('page.evolutionDecisions.statusRejected')
      case STATUS_EXECUTED:
        return t('page.evolutionDecisions.statusExecuted')
      default:
        return status
    }
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'decisionId',
      headerName: t('page.evolutionDecisions.decisionId'),
      width: 150,
    },
    {
      field: 'type',
      headerName: t('page.evolutionDecisions.type'),
      width: 150,
      renderCell: (params) => {
        const VARIANT_BODY2 = 'body2' as const
        return <Typography variant={VARIANT_BODY2}>{getTypeLabel(params.value as string)}</Typography>
      },
    },
    {
      field: 'description',
      headerName: t('page.evolutionDecisions.description'),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'proposedAt',
      headerName: t('page.evolutionDecisions.proposedAt'),
      width: 130,
    },
    {
      field: 'decidedAt',
      headerName: t('page.evolutionDecisions.decidedAt'),
      width: 130,
    },
    {
      field: 'status',
      headerName: t('page.evolutionDecisions.status'),
      width: 120,
      renderCell: (params) => {
        const status = params.value as string
        const SIZE_SMALL = 'small' as const
        const FONT_WEIGHT = 600
        return (
          <Chip
            label={getStatusLabel(status)}
            color={getStatusColor(status)}
            size={SIZE_SMALL}
            sx={{ fontWeight: FONT_WEIGHT }}
          />
        )
      },
    },
    {
      field: 'impact',
      headerName: t('page.evolutionDecisions.impact'),
      width: 200,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 6 API Integration
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredDecisions}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 4,
                component: (
                  <TextField
                    label={t('common.search')}
                    placeholder={t('page.evolutionDecisions.decisionId')}
                    fullWidth
                    size={'small' as const}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                ),
              },
              {
                width: 4,
                component: (
                  <Select
                    label={t('page.evolutionDecisions.filterStatus')}
                    fullWidth
                    size={'small' as const}
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <MenuItem value={STATUS_ALL}>{t('common.filter')}</MenuItem>
                    <MenuItem value={STATUS_PROPOSED}>{t('page.evolutionDecisions.statusPending')}</MenuItem>
                    <MenuItem value={STATUS_APPROVED}>{t('page.evolutionDecisions.statusApproved')}</MenuItem>
                    <MenuItem value={STATUS_REJECTED}>{t('page.evolutionDecisions.statusRejected')}</MenuItem>
                    <MenuItem value={STATUS_EXECUTED}>{t('page.evolutionDecisions.statusExecuted')}</MenuItem>
                  </Select>
                ),
              },
              {
                width: 4,
                component: (
                  <Select
                    label={t('page.evolutionDecisions.filterType')}
                    fullWidth
                    size={'small' as const}
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <MenuItem value={'all' as const}>{t('common.filter')}</MenuItem>
                    <MenuItem value={'PROMOTE' as const}>{t('page.evolutionDecisions.typePolicyAdjustment')}</MenuItem>
                    <MenuItem value={'FREEZE' as const}>{t('page.evolutionDecisions.typeTrustChange')}</MenuItem>
                    <MenuItem value={'REVOKE' as const}>{t('page.evolutionDecisions.typeCapabilityToggle')}</MenuItem>
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
                  setStatusFilter(STATUS_ALL)
                  setTypeFilter('all')
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t('page.evolutionDecisions.emptyTitle'),
          description: t('page.evolutionDecisions.emptyDescription'),
        }}
        pagination={{
          page,
          pageSize,
          total,
          onPageChange: handlePageChange,
          onPageSizeChange: handlePageSizeChange,
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 6 API Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setDetailedDecision(null)
        }}
        title={selectedDecision?.decisionId || ''}
      >
        {detailLoading && (
          <Typography variant={'body2' as const}>{t('common.loading')}</Typography>
        )}
        {selectedDecision && detailedDecision && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Decision ID */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.decisionId')}
              </Typography>
              <Typography variant={'body1' as const}>{detailedDecision.decision_id}</Typography>
            </Box>

            {/* Type */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.type')}
              </Typography>
              <Typography variant={'body1' as const}>{getTypeLabel(detailedDecision.action)}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.description')}
              </Typography>
              <Typography variant={'body1' as const}>{detailedDecision.explanation}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.status')}
              </Typography>
              <Chip
                label={getStatusLabel(detailedDecision.status || STATUS_PROPOSED)}
                color={getStatusColor(detailedDecision.status || STATUS_PROPOSED)}
                size={'small' as const}
              />
            </Box>

            {/* Proposed At */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.proposedAt')}
              </Typography>
              <Typography variant={'body1' as const}>
                {detailedDecision.meta.created_at
                  ? new Date(detailedDecision.meta.created_at).toLocaleString()
                  : EMPTY_PLACEHOLDER}
              </Typography>
            </Box>

            {/* Decided At */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.decidedAt')}
              </Typography>
              <Typography variant={'body1' as const}>
                {detailedDecision.decided_at
                  ? new Date(detailedDecision.decided_at).toLocaleString()
                  : EMPTY_PLACEHOLDER}
              </Typography>
            </Box>

            {/* Impact */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.impact')}
              </Typography>
              {detailedDecision.consequences.map((consequence, index) => {
                const BULLET = '\u2022'
                const MARGIN_BOTTOM = 0.5
                return (
                  <Typography key={index} variant={'body2' as const} sx={{ mb: MARGIN_BOTTOM }}>
                    {BULLET} {consequence}
                  </Typography>
                )
              })}
            </Box>

            {/* Trust Tier */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.trustTier')}
              </Typography>
              <Typography variant={'body1' as const}>{detailedDecision.trust_tier}</Typography>
            </Box>

            {/* Risk Score */}
            <Box>
              <Typography variant={'body2' as const} color={'text.secondary' as const} gutterBottom>
                {t('page.evolutionDecisions.riskScore')}
              </Typography>
              <Typography variant={'body1' as const}>{detailedDecision.risk_score.toFixed(2)}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
