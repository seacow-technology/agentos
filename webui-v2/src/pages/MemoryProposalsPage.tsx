/**
 * MemoryProposalsPage - Memory Proposals
 *
 * Phase 6: Real API Integration
 * - ✅ API Integration: memoryosService (list/approve/reject)
 * - ✅ Loading/Success/Error/Empty states
 * - ✅ Filtering and pagination
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Chip, Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { memoryosService } from '@services'
import type { MemoryProposal } from '@services'

/**
 * Constants
 */
const COMPONENT_SIZE = 'small' as const
const STATUS_DEFAULT = 'default' as const
const STATUS_SUCCESS = 'success' as const
const STATUS_WARNING = 'warning' as const
const STATUS_ERROR = 'error' as const

// Button variants and colors
const BUTTON_VARIANT_CONTAINED = 'contained' as const
const BUTTON_VARIANT_OUTLINED = 'outlined' as const
const BUTTON_COLOR_SUCCESS = 'success' as const
const BUTTON_COLOR_ERROR = 'error' as const

// Typography variants and colors
const TYPOGRAPHY_VARIANT_BODY1 = 'body1' as const
const TYPOGRAPHY_VARIANT_BODY2 = 'body2' as const
const TYPOGRAPHY_COLOR_SECONDARY = 'text.secondary' as const

// Colors
const COLOR_GREEN = '#2e7d32' as const
const COLOR_INHERIT = 'inherit' as const
const FONT_WEIGHT_BOLD = 'bold' as const
const FONT_WEIGHT_NORMAL = 'normal' as const

// Layout constants
const FLEX_DIRECTION_COLUMN = 'column' as const
const DISPLAY_FLEX = 'flex' as const

// Filter values
const FILTER_ALL = 'all' as const
const FILTER_PERFORMANCE = 'performance' as const
const FILTER_PENDING = 'pending' as const
const FILTER_REVIEW = 'review' as const
const FILTER_APPROVED = 'approved' as const
const FILTER_REJECTED = 'rejected' as const

// Status strings for comparison
const STATUS_APPROVED = 'Approved' as const
const STATUS_REJECTED = 'Rejected' as const
const STATUS_PENDING = 'Pending' as const
const STATUS_UNDER_REVIEW = 'Under Review' as const

/**
 * Types
 */
interface ProposalRow {
  id: string
  title: string
  proposedBy: string
  category: string
  status: string
  votes: number
  createdAt: string
  proposal_type: string
  content: string
}

/**
 * Convert API proposal to table row
 */
const proposalToRow = (proposal: MemoryProposal): ProposalRow => {
  // Extract metadata
  const metadata = typeof proposal.content === 'string'
    ? (() => { try { return JSON.parse(proposal.content) } catch { return {} } })()
    : proposal.content || {}

  return {
    id: proposal.id,
    title: metadata.title || proposal.proposal_type || 'Untitled',
    proposedBy: metadata.proposed_by || 'System',
    category: metadata.category || proposal.proposal_type || 'General',
    status: proposal.status === 'pending' ? 'Pending'
      : proposal.status === 'approved' ? 'Approved'
      : proposal.status === 'rejected' ? 'Rejected'
      : 'Under Review',
    votes: metadata.votes || 0,
    createdAt: proposal.created_at ? new Date(proposal.created_at).toLocaleString() : '-',
    proposal_type: proposal.proposal_type,
    content: proposal.content,
  }
}

/**
 * MemoryProposalsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function MemoryProposalsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // Data State
  // ===================================
  const [proposals, setProposals] = useState<ProposalRow[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)

  // ===================================
  // Filter State
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>(FILTER_ALL)
  const [statusFilter, setStatusFilter] = useState<string>(FILTER_ALL)

  // ===================================
  // Pagination State
  // ===================================
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)

  // ===================================
  // Interaction State
  // ===================================
  const [selectedProposal, setSelectedProposal] = useState<ProposalRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)

  // Create form state
  const [formKey, setFormKey] = useState('')
  const [formValue, setFormValue] = useState('')
  const [formNamespace, setFormNamespace] = useState('user_preferences')
  const [formReason, setFormReason] = useState('')

  // ===================================
  // API Handlers
  // ===================================
  const loadProposals = useCallback(async () => {
    setLoading(true)
    try {
      // Map status filter to API format
      const apiStatus = statusFilter === FILTER_ALL ? undefined
        : statusFilter === FILTER_PENDING ? 'pending' as const
        : statusFilter === FILTER_REVIEW ? 'pending' as const // Map "Under Review" to pending
        : statusFilter === FILTER_APPROVED ? 'approved' as const
        : statusFilter === FILTER_REJECTED ? 'rejected' as const
        : undefined

      const response = await memoryosService.listMemoryProposals({
        status: apiStatus,
        page: page + 1, // API uses 1-based indexing
        limit: pageSize,
      })

      // Defensive check: ensure proposals is always an array
      const proposals = Array.isArray(response.proposals) ? response.proposals : []
      const rows = proposals.map(proposalToRow)

      // Apply client-side search filter
      const filteredRows = searchQuery
        ? rows.filter((row) =>
            row.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            row.proposedBy.toLowerCase().includes(searchQuery.toLowerCase())
          )
        : rows

      setProposals(filteredRows)
      setTotal(response.total)
    } catch (error) {
      console.error('Failed to load memory proposals:', error)
      toast.error('Failed to load proposals')
      setProposals([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, statusFilter, searchQuery])

  // Load proposals on mount and when filters change
  useEffect(() => {
    loadProposals()
  }, [loadProposals])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.memoryProposals.title),
    subtitle: t(K.page.memoryProposals.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: loadProposals,
    },
    {
      key: 'create',
      label: t(K.page.memoryProposals.createProposal),
      variant: 'contained',
      onClick: () => setCreateDialogOpen(true),
    },
  ])

  // ===================================
  // Interaction Handlers
  // ===================================
  const handleRowClick = (row: ProposalRow) => {
    setSelectedProposal(row)
    setDrawerOpen(true)
  }

  const handleApprove = async () => {
    if (!selectedProposal) return

    setActionLoading(true)
    try {
      await memoryosService.approveMemoryProposal(selectedProposal.id, {
        reason: 'Approved from Memory Proposals page',
      })

      toast.success(t(K.page.memoryProposals.approveSuccess))
      setDrawerOpen(false)
      setSelectedProposal(null)

      // Reload proposals
      await loadProposals()
    } catch (error) {
      console.error('Failed to approve proposal:', error)
      toast.error('Failed to approve proposal')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!selectedProposal) return

    setActionLoading(true)
    try {
      await memoryosService.rejectMemoryProposal(selectedProposal.id, {
        reason: 'Rejected from Memory Proposals page',
      })

      toast.success(t(K.page.memoryProposals.rejectSuccess))
      setDrawerOpen(false)
      setSelectedProposal(null)

      // Reload proposals
      await loadProposals()
    } catch (error) {
      console.error('Failed to reject proposal:', error)
      toast.error('Failed to reject proposal')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApplyFilters = () => {
    // Reset to first page and reload
    setPage(0)
    loadProposals()
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setCategoryFilter(FILTER_ALL)
    setStatusFilter(FILTER_ALL)
    setPage(0)
  }

  const handleCreateProposal = async () => {
    // Validation
    if (!formKey.trim() || !formValue.trim()) {
      toast.error('Key and Value are required')
      return
    }

    setCreateLoading(true)
    try {
      await memoryosService.createMemoryProposal({
        agent_id: 'user', // TODO: Get from auth context
        memory_item: {
          key: formKey.trim(),
          value: formValue.trim(),
          namespace: formNamespace,
        },
        reason: formReason.trim() || undefined,
      })

      toast.success('Proposal created successfully')
      setCreateDialogOpen(false)

      // Reset form
      setFormKey('')
      setFormValue('')
      setFormNamespace('user_preferences')
      setFormReason('')

      // Reload proposals
      await loadProposals()
    } catch (error) {
      console.error('Failed to create proposal:', error)
      toast.error('Failed to create proposal')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleCancelCreate = () => {
    setCreateDialogOpen(false)
    // Reset form
    setFormKey('')
    setFormValue('')
    setFormNamespace('user_preferences')
    setFormReason('')
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.memoryProposals.columnId),
      width: 80,
    },
    {
      field: 'title',
      headerName: t(K.page.memoryProposals.columnTitle),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'proposedBy',
      headerName: t(K.page.memoryProposals.columnProposedBy),
      width: 160,
    },
    {
      field: 'category',
      headerName: t(K.page.memoryProposals.columnCategory),
      width: 140,
    },
    {
      field: 'status',
      headerName: t(K.page.memoryProposals.columnStatus),
      width: 140,
      renderCell: (params) => {
        const statusColors: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
          [STATUS_APPROVED]: STATUS_SUCCESS,
          [STATUS_UNDER_REVIEW]: STATUS_WARNING,
          [STATUS_PENDING]: STATUS_DEFAULT,
          [STATUS_REJECTED]: STATUS_ERROR,
        }
        return (
          <Chip
            label={params.value}
            color={statusColors[params.value as string] || STATUS_DEFAULT}
            size={COMPONENT_SIZE}
          />
        )
      },
    },
    {
      field: 'votes',
      headerName: t(K.page.memoryProposals.columnVotes),
      width: 100,
      renderCell: (params) => (
        <strong style={{ color: params.value > 20 ? COLOR_GREEN : COLOR_INHERIT }}>
          {params.value}
        </strong>
      ),
    },
    {
      field: 'createdAt',
      headerName: t(K.page.memoryProposals.columnCreatedAt),
      width: 180,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={proposals}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 4,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.memoryProposals.searchPlaceholder)}
                  fullWidth
                  size={COMPONENT_SIZE}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleApplyFilters()
                    }
                  }}
                />
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t(K.page.memoryProposals.filterCategory)}
                  fullWidth
                  size={COMPONENT_SIZE}
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                >
                  <MenuItem value={FILTER_ALL}>{t(K.page.memoryProposals.categoryAll)}</MenuItem>
                  <MenuItem value={FILTER_PERFORMANCE}>{t(K.page.memoryProposals.categoryPerformance)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t(K.page.memoryProposals.filterStatus)}
                  fullWidth
                  size={COMPONENT_SIZE}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value={FILTER_ALL}>{t(K.page.memoryProposals.statusAll)}</MenuItem>
                  <MenuItem value={FILTER_PENDING}>{t(K.page.memoryProposals.statusPending)}</MenuItem>
                  <MenuItem value={FILTER_REVIEW}>{t(K.page.memoryProposals.statusReview)}</MenuItem>
                  <MenuItem value={FILTER_APPROVED}>{t(K.page.memoryProposals.statusApproved)}</MenuItem>
                  <MenuItem value={FILTER_REJECTED}>{t(K.page.memoryProposals.statusRejected)}</MenuItem>
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
        title: t(K.page.memoryProposals.noProposals),
        description: t(K.page.memoryProposals.createFirstProposal),
        actions: [
          {
            label: t(K.page.memoryProposals.createProposal),
            onClick: () => setCreateDialogOpen(true),
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page,
        pageSize,
        total,
        onPageChange: (newPage: number) => {
          setPage(newPage)
        },
        onPageSizeChange: (newPageSize: number) => {
          setPageSize(newPageSize)
          setPage(0) // Reset to first page when page size changes
        },
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 6 API Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedProposal(null)
        }}
        title={selectedProposal?.title || ''}
        actions={
          <>
            <Button
              variant={BUTTON_VARIANT_CONTAINED}
              color={BUTTON_COLOR_SUCCESS}
              onClick={handleApprove}
              disabled={actionLoading || selectedProposal?.status === STATUS_APPROVED}
            >
              {t(K.page.memoryProposals.approve)}
            </Button>
            <Button
              variant={BUTTON_VARIANT_OUTLINED}
              color={BUTTON_COLOR_ERROR}
              onClick={handleReject}
              disabled={actionLoading || selectedProposal?.status === STATUS_REJECTED}
            >
              {t(K.page.memoryProposals.reject)}
            </Button>
          </>
        }
      >
        {selectedProposal && (
          <Box sx={{ display: DISPLAY_FLEX, flexDirection: FLEX_DIRECTION_COLUMN, gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnId)}
              </Typography>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY1}>{selectedProposal.id}</Typography>
            </Box>

            {/* Proposed By */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnProposedBy)}
              </Typography>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY1}>{selectedProposal.proposedBy}</Typography>
            </Box>

            {/* Category */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnCategory)}
              </Typography>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY1}>{selectedProposal.category}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnStatus)}
              </Typography>
              <Chip
                label={selectedProposal.status}
                color={
                  selectedProposal.status === STATUS_APPROVED
                    ? STATUS_SUCCESS
                    : selectedProposal.status === STATUS_UNDER_REVIEW
                    ? STATUS_WARNING
                    : selectedProposal.status === STATUS_PENDING
                    ? STATUS_DEFAULT
                    : STATUS_ERROR
                }
                size={COMPONENT_SIZE}
              />
            </Box>

            {/* Votes */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnVotes)}
              </Typography>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY1} sx={{ fontWeight: selectedProposal.votes > 20 ? FONT_WEIGHT_BOLD : FONT_WEIGHT_NORMAL, color: selectedProposal.votes > 20 ? COLOR_GREEN : COLOR_INHERIT }}>
                {selectedProposal.votes}
              </Typography>
            </Box>

            {/* Created At */}
            <Box>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY2} color={TYPOGRAPHY_COLOR_SECONDARY} gutterBottom>
                {t(K.page.memoryProposals.columnCreatedAt)}
              </Typography>
              <Typography variant={TYPOGRAPHY_VARIANT_BODY1}>{selectedProposal.createdAt}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Create Proposal Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={handleCancelCreate}
        maxWidth="sm"
        fullWidth
        sx={{
          // ✅ Ensure dialog is above AppBar (zIndex: drawer + 1 = 1041) and PageHeaderBar
          zIndex: (theme) => theme.zIndex.modal + 100,
        }}
      >
        <DialogTitle>{t(K.page.memoryProposals.createProposal)}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: DISPLAY_FLEX, flexDirection: FLEX_DIRECTION_COLUMN, gap: 2, pt: 1 }}>
            {/* Namespace */}
            <Select
              label={t(K.page.memoryProposals.formNamespace)}
              value={formNamespace}
              onChange={(e) => setFormNamespace(e.target.value as string)}
              size={COMPONENT_SIZE}
              fullWidth
            >
              <MenuItem value="user_preferences">{t(K.page.memoryProposals.namespaceUserPreferences)}</MenuItem>
              <MenuItem value="system">{t(K.page.memoryProposals.namespaceSystem)}</MenuItem>
              <MenuItem value="project">{t(K.page.memoryProposals.namespaceProject)}</MenuItem>
              <MenuItem value="conversation">{t(K.page.memoryProposals.namespaceConversation)}</MenuItem>
            </Select>

            {/* Key */}
            <TextField
              label={t(K.page.memoryProposals.formKey)}
              value={formKey}
              onChange={(e) => setFormKey(e.target.value)}
              size={COMPONENT_SIZE}
              fullWidth
              placeholder={t(K.page.memoryProposals.placeholderKey)}
            />

            {/* Value */}
            <TextField
              label={t(K.page.memoryProposals.formValue)}
              value={formValue}
              onChange={(e) => setFormValue(e.target.value)}
              size={COMPONENT_SIZE}
              fullWidth
              multiline
              rows={3}
              placeholder={t(K.page.memoryProposals.placeholderValue)}
            />

            {/* Reason */}
            <TextField
              label={t(K.page.memoryProposals.formReason)}
              value={formReason}
              onChange={(e) => setFormReason(e.target.value)}
              size={COMPONENT_SIZE}
              fullWidth
              multiline
              rows={2}
              placeholder={t(K.page.memoryProposals.placeholderReason)}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelCreate} disabled={createLoading}>
            {t(K.common.cancel)}
          </Button>
          <Button
            onClick={handleCreateProposal}
            variant={BUTTON_VARIANT_CONTAINED}
            disabled={createLoading || !formKey.trim() || !formValue.trim()}
          >
            {createLoading ? t(K.page.memoryProposals.creating) : t(K.common.create)}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
