/**
 * MarketplaceRegistryPage - Marketplace Registry Management
 *
 * 🔒 Migration Contract Compliance:
 * - ✅ Text System: Use t(K.page.marketplaceRegistry.xxx) (G7-G8)
 * - ✅ Layout: usePageHeader + usePageActions (G10-G11)
 * - ✅ Table Contract: TableShell three-row structure
 * - ✅ Phase 3 Integration: DetailDrawer + ConfirmDialog
 * - ✅ Phase 6: Real API integration with networkosService
 */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import {
  Box,
  Typography,
  Chip,
  TextField,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TableShell,
  FilterBar,
  Select,
  MenuItem,
} from '@/ui'
import type { GridColDef } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import {
  networkosService,
  type MarketplaceCapability,
} from '@/services/networkos.service'

// ===================================
// Component
// ===================================

export default function MarketplaceRegistryPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter + Data Loading)
  // ===================================
  const [reviewStatusFilter, setReviewStatusFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('all')
  const [capabilities, setCapabilities] = useState<MarketplaceCapability[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [totalCount, setTotalCount] = useState(0)

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedCapability, setSelectedCapability] = useState<MarketplaceCapability | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  // ===================================
  // Phase 6: API Functions
  // ===================================
  const loadCapabilities = useCallback(async () => {
    setLoading(true)
    try {
      const response = await networkosService.listMarketplaceCapabilities({
        review_status: reviewStatusFilter === 'all' ? undefined : reviewStatusFilter,
        page,
        limit: pageSize,
      })

      setCapabilities(response.capabilities || [])
      setTotalCount(response.total || 0)

    } catch (error) {
      console.error('Failed to load marketplace capabilities:', error)
      toast.error(t(K.page.marketplaceRegistry.loadFailed))
      setCapabilities([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, reviewStatusFilter, t])

  const handleRefresh = async () => {
    await loadCapabilities()
  }

  const handleApprove = async () => {
    if (!selectedCapability) return

    try {
      await networkosService.approveCapability(selectedCapability.id)
      toast.success(t(K.page.marketplaceRegistry.approveSuccess))
      setApproveDialogOpen(false)
      setDrawerOpen(false)
      setSelectedCapability(null)
      await loadCapabilities()
    } catch (error) {
      console.error('Failed to approve capability:', error)
      toast.error(t(K.page.marketplaceRegistry.approveFailed))
    }
  }

  const handleReject = async () => {
    if (!selectedCapability || !rejectReason.trim()) {
      toast.error('Rejection reason is required')
      return
    }

    try {
      await networkosService.rejectCapability(selectedCapability.id, {
        reason: rejectReason,
      })
      toast.success(t(K.page.marketplaceRegistry.rejectSuccess))
      setRejectDialogOpen(false)
      setDrawerOpen(false)
      setSelectedCapability(null)
      setRejectReason('')
      await loadCapabilities()
    } catch (error) {
      console.error('Failed to reject capability:', error)
      toast.error(t(K.page.marketplaceRegistry.rejectFailed))
    }
  }

  // ===================================
  // Effects - Load data on mount and filter changes
  // ===================================
  useEffect(() => {
    loadCapabilities()
  }, [loadCapabilities])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.marketplaceRegistry.title),
    subtitle: t(K.page.marketplaceRegistry.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: handleRefresh,
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = async (row: MarketplaceCapability) => {
    try {
      const response = await networkosService.getMarketplaceCapability(row.id)
      setSelectedCapability(response.capability)
      setDrawerOpen(true)
    } catch (error) {
      console.error('Failed to load capability details:', error)
      toast.error(t(K.common.error))
    }
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0)
  }

  const handleApproveClick = () => {
    setDrawerOpen(false)
    setApproveDialogOpen(true)
  }

  const handleRejectClick = () => {
    setDrawerOpen(false)
    setRejectDialogOpen(true)
  }

  // ===================================
  // Table Columns Definition (7 columns)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.marketplaceRegistry.capabilityId),
      width: 120,
    },
    {
      field: 'name',
      headerName: t(K.page.marketplaceRegistry.name),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'publisher',
      headerName: t(K.page.marketplaceRegistry.publisher),
      width: 150,
    },
    {
      field: 'version',
      headerName: t(K.page.marketplaceRegistry.version),
      width: 100,
    },
    {
      field: 'status',
      headerName: t(K.page.marketplaceRegistry.status),
      width: 120,
      renderCell: (params) => {
        const statusColorMap: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning' | 'info'> = {
          active: 'success',
          inactive: 'default',
          pending: 'warning',
        }
        return (
          <Chip
            label={params.value}
            color={statusColorMap[params.value as string] || 'default'}
            size="small" // eslint-disable-line react/jsx-no-literals
          />
        )
      },
    },
    {
      field: 'submitted_at',
      headerName: t(K.page.marketplaceRegistry.submittedAt),
      width: 180,
    },
    {
      field: 'review_status',
      headerName: t(K.page.marketplaceRegistry.reviewStatus),
      width: 150,
      renderCell: (params) => {
        const statusColorMap: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning' | 'info'> = {
          pending: 'warning',
          approved: 'success',
          rejected: 'error',
        }
        const statusLabelMap: Record<string, string> = {
          pending: t(K.page.marketplaceRegistry.statusPending),
          approved: t(K.page.marketplaceRegistry.statusApproved),
          rejected: t(K.page.marketplaceRegistry.statusRejected),
        }
        return (
          <Chip
            label={statusLabelMap[params.value as string] || params.value}
            color={statusColorMap[params.value as string] || 'default'}
            size="small" // eslint-disable-line react/jsx-no-literals
          />
        )
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={capabilities}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 3,
                component: (
                  <Select
                    fullWidth
                    size="small" // eslint-disable-line react/jsx-no-literals
                    value={reviewStatusFilter}
                    onChange={(e) => setReviewStatusFilter(e.target.value as typeof reviewStatusFilter)}
                    displayEmpty
                  >
                    {/* eslint-disable react/jsx-no-literals, local-rules/no-hardcoded-jsx-strings */}
                    <MenuItem value="all">{t(K.page.marketplaceRegistry.statusAll)}</MenuItem>
                    <MenuItem value="pending">{t(K.page.marketplaceRegistry.statusPending)}</MenuItem>
                    <MenuItem value="approved">{t(K.page.marketplaceRegistry.statusApproved)}</MenuItem>
                    <MenuItem value="rejected">{t(K.page.marketplaceRegistry.statusRejected)}</MenuItem>
                    {/* eslint-enable react/jsx-no-literals, local-rules/no-hardcoded-jsx-strings */}
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'apply',
                label: t(K.common.apply),
                variant: 'contained',
                onClick: loadCapabilities,
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.marketplaceRegistry.emptyTitle),
          description: t(K.page.marketplaceRegistry.emptyDescription),
          actions: [
            {
              label: t(K.common.refresh),
              onClick: handleRefresh,
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page: page,
          pageSize: pageSize,
          total: totalCount,
          onPageChange: handlePageChange,
          onPageSizeChange: handlePageSizeChange,
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedCapability(null)
        }}
        title={selectedCapability?.name || ''}
        actions={
          selectedCapability?.review_status === 'pending' ? (
            <>
              <Button
                variant="contained" // eslint-disable-line react/jsx-no-literals
                color="success" // eslint-disable-line react/jsx-no-literals
                onClick={handleApproveClick}
              >
                {t(K.page.marketplaceRegistry.approve)}
              </Button>
              <Button
                variant="outlined" // eslint-disable-line react/jsx-no-literals
                color="error" // eslint-disable-line react/jsx-no-literals
                onClick={handleRejectClick}
              >
                {t(K.page.marketplaceRegistry.reject)}
              </Button>
            </>
          ) : null
        }
      >
        {selectedCapability && (
          /* eslint-disable react/jsx-no-literals */
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.capabilityId)}
              </Typography>
              <Typography variant="body1">{selectedCapability.id}</Typography>
            </Box>

            {/* Publisher */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.publisher)}
              </Typography>
              <Typography variant="body1">{selectedCapability.publisher}</Typography>
            </Box>

            {/* Version */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.version)}
              </Typography>
              <Typography variant="body1">{selectedCapability.version}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.status)}
              </Typography>
              <Chip
                label={selectedCapability.status}
                color={
                  selectedCapability.status === 'active'
                    ? 'success'
                    : selectedCapability.status === 'pending'
                    ? 'warning'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Review Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.reviewStatus)}
              </Typography>
              <Chip
                label={
                  selectedCapability.review_status === 'pending'
                    ? t(K.page.marketplaceRegistry.statusPending)
                    : selectedCapability.review_status === 'approved'
                    ? t(K.page.marketplaceRegistry.statusApproved)
                    : t(K.page.marketplaceRegistry.statusRejected)
                }
                color={
                  selectedCapability.review_status === 'approved'
                    ? 'success'
                    : selectedCapability.review_status === 'rejected'
                    ? 'error'
                    : 'warning'
                }
                size="small"
              />
            </Box>

            {/* Submitted At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.marketplaceRegistry.submittedAt)}
              </Typography>
              <Typography variant="body1">{selectedCapability.submitted_at}</Typography>
            </Box>

            {/* Description */}
            {selectedCapability.description && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.marketplaceRegistry.description)}
                </Typography>
                <Typography variant="body1">{selectedCapability.description}</Typography>
              </Box>
            )}

            {/* Tags */}
            {selectedCapability.tags && selectedCapability.tags.length > 0 && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.marketplaceRegistry.tags)}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  {selectedCapability.tags.map((tag, index) => (
                    <Chip key={index} label={tag} size="small" variant="outlined" />
                  ))}
                </Box>
              </Box>
            )}
          </Box>
          /* eslint-enable react/jsx-no-literals */
        )}
      </DetailDrawer>

      {/* Approve Confirmation Dialog */}
      <ConfirmDialog
        open={approveDialogOpen}
        onClose={() => setApproveDialogOpen(false)}
        onConfirm={handleApprove}
        title={t(K.page.marketplaceRegistry.approve)}
        // eslint-disable-next-line react/jsx-no-literals
        message={`Are you sure you want to approve "${selectedCapability?.name}"?`}
        confirmText={t(K.page.marketplaceRegistry.approve)}
        cancelText={t(K.common.cancel)}
      />

      {/* Reject Dialog with Reason Input */}
      {/* eslint-disable react/jsx-no-literals */}
      <Dialog
        open={rejectDialogOpen}
        onClose={() => {
          setRejectDialogOpen(false)
          setRejectReason('')
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t(K.page.marketplaceRegistry.reject)}</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            {/* eslint-disable-next-line local-rules/no-hardcoded-jsx-strings */}
            <Typography>
              Are you sure you want to reject "{selectedCapability?.name}"?
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={4}
              label={t(K.page.marketplaceRegistry.rejectReasonLabel)}
              placeholder={t(K.page.marketplaceRegistry.rejectReasonPlaceholder)}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              required
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setRejectDialogOpen(false)
              setRejectReason('')
            }}
          >
            {t(K.common.cancel)}
          </Button>
          <Button
            onClick={handleReject}
            variant="contained"
            color="error"
            disabled={!rejectReason.trim()}
          >
            {t(K.page.marketplaceRegistry.reject)}
          </Button>
        </DialogActions>
      </Dialog>
      {/* eslint-enable react/jsx-no-literals */}
    </>
  )
}
