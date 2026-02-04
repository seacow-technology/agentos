/**
 * GovernanceFindingsView - Governance Findings Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.governanceFindings.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 6 Integration: Real API with networkosService
 *
 * Features:
 * - Governance findings list (policy violations, trust anomalies, privilege abuse, audit failures)
 * - Filtering by type and severity
 * - DetailDrawer for finding details
 * - Export findings report
 * - Real-time data refresh
 */

import { useState, useEffect, useCallback } from 'react'
import { Box, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Chip, Button } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer, DeleteConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { networkosService } from '@/services/networkos.service'
import type { GovernanceFinding } from '@/services/networkos.service'

// ===================================
// Types
// ===================================

interface ListGovernanceFindingsRequest {
  type?: string
  severity?: string
  status?: string
  page?: number
  limit?: number
}

// ===================================
// Component
// ===================================

export default function GovernanceFindingsView() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [findings, setFindings] = useState<GovernanceFinding[]>([])
  const [loading, setLoading] = useState(false)

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // Pagination state
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [totalCount, setTotalCount] = useState(0)

  // Interaction state
  const [selectedFinding, setSelectedFinding] = useState<GovernanceFinding | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // ===================================
  // API Functions
  // ===================================

  const loadFindings = useCallback(async () => {
    setLoading(true)
    try {
      // Build request parameters
      const params: ListGovernanceFindingsRequest = {
        page: page + 1, // API uses 1-based pagination
        limit: pageSize,
      }

      if (typeFilter !== 'all') {
        params.type = typeFilter
      }
      if (severityFilter !== 'all') {
        params.severity = severityFilter
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter
      }

      // Call real API
      const response = await networkosService.listGovernanceFindings(params)
      setFindings(response.findings)
      setTotalCount(response.total)
    } catch (err) {
      console.error('Failed to load governance findings:', err)
      toast.error(t(K.page.governanceFindings.loadFailed))

      // Set empty data on error
      setFindings([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, typeFilter, severityFilter, statusFilter, t])

  const loadFindingDetail = async (findingId: string) => {
    try {
      const response = await networkosService.getGovernanceFinding(findingId)
      setSelectedFinding(response.finding)
    } catch (err) {
      console.error('Failed to load finding detail:', err)
      toast.error(t(K.page.governanceFindings.loadFailed))
    }
  }

  const handleRefresh = async () => {
    await loadFindings()
  }

  const handleExport = async () => {
    try {
      // TODO: Implement real export API when available
      // await networkosService.exportGovernanceFindings()
      toast.info(t(K.page.governanceFindings.exportReport))
    } catch (err) {
      console.error('Failed to export findings:', err)
      toast.error(t(K.page.governanceFindings.exportFailed))
    }
  }

  // ===================================
  // Effects
  // ===================================

  useEffect(() => {
    loadFindings()
  }, [loadFindings])

  // ===================================
  // Page Header and Actions
  // ===================================

  usePageHeader({
    title: t(K.page.governanceFindings.title),
    subtitle: t(K.page.governanceFindings.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.page.governanceFindings.refresh),
      variant: 'outlined',
      onClick: handleRefresh,
    },
    {
      key: 'export',
      label: t(K.page.governanceFindings.export),
      variant: 'contained',
      onClick: handleExport,
    },
  ])

  // ===================================
  // Interaction Handlers
  // ===================================

  const handleRowClick = (row: GovernanceFinding) => {
    setSelectedFinding(row)
    setDrawerOpen(true)
    // Optionally load detailed data
    loadFindingDetail(row.id)
  }

  const handleDelete = async () => {
    if (!selectedFinding) return
    try {
      await networkosService.deleteGovernanceFinding(selectedFinding.id)
      toast.success(t(K.page.governanceFindings.dismissedSuccess))
      setDeleteDialogOpen(false)
      setDrawerOpen(false)
      await loadFindings()
    } catch (err) {
      console.error('Failed to delete finding:', err)
      toast.error(t(K.page.governanceFindings.deleteFailed))
    }
  }

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0)
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setTypeFilter('all')
    setSeverityFilter('all')
    setStatusFilter('all')
  }

  // ===================================
  // Table Columns Definition
  // ===================================

  const columns: GridColDef[] = [
    {
      field: 'finding_id',
      headerName: t(K.page.governanceFindings.findingId),
      width: 120,
    },
    {
      field: 'type',
      headerName: t(K.page.governanceFindings.type),
      width: 150,
      renderCell: (params) => {
        const typeMap: Record<string, string> = {
          policy_violation: t(K.page.governanceFindings.typePolicyViolation),
          trust_anomaly: t(K.page.governanceFindings.typeTrustAnomaly),
          privilege_abuse: t(K.page.governanceFindings.typePrivilegeAbuse),
          audit_failure: t(K.page.governanceFindings.typeAuditFailure),
        }
        return typeMap[params.value as string] || params.value
      },
    },
    {
      field: 'severity',
      headerName: t(K.page.governanceFindings.severity),
      width: 120,
      renderCell: (params) => {
        const severityColorMap: Record<string, 'error' | 'warning' | 'info'> = {
          high: 'error',
          medium: 'warning',
          low: 'info',
        }
        const severityLabelMap: Record<string, string> = {
          high: t(K.page.governanceFindings.severityHigh),
          medium: t(K.page.governanceFindings.severityMedium),
          low: t(K.page.governanceFindings.severityLow),
        }
        return (
          <Chip
            label={severityLabelMap[params.value as string] || params.value}
            color={severityColorMap[params.value as string] || 'default'}
            size="small"
          />
        )
      },
    },
    {
      field: 'entity',
      headerName: t(K.page.governanceFindings.entity),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'discovered_at',
      headerName: t(K.page.governanceFindings.discoveredAt),
      width: 180,
    },
    {
      field: 'status',
      headerName: t(K.page.governanceFindings.status),
      width: 130,
      renderCell: (params) => {
        const statusColorMap: Record<string, 'error' | 'warning' | 'success'> = {
          open: 'error',
          investigating: 'warning',
          resolved: 'success',
        }
        const statusLabelMap: Record<string, string> = {
          open: t(K.page.governanceFindings.statusOpen),
          investigating: t(K.page.governanceFindings.statusInvestigating),
          resolved: t(K.page.governanceFindings.statusResolved),
        }
        return (
          <Chip
            label={statusLabelMap[params.value as string] || params.value}
            color={statusColorMap[params.value as string] || 'default'}
            size="small"
          />
        )
      },
    },
  ]

  // ===================================
  // Render
  // ===================================

  return (
    <>
      <TableShell
        loading={loading}
        rows={findings}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 3,
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
                width: 3,
                component: (
                  <Select
                    fullWidth
                    size="small"
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">{t(K.page.governanceFindings.allTypes)}</MenuItem>
                    <MenuItem value="policy_violation">
                      {t(K.page.governanceFindings.typePolicyViolation)}
                    </MenuItem>
                    <MenuItem value="trust_anomaly">
                      {t(K.page.governanceFindings.typeTrustAnomaly)}
                    </MenuItem>
                    <MenuItem value="privilege_abuse">
                      {t(K.page.governanceFindings.typePrivilegeAbuse)}
                    </MenuItem>
                    <MenuItem value="audit_failure">
                      {t(K.page.governanceFindings.typeAuditFailure)}
                    </MenuItem>
                  </Select>
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    fullWidth
                    size="small"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">{t(K.page.governanceFindings.allSeverities)}</MenuItem>
                    <MenuItem value="high">{t(K.page.governanceFindings.severityHigh)}</MenuItem>
                    <MenuItem value="medium">{t(K.page.governanceFindings.severityMedium)}</MenuItem>
                    <MenuItem value="low">{t(K.page.governanceFindings.severityLow)}</MenuItem>
                  </Select>
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    fullWidth
                    size="small"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value="all">{t(K.page.governanceFindings.allStatus)}</MenuItem>
                    <MenuItem value="open">{t(K.page.governanceFindings.statusOpen)}</MenuItem>
                    <MenuItem value="investigating">
                      {t(K.page.governanceFindings.statusInvestigating)}
                    </MenuItem>
                    <MenuItem value="resolved">{t(K.page.governanceFindings.statusResolved)}</MenuItem>
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
                onClick: loadFindings,
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.governanceFindings.emptyTitle),
          description: t(K.page.governanceFindings.emptyDescription),
          actions: [
            {
              label: t(K.common.refresh),
              onClick: handleRefresh,
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page,
          pageSize,
          total: totalCount,
          onPageChange: handlePageChange,
          onPageSizeChange: handlePageSizeChange,
        }}
        onRowClick={handleRowClick}
      />

      {/* Detail Drawer */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedFinding?.finding_id || ''}
        actions={
          <>
            <Button
              variant="contained"
              color="primary"
              onClick={() => {
                console.log('Investigate finding:', selectedFinding?.id)
                toast.info(t(K.page.governanceFindings.investigationStarted))
              }}
            >
              {t(K.page.governanceFindings.investigate)}
            </Button>
            <Button
              variant="outlined"
              color="success"
              onClick={() => {
                console.log('Resolve finding:', selectedFinding?.id)
                toast.success(t(K.page.governanceFindings.markedResolved))
                setDrawerOpen(false)
              }}
            >
              {t(K.page.governanceFindings.resolve)}
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={() => {
                setDrawerOpen(false)
                setDeleteDialogOpen(true)
              }}
            >
              {t(K.common.delete)}
            </Button>
          </>
        }
      >
        {selectedFinding && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Type */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.type)}
              </Typography>
              <Typography variant="body1">
                {
                  {
                    policy_violation: t(K.page.governanceFindings.typePolicyViolation),
                    trust_anomaly: t(K.page.governanceFindings.typeTrustAnomaly),
                    privilege_abuse: t(K.page.governanceFindings.typePrivilegeAbuse),
                    audit_failure: t(K.page.governanceFindings.typeAuditFailure),
                  }[selectedFinding.type]
                }
              </Typography>
            </Box>

            {/* Severity */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.severity)}
              </Typography>
              <Chip
                label={
                  {
                    high: t(K.page.governanceFindings.severityHigh),
                    medium: t(K.page.governanceFindings.severityMedium),
                    low: t(K.page.governanceFindings.severityLow),
                  }[selectedFinding.severity]
                }
                color={
                  {
                    high: 'error' as const,
                    medium: 'warning' as const,
                    low: 'info' as const,
                  }[selectedFinding.severity]
                }
                size="small"
              />
            </Box>

            {/* Entity */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.entity)}
              </Typography>
              <Typography variant="body1">{selectedFinding.entity}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.description)}
              </Typography>
              <Typography variant="body1">{selectedFinding.description}</Typography>
            </Box>

            {/* Discovered At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.discoveredAt)}
              </Typography>
              <Typography variant="body1">{selectedFinding.discovered_at}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governanceFindings.status)}
              </Typography>
              <Chip
                label={
                  {
                    open: t(K.page.governanceFindings.statusOpen),
                    investigating: t(K.page.governanceFindings.statusInvestigating),
                    resolved: t(K.page.governanceFindings.statusResolved),
                  }[selectedFinding.status]
                }
                color={
                  {
                    open: 'error' as const,
                    investigating: 'warning' as const,
                    resolved: 'success' as const,
                  }[selectedFinding.status]
                }
                size="small"
              />
            </Box>

            {/* Metadata */}
            {selectedFinding.metadata && Object.keys(selectedFinding.metadata).length > 0 && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.governanceFindings.additionalInfo)}
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Object.entries(selectedFinding.metadata).map(([key, value]) => (
                    <Box key={key} sx={{ display: 'flex', gap: 1 }}>
                      <Typography variant="body2" fontWeight="medium">
                        {key}:
                      </Typography>
                      <Typography variant="body2">{String(value)}</Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DetailDrawer>

      {/* Delete Confirm Dialog */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType={t(K.page.governanceFindings.resourceType)}
        resourceName={selectedFinding?.finding_id}
      />
    </>
  )
}
