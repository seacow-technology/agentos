/**
 * FindingsPage - 发现管理页面 (Governance Findings)
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.findings.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 3 Integration: 添加 DetailDrawer + DeleteConfirmDialog
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ Phase 6 Integration: Real API with networkosService.listFindings()
 */

/* eslint-disable react/jsx-no-literals */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, StatCard, TextField, Select, MenuItem, Chip, Button, Box, Typography, Grid } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import { BugIcon, LinkOffIcon, WarningIcon, ScheduleIcon } from '@/ui/icons'
import { networkosService, type SecurityFinding } from '@/services/networkos.service'
import { toast } from '@/ui/feedback'

// ===================================
// Types - Using SecurityFinding from service
// ===================================

// Use SecurityFinding directly as FindingRow
type FindingRow = SecurityFinding

/**
 * FindingsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🎨 7列表格，包含 actions 列（renderCell 显示 Chip）
 */
export default function FindingsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter + Data Loading)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  const [findings, setFindings] = useState<FindingRow[]>([])
  const [loading, setLoading] = useState(false)

  // P1-10: Pagination state
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [totalCount, setTotalCount] = useState(0)

  // Stats state
  const [stats, setStats] = useState({
    totalFindings: 0,
    unlinkedCount: 0,
    bySeverity: { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 },
    byWindow: { '24h': 0, '7d': 0, '30d': 0 },
  })

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedFinding, setSelectedFinding] = useState<FindingRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // API Functions - Phase 6 Integration
  // ===================================
  const loadFindings = useCallback(async () => {
    setLoading(true)
    try {
      // Build API parameters
      const params: {
        severity?: string;
        status?: string;
        offset?: number;
        limit?: number;
      } = {
        offset: page * pageSize,
        limit: pageSize,
      }

      if (severityFilter !== 'all') {
        params.severity = severityFilter
      }
      if (statusFilter !== 'all') {
        params.status = statusFilter
      }

      // Call real API
      const response = await networkosService.listFindings(params)

      setFindings((response?.findings || []) as FindingRow[])
      setTotalCount(response?.total || 0)

      toast.success(t(K.page.findings.loadSuccess))
    } catch (error) {
      console.error('Failed to load findings:', error)
      toast.error(t(K.page.findings.loadFailed))
      setFindings([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, severityFilter, statusFilter, t])

  const loadStats = useCallback(async () => {
    try {
      // Calculate stats from findings data (backend max limit is 500)
      const allFindings = await networkosService.listFindings({ limit: 500 })

      // Defensive check: ensure findings array exists
      const findingsArray = allFindings?.findings || []

      const criticalCount = findingsArray.filter(f => f.severity === 'critical').length
      const last24hCount = findingsArray.filter(f => {
        const discoveredTime = new Date(f.discovered_at).getTime()
        const now = Date.now()
        return (now - discoveredTime) < 24 * 60 * 60 * 1000
      }).length

      setStats({
        totalFindings: allFindings?.total || 0,
        unlinkedCount: 0, // Not tracked in API yet
        bySeverity: {
          CRITICAL: criticalCount,
          HIGH: findingsArray.filter(f => f.severity === 'high').length,
          MEDIUM: findingsArray.filter(f => f.severity === 'medium').length,
          LOW: findingsArray.filter(f => f.severity === 'low').length,
        },
        byWindow: {
          '24h': last24hCount,
          '7d': 0, // Calculate if needed
          '30d': 0, // Calculate if needed
        },
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
      // Keep default stats
    }
  }, [])

  const handleRefresh = async () => {
    await Promise.all([loadFindings(), loadStats()])
  }

  const handleUpdateStatus = async (findingId: string, status: 'new' | 'acknowledged' | 'in_progress' | 'resolved' | 'dismissed') => {
    try {
      await networkosService.updateFindingStatus(findingId, status)
      toast.success(t(K.page.findings.updateSuccess))
      await loadFindings()
      setDrawerOpen(false)
    } catch (error) {
      console.error('Failed to update finding status:', error)
      toast.error(t(K.page.findings.updateFailed))
    }
  }

  const handleAcknowledge = async () => {
    if (selectedFinding) {
      await handleUpdateStatus(selectedFinding.id, 'acknowledged')
    }
  }

  const handleResolve = async () => {
    if (selectedFinding) {
      await handleUpdateStatus(selectedFinding.id, 'resolved')
    }
  }

  const handleDismiss = async () => {
    if (selectedFinding) {
      await handleUpdateStatus(selectedFinding.id, 'dismissed')
    }
  }

  // ===================================
  // Effects - Load data on mount and filter changes
  // ===================================
  useEffect(() => {
    loadFindings()
    loadStats()
  }, [loadFindings, loadStats]) // P1-8, P1-10: Reload when filters or pagination change

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.findings.title),
    subtitle: t(K.page.findings.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'contained',
      onClick: handleRefresh,
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: FindingRow) => {
    setSelectedFinding(row)
    setDrawerOpen(true)
  }


  // P1-10: Pagination handlers
  const handlePageChange = (newPage: number) => {
    setPage(newPage)
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(0) // Reset to first page when page size changes
  }


  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'finding_id',
      headerName: t(K.page.findings.findingId),
      width: 150,
    },
    {
      field: 'title',
      headerName: t(K.page.findings.findingTitle),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'severity',
      headerName: t(K.page.findings.severity),
      width: 120,
      renderCell: (params) => {
        const severityColorMap: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning' | 'info'> = {
          critical: 'error',
          high: 'error',
          medium: 'warning',
          low: 'info',
        }
        const chipSize = 'small' as const
        return (
          <Chip
            label={t(K.page.findings[`severity${params.value.charAt(0).toUpperCase() + params.value.slice(1)}` as keyof typeof K.page.findings])}
            color={severityColorMap[params.value as string] || 'default'}
            size={chipSize}
          />
        )
      },
    },
    {
      field: 'category',
      headerName: t(K.page.findings.category),
      width: 150,
      renderCell: (params) => {
        return t(K.page.findings[`category${params.value.charAt(0).toUpperCase() + params.value.slice(1)}` as keyof typeof K.page.findings])
      },
    },
    {
      field: 'discovered_at',
      headerName: t(K.page.findings.discoveredAt),
      width: 180,
    },
    {
      field: 'status',
      headerName: t(K.page.findings.status),
      width: 150,
      renderCell: (params) => {
        const statusColorMap: Record<string, 'default' | 'primary' | 'success' | 'error' | 'warning' | 'info'> = {
          new: 'error',
          in_progress: 'warning',
          acknowledged: 'info',
          resolved: 'success',
          dismissed: 'default',
        }
        const chipSize = 'small' as const
        return (
          <Chip
            label={t(K.page.findings[`status${params.value.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join('')}` as keyof typeof K.page.findings])}
            color={statusColorMap[params.value as string] || 'default'}
            size={chipSize}
          />
        )
      },
    },
  ]

  // ===================================
  // Render: Stats Dashboard + TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      {/* P0-6: Statistics Dashboard */}
      <Box sx={{ mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title={t(K.page.findings.totalFindings)}
              value={stats.totalFindings.toString()}
              icon={<BugIcon />}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title={t(K.page.findings.unlinkedFindings)}
              value={stats.unlinkedCount.toString()}
              icon={<LinkOffIcon />}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title={t(K.page.findings.criticalFindings)}
              value={stats.bySeverity.CRITICAL.toString()}
              icon={<WarningIcon />}
              changeType="decrease"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title={t(K.page.findings.last24h)}
              value={stats.byWindow['24h'].toString()}
              icon={<ScheduleIcon />}
            />
          </Grid>
        </Grid>
      </Box>

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
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.findings.allSeverities)}</MenuItem>
                  <MenuItem value="critical">{t(K.page.findings.severityCritical)}</MenuItem>
                  <MenuItem value="high">{t(K.page.findings.severityHigh)}</MenuItem>
                  <MenuItem value="medium">{t(K.page.findings.severityMedium)}</MenuItem>
                  <MenuItem value="low">{t(K.page.findings.severityLow)}</MenuItem>
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
                  <MenuItem value="all">{t(K.page.findings.allStatus)}</MenuItem>
                  <MenuItem value="new">{t(K.page.findings.statusNew)}</MenuItem>
                  <MenuItem value="acknowledged">{t(K.page.findings.statusAcknowledged)}</MenuItem>
                  <MenuItem value="in_progress">{t(K.page.findings.statusInProgress)}</MenuItem>
                  <MenuItem value="resolved">{t(K.page.findings.statusResolved)}</MenuItem>
                  <MenuItem value="dismissed">{t(K.page.findings.statusDismissed)}</MenuItem>
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
                setSeverityFilter('all')
                setStatusFilter('all')
              },
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
        title: t(K.page.findings.emptyTitle),
        description: t(K.page.findings.emptyDescription),
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
        total: totalCount, // P1-10: Use total count from API
        onPageChange: handlePageChange, // P1-10: Handle page change
        onPageSizeChange: handlePageSizeChange, // P1-10: Handle page size change
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedFinding?.title || ''}
        actions={
          <>
            <Button
              variant="contained"
              color="success"
              onClick={handleResolve}
              disabled={selectedFinding?.status === 'resolved'}
            >
              {t(K.page.findings.resolve)}
            </Button>
            <Button
              variant="outlined"
              onClick={handleAcknowledge}
              disabled={selectedFinding?.status === 'acknowledged' || selectedFinding?.status === 'resolved'}
            >
              {t(K.page.findings.acknowledge)}
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={handleDismiss}
              disabled={selectedFinding?.status === 'dismissed' || selectedFinding?.status === 'resolved'}
            >
              {t(K.page.findings.dismiss)}
            </Button>
          </>
        }
      >
        {selectedFinding && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Finding ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.findings.findingId)}
              </Typography>
              <Typography variant="body1">{selectedFinding.finding_id}</Typography>
            </Box>

            {/* Severity */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.findings.severity)}
              </Typography>
              <Chip
                label={t(K.page.findings[`severity${selectedFinding.severity.charAt(0).toUpperCase() + selectedFinding.severity.slice(1)}` as keyof typeof K.page.findings])}
                color={
                  selectedFinding.severity === 'critical'
                    ? 'error'
                    : selectedFinding.severity === 'high'
                    ? 'error'
                    : selectedFinding.severity === 'medium'
                    ? 'warning'
                    : 'info'
                }
                size="small"
              />
            </Box>

            {/* Category */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.findings.category)}
              </Typography>
              <Typography variant="body1">
                {t(K.page.findings[`category${selectedFinding.category.charAt(0).toUpperCase() + selectedFinding.category.slice(1)}` as keyof typeof K.page.findings])}
              </Typography>
            </Box>

            {/* Description */}
            {selectedFinding.description && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.findings.description)}
                </Typography>
                <Typography variant="body1">{selectedFinding.description}</Typography>
              </Box>
            )}

            {/* Source */}
            {selectedFinding.source && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.findings.source)}
                </Typography>
                <Typography variant="body1">{selectedFinding.source}</Typography>
              </Box>
            )}

            {/* Evidence */}
            {selectedFinding.evidence && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.findings.evidence)}
                </Typography>
                <Typography variant="body1">{selectedFinding.evidence}</Typography>
              </Box>
            )}

            {/* Recommendation */}
            {selectedFinding.recommendation && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.findings.recommendation)}
                </Typography>
                <Typography variant="body1">{selectedFinding.recommendation}</Typography>
              </Box>
            )}

            {/* Impact */}
            {selectedFinding.impact && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.findings.impact)}
                </Typography>
                <Typography variant="body1">{selectedFinding.impact}</Typography>
              </Box>
            )}

            {/* Discovered At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.findings.discoveredAt)}
              </Typography>
              <Typography variant="body1">{selectedFinding.discovered_at}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.findings.status)}
              </Typography>
              <Chip
                label={t(K.page.findings[`status${selectedFinding.status.split('_').map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join('')}` as keyof typeof K.page.findings])}
                color={
                  selectedFinding.status === 'resolved'
                    ? 'success'
                    : selectedFinding.status === 'in_progress'
                    ? 'warning'
                    : selectedFinding.status === 'acknowledged'
                    ? 'info'
                    : selectedFinding.status === 'dismissed'
                    ? 'default'
                    : 'error'
                }
                size="small"
              />
            </Box>
          </Box>
        )}
      </DetailDrawer>

    </>
  )
}
