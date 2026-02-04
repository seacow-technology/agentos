/**
 * DecisionTimelinePage - 决策时间线页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Phase 3 Integration: 添加 DetailDrawer
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect } from 'react'
import { Box, Typography, Chip } from '@mui/material'
import { TextField, Select, MenuItem } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import { brainosService } from '@/services'

// ===================================
// Types
// ===================================

interface DecisionRow {
  id: number
  decision: string
  context: string
  timestamp: string
  confidence: number
  status: string
}


/**
 * DecisionTimelinePage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function DecisionTimelinePage() {
  const [loading, setLoading] = useState(true)
  const [decisions, setDecisions] = useState<any[]>([])

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedDecision, setSelectedDecision] = useState<DecisionRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Data Fetching - Real API Integration
  // ===================================
  useEffect(() => {
    const fetchDecisions = async () => {
      setLoading(true)
      try {
        const response = await brainosService.listGovernanceDecisions({ limit: 100 })
        // Map GovernanceDecision to DecisionRow for UI
        const mappedDecisions = response.records.map((d) => ({
          id: d.decision_id,
          decision: d.decision_type || 'Unknown Decision',
          context: d.seed || '',
          timestamp: d.timestamp,
          confidence: d.confidence_score || 0,
          status: d.status,
        }))
        setDecisions(mappedDecisions)
      } catch (err) {
        console.error('Failed to fetch decisions:', err)
        setDecisions([])
      } finally {
        setLoading(false)
      }
    }

    fetchDecisions()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.decisionTimeline.title'),
    subtitle: t('page.decisionTimeline.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => console.log('Refresh decisions'),
    },
    {
      key: 'export',
      label: t('common.export'),
      variant: 'contained',
      onClick: () => console.log('Export decisions'),
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: DecisionRow) => {
    setSelectedDecision(row)
    setDrawerOpen(true)
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
      field: 'decision',
      headerName: t('page.decisionTimeline.columnDecision'),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'context',
      headerName: t('page.decisionTimeline.columnContext'),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'timestamp',
      headerName: t('page.decisionTimeline.columnTimestamp'),
      width: 180,
    },
    {
      field: 'confidence',
      headerName: t('page.decisionTimeline.columnConfidence'),
      width: 120,
      valueFormatter: (params: any) => `${((params.value as number) * 100).toFixed(0)}%`,
    },
    {
      field: 'status',
      headerName: t('form.field.status'),
      width: 120,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={decisions}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t('page.decisionTimeline.searchPlaceholder')}
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
                  label={t('form.field.status')}
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value="all">{t('page.decisionTimeline.statusAll')}</MenuItem>
                  <MenuItem value="approved">{t('page.decisionTimeline.statusApproved')}</MenuItem>
                  <MenuItem value="rejected">{t('page.decisionTimeline.statusRejected')}</MenuItem>
                  <MenuItem value="pending">{t('page.decisionTimeline.statusPending')}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setStatusFilter('all')
              },
            },
            {
              key: 'apply',
              label: t('common.apply'),
              variant: 'contained',
              onClick: () => {}, // 🔒 No-Interaction: 空函数
            },
          ]}
        />
      }
      emptyState={{
        title: t('page.decisionTimeline.noDecisions'),
        description: t('page.decisionTimeline.noDecisionsDesc'),
        actions: [
          {
            label: t('common.refresh'),
            onClick: () => {}, // 🔒 No-Interaction: 空函数
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: decisions.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedDecision?.decision || ''}
      >
        {selectedDecision && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                ID
              </Typography>
              <Typography variant="body1">{selectedDecision.id}</Typography>
            </Box>

            {/* Context */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.decisionTimeline.labelContext)}
              </Typography>
              <Typography variant="body1">{selectedDecision.context}</Typography>
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.decisionTimeline.labelTimestamp)}
              </Typography>
              <Typography variant="body1">{selectedDecision.timestamp}</Typography>
            </Box>

            {/* Confidence */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.decisionTimeline.labelConfidence)}
              </Typography>
              <Typography variant="body1">
                {(selectedDecision.confidence * 100).toFixed(0)}%
              </Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.decisionTimeline.labelStatus)}
              </Typography>
              <Chip
                label={selectedDecision.status}
                color={
                  selectedDecision.status === 'Approved'
                    ? 'success'
                    : selectedDecision.status === 'Rejected'
                    ? 'error'
                    : 'warning'
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
