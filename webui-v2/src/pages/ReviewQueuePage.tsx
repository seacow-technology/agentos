/**
 * ReviewQueuePage - Human Review Queue Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 3 Integration: 添加 DetailDrawer 和操作 Dialog
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ Phase 6: 真实API集成 (brainosService)
 */

import { useState, useEffect, useCallback } from 'react'
import { Box, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Chip, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '@/ui'
import { useTextTranslation } from '@/ui/text'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { brainosService } from '@/services/brainos.service'
import type { ReviewQueueItem } from '@/services/brainos.service'

// ===================================
// Types
// ===================================

interface ReviewQueueRow {
  id: string
  itemId: string
  type: string
  priority: 'High' | 'Medium' | 'Low'
  submitter: string
  submittedAt: string
  status: 'pending' | 'approved' | 'rejected' | 'deferred'
}

// ===================================
// Constants
// ===================================

const EMPTY_PLACEHOLDER = '-'
const STATUS_PENDING = 'pending'
const STATUS_APPROVED = 'approved'
const STATUS_REJECTED = 'rejected'
const PRIORITY_HIGH = 'High'
const PRIORITY_MEDIUM = 'Medium'
const PRIORITY_LOW = 'Low'

/**
 * ReviewQueuePage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * FilterBar: Search(6) + Priority(6)
 * Table: 6 columns with priority/status chip display
 */
export default function ReviewQueuePage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [reviews, setReviews] = useState<ReviewQueueRow[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)

  // ===================================
  // State - Filters
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [priorityFilter, setPriorityFilter] = useState<string>('all')

  // ===================================
  // State - Interaction
  // ===================================
  const [selectedReview, setSelectedReview] = useState<ReviewQueueRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [itemDetail, setItemDetail] = useState<ReviewQueueItem | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // ===================================
  // State - Dialogs
  // ===================================
  const [approveDialogOpen, setApproveDialogOpen] = useState(false)
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t('page.reviewQueue.title'),
    subtitle: t('page.reviewQueue.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('page.reviewQueue.refresh'),
      variant: 'outlined',
      onClick: () => { void fetchReviews() },
    },
  ])

  // ===================================
  // API - Fetch Review Queue
  // ===================================
  const fetchReviews = useCallback(async () => {
    setLoading(true)
    try {
      const response = await brainosService.listReviewQueue({
        page: page + 1, // API uses 1-based indexing
        limit: pageSize,
      })

      const rows: ReviewQueueRow[] = response.items.map((item) => {
        // Parse content to extract metadata
        const content = typeof item.content === 'string' ? JSON.parse(item.content) : item.content
        const priority = content.priority || PRIORITY_MEDIUM
        const submitter = content.submitter || 'System'

        return {
          id: item.id,
          itemId: item.id,
          type: item.proposal_type || 'Unknown',
          priority,
          submitter,
          submittedAt: item.created_at ? new Date(item.created_at).toLocaleDateString() : EMPTY_PLACEHOLDER,
          status: item.status,
        }
      })

      setReviews(rows)
      setTotal(response.total)
      toast.success(t('page.reviewQueue.loadSuccess'))
    } catch (error) {
      console.error('Failed to fetch review queue:', error)
      toast.error(t('page.reviewQueue.loadFailed'))
      setReviews([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, t])

  // ===================================
  // API - Load Item Detail
  // ===================================
  const loadItemDetail = useCallback(async (itemId: string) => {
    setDetailLoading(true)
    try {
      const response = await brainosService.getReviewQueueItem(itemId)
      setItemDetail(response.item)
    } catch (error) {
      console.error('Failed to load item detail:', error)
      setItemDetail(null)
      toast.error(t('page.reviewQueue.loadFailed'))
    } finally {
      setDetailLoading(false)
    }
  }, [t])

  // ===================================
  // API - Approve Review Item
  // ===================================
  const handleApprove = useCallback(async () => {
    if (!selectedReview) return

    setActionLoading(true)
    try {
      await brainosService.approveReviewItem(selectedReview.id, {})
      toast.success(t('page.reviewQueue.approveSuccess'))
      setApproveDialogOpen(false)
      setDrawerOpen(false)
      await fetchReviews()
    } catch (error) {
      console.error('Failed to approve review item:', error)
      toast.error(t('page.reviewQueue.approveFailed'))
    } finally {
      setActionLoading(false)
    }
  }, [selectedReview, t, fetchReviews])

  // ===================================
  // API - Reject Review Item
  // ===================================
  const handleReject = useCallback(async () => {
    if (!selectedReview || !rejectReason.trim()) return

    setActionLoading(true)
    try {
      await brainosService.rejectReviewItem(selectedReview.id, {
        reason: rejectReason,
      })
      toast.success(t('page.reviewQueue.rejectSuccess'))
      setRejectDialogOpen(false)
      setDrawerOpen(false)
      setRejectReason('')
      await fetchReviews()
    } catch (error) {
      console.error('Failed to reject review item:', error)
      toast.error(t('page.reviewQueue.rejectFailed'))
    } finally {
      setActionLoading(false)
    }
  }, [selectedReview, rejectReason, t, fetchReviews])

  // ===================================
  // Handlers
  // ===================================
  const handleRowClick = useCallback((row: ReviewQueueRow) => {
    setSelectedReview(row)
    setDrawerOpen(true)
    void loadItemDetail(row.id)
  }, [loadItemDetail])

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
    void fetchReviews()
  }, [fetchReviews])

  // ===================================
  // Computed - Filtered Reviews (Client-side search + priority filter)
  // ===================================
  const filteredReviews = reviews.filter((review) => {
    const matchesSearch = searchQuery === '' ||
      review.itemId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      review.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      review.submitter.toLowerCase().includes(searchQuery.toLowerCase())

    const matchesPriority = priorityFilter === 'all' || review.priority === priorityFilter

    return matchesSearch && matchesPriority
  })

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'itemId',
      headerName: t('page.reviewQueue.itemId'),
      width: 120,
    },
    {
      field: 'type',
      headerName: t('page.reviewQueue.type'),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'priority',
      headerName: t('page.reviewQueue.priority'),
      width: 130,
      renderCell: (params) => {
        const priority = params.value as 'High' | 'Medium' | 'Low'
        const color = priority === PRIORITY_HIGH ? 'error' : priority === PRIORITY_MEDIUM ? 'warning' : 'success'
        const label = priority === PRIORITY_HIGH
          ? t('page.reviewQueue.priorityHigh')
          : priority === PRIORITY_MEDIUM
          ? t('page.reviewQueue.priorityMedium')
          : t('page.reviewQueue.priorityLow')
        return (
          <Chip
            label={label}
            color={color}
            size="small"
            sx={{ fontWeight: 600 }}
          />
        )
      },
    },
    {
      field: 'submitter',
      headerName: t('page.reviewQueue.submitter'),
      width: 150,
    },
    {
      field: 'submittedAt',
      headerName: t('page.reviewQueue.submittedAt'),
      width: 140,
    },
    {
      field: 'status',
      headerName: t('page.reviewQueue.status'),
      width: 130,
      renderCell: (params) => {
        const status = params.value as string
        const label = status === STATUS_PENDING
          ? t('page.reviewQueue.statusPending')
          : status === STATUS_APPROVED
          ? t('page.reviewQueue.statusApproved')
          : status === STATUS_REJECTED
          ? t('page.reviewQueue.statusRejected')
          : status
        return <Chip label={label} size="small" />
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 6 API Integration
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredReviews}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t('common.search')}
                    placeholder={t('page.reviewQueue.itemId')}
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
                    label={t('page.reviewQueue.priority')}
                    fullWidth
                    size="small"
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                  >
                    <MenuItem value="all">{t('common.filter')}</MenuItem>
                    <MenuItem value={PRIORITY_HIGH}>{t('page.reviewQueue.priorityHigh')}</MenuItem>
                    <MenuItem value={PRIORITY_MEDIUM}>{t('page.reviewQueue.priorityMedium')}</MenuItem>
                    <MenuItem value={PRIORITY_LOW}>{t('page.reviewQueue.priorityLow')}</MenuItem>
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
                  setPriorityFilter('all')
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t('page.reviewQueue.emptyTitle'),
          description: t('page.reviewQueue.emptyDescription'),
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
          setItemDetail(null)
        }}
        title={selectedReview?.type || ''}
        actions={
          <>
            <Button
              variant="contained"
              color="success"
              disabled={actionLoading || selectedReview?.status === STATUS_APPROVED}
              onClick={() => setApproveDialogOpen(true)}
            >
              {t('page.reviewQueue.approve')}
            </Button>
            <Button
              variant="outlined"
              color="error"
              disabled={actionLoading || selectedReview?.status === STATUS_REJECTED}
              onClick={() => setRejectDialogOpen(true)}
            >
              {t('page.reviewQueue.reject')}
            </Button>
          </>
        }
      >
        {selectedReview && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Item ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.itemId')}
              </Typography>
              <Typography variant="body1">{selectedReview.itemId}</Typography>
            </Box>

            {/* Type */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.type')}
              </Typography>
              <Typography variant="body1">{selectedReview.type}</Typography>
            </Box>

            {/* Priority */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.priority')}
              </Typography>
              <Chip
                label={
                  selectedReview.priority === PRIORITY_HIGH
                    ? t('page.reviewQueue.priorityHigh')
                    : selectedReview.priority === PRIORITY_MEDIUM
                    ? t('page.reviewQueue.priorityMedium')
                    : t('page.reviewQueue.priorityLow')
                }
                color={
                  selectedReview.priority === PRIORITY_HIGH
                    ? 'error'
                    : selectedReview.priority === PRIORITY_MEDIUM
                    ? 'warning'
                    : 'success'
                }
                size="small"
              />
            </Box>

            {/* Submitter */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.submitter')}
              </Typography>
              <Typography variant="body1">{selectedReview.submitter}</Typography>
            </Box>

            {/* Submitted At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.submittedAt')}
              </Typography>
              <Typography variant="body1">{selectedReview.submittedAt}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t('page.reviewQueue.status')}
              </Typography>
              <Chip
                label={
                  selectedReview.status === STATUS_PENDING
                    ? t('page.reviewQueue.statusPending')
                    : selectedReview.status === STATUS_APPROVED
                    ? t('page.reviewQueue.statusApproved')
                    : selectedReview.status === STATUS_REJECTED
                    ? t('page.reviewQueue.statusRejected')
                    : selectedReview.status
                }
                size="small"
              />
            </Box>

            {/* Item Detail - Loading state */}
            {detailLoading && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t('page.reviewQueue.viewDetails')}
                </Typography>
                <Typography variant="body1">{t('common.loading')}</Typography>
              </Box>
            )}

            {/* Item Detail - Content */}
            {itemDetail && !detailLoading && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t('page.reviewQueue.viewDetails')}
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {typeof itemDetail.content === 'string'
                    ? itemDetail.content
                    : JSON.stringify(itemDetail.content, null, 2)}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </DetailDrawer>

      {/* Approve Confirm Dialog - Phase 6 API Integration */}
      <ConfirmDialog
        open={approveDialogOpen}
        onClose={() => setApproveDialogOpen(false)}
        onConfirm={handleApprove}
        title={t('page.reviewQueue.approve')}
        message={t('page.reviewQueue.emptyDescription')}
        confirmText={t('page.reviewQueue.approve')}
        cancelText={t('common.cancel')}
        loading={actionLoading}
      />

      {/* Reject Dialog - Phase 6 API Integration */}
      <Dialog
        open={rejectDialogOpen}
        onClose={() => {
          setRejectDialogOpen(false)
          setRejectReason('')
        }}
      >
        <DialogTitle>{t('page.reviewQueue.reject')}</DialogTitle>
        <DialogContent>
          <TextField
            label={t('page.reviewQueue.rejectReasonLabel')}
            placeholder={t('page.reviewQueue.rejectReasonPlaceholder')}
            fullWidth
            multiline
            rows={4}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setRejectDialogOpen(false)
              setRejectReason('')
            }}
            disabled={actionLoading}
          >
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleReject}
            variant="contained"
            color="error"
            disabled={actionLoading || !rejectReason.trim()}
          >
            {t('page.reviewQueue.reject')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
