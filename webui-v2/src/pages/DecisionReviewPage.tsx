/**
 * DecisionReviewPage - Decision Review Management
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
import { TextField, Select, MenuItem, Chip, Box, Typography, Button, Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { brainosService } from '@/services/brainos.service'
import type {
  GovernanceDecision,
  ReplayDecisionResponse,
} from '@/services/brainos.service'

// ===================================
// Types
// ===================================

interface DecisionRow {
  id: string
  decision_type: 'NAVIGATION' | 'COMPARE' | 'HEALTH'
  seed: string
  status: 'PENDING' | 'APPROVED' | 'BLOCKED' | 'SIGNED' | 'FAILED'
  final_verdict: 'ALLOW' | 'WARN' | 'BLOCK' | 'REQUIRE_SIGNOFF'
  confidence_score?: number
  timestamp: string
}

// ===================================
// Constants
// ===================================

const EMPTY_PLACEHOLDER = '-'
const STATUS_PENDING = 'PENDING'
const STATUS_APPROVED = 'APPROVED'
const STATUS_SIGNED = 'SIGNED'
const STATUS_ALL = 'all'

const VERDICT_ALLOW = 'ALLOW'
const VERDICT_WARN = 'WARN'
const VERDICT_BLOCK = 'BLOCK'
const VERDICT_REQUIRE_SIGNOFF = 'REQUIRE_SIGNOFF'

/**
 * DecisionReviewPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * FilterBar: Search(4) + Status(4)
 * Table: 6 columns with status chip display
 */
export default function DecisionReviewPage() {
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
  const [selectedDetail, setSelectedDetail] = useState<GovernanceDecision | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [replayData, setReplayData] = useState<ReplayDecisionResponse | null>(null)
  const [replayLoading, setReplayLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // ===================================
  // State - Dialogs
  // ===================================
  const [signoffDialogOpen, setSignoffDialogOpen] = useState(false)
  const [signoffSigner, setSignoffSigner] = useState('')
  const [signoffNote, setSignoffNote] = useState('')

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t('page.decisionReview.title'),
    subtitle: t('page.decisionReview.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('page.decisionReview.refresh'),
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
      const apiStatus = statusFilter === STATUS_ALL ? undefined : (statusFilter as 'PENDING' | 'APPROVED' | 'BLOCKED' | 'SIGNED' | 'FAILED')
      const apiType = typeFilter === 'all' ? undefined : (typeFilter as 'NAVIGATION' | 'COMPARE' | 'HEALTH')

      const response = await brainosService.listGovernanceDecisions({
        status: apiStatus,
        decision_type: apiType,
        limit: 100, // governance API doesn't have pagination yet
      })

      // Map governance decisions to table rows
      const records = response?.records || []
      const rows: DecisionRow[] = records.map((record) => ({
        id: record.decision_id,
        decision_type: record.decision_type,
        seed: record.seed,
        status: record.status,
        final_verdict: record.final_verdict,
        confidence_score: record.confidence_score,
        timestamp: record.timestamp,
      }))

      setDecisions(rows)
      setTotal(rows.length)
      toast.success(t('page.decisionReview.loadSuccess'))
    } catch (error) {
      console.error('Failed to fetch decisions:', error)
      toast.error(t('page.decisionReview.loadFailed'))
      setDecisions([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, typeFilter, t])

  // ===================================
  // API - Load Decision Detail and Replay
  // ===================================
  const loadDecisionDetail = useCallback(async (decisionId: string) => {
    setReplayLoading(true)
    try {
      // Load both detail and replay data in parallel
      const [detailResponse, replayResponse] = await Promise.all([
        brainosService.getGovernanceDecision(decisionId),
        brainosService.replayGovernanceDecision(decisionId).catch(() => null),
      ])

      setSelectedDetail(detailResponse.decision)
      setReplayData(replayResponse)
    } catch (error) {
      console.error('Failed to load decision detail:', error)
      toast.error(t('page.decisionReview.detailLoadFailed'))
      setSelectedDetail(null)
      setReplayData(null)
    } finally {
      setReplayLoading(false)
    }
  }, [t])

  // ===================================
  // API - Sign-off Decision
  // ===================================
  const handleSignoff = useCallback(async () => {
    if (!selectedDecision || !signoffSigner.trim() || !signoffNote.trim()) return

    setActionLoading(true)
    try {
      await brainosService.signoffGovernanceDecision(selectedDecision.id, {
        signed_by: signoffSigner,
        note: signoffNote,
      })
      toast.success(t('page.decisionReview.signoffSuccess'))
      setSignoffDialogOpen(false)
      setDrawerOpen(false)
      setSignoffSigner('')
      setSignoffNote('')
      await fetchDecisions()
    } catch (error) {
      console.error('Failed to sign off decision:', error)
      toast.error(t('page.decisionReview.signoffFailed'))
    } finally {
      setActionLoading(false)
    }
  }, [selectedDecision, signoffSigner, signoffNote, t, fetchDecisions])

  // ===================================
  // Handlers
  // ===================================
  const handleRowClick = useCallback((row: DecisionRow) => {
    setSelectedDecision(row)
    setDrawerOpen(true)
    void loadDecisionDetail(row.id)
  }, [loadDecisionDetail])

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
      decision.seed.toLowerCase().includes(searchQuery.toLowerCase()) ||
      decision.decision_type.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesSearch
  })

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'decision_type',
      headerName: t('page.decisionReview.decisionType'),
      width: 130,
    },
    {
      field: 'seed',
      headerName: t('page.decisionReview.seed'),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'final_verdict',
      headerName: t('page.decisionReview.verdict'),
      width: 150,
      renderCell: (params) => {
        const verdict = params.value as string
        const color = verdict === VERDICT_BLOCK ? 'error' :
                     verdict === VERDICT_REQUIRE_SIGNOFF ? 'warning' :
                     verdict === VERDICT_WARN ? 'info' : 'success'
        const label = verdict === VERDICT_ALLOW
          ? t('page.decisionReview.verdictAllow')
          : verdict === VERDICT_WARN
          ? t('page.decisionReview.verdictWarn')
          : verdict === VERDICT_BLOCK
          ? t('page.decisionReview.verdictBlock')
          : verdict === VERDICT_REQUIRE_SIGNOFF
          ? t('page.decisionReview.verdictSignoff')
          : verdict
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
      field: 'status',
      headerName: t('page.decisionReview.status'),
      width: 120,
      renderCell: (params) => {
        const status = params.value as string
        const color = status === STATUS_SIGNED ? 'success' :
                     status === STATUS_PENDING ? 'warning' :
                     status === STATUS_APPROVED ? 'info' : 'default'
        const label = status === STATUS_PENDING
          ? t('page.decisionReview.statusPending')
          : status === STATUS_APPROVED
          ? t('page.decisionReview.statusApproved')
          : status === STATUS_SIGNED
          ? t('page.decisionReview.statusSigned')
          : status
        return <Chip label={label} color={color} size="small" />
      },
    },
    {
      field: 'confidence_score',
      headerName: t('page.decisionReview.confidence'),
      width: 110,
      renderCell: (params) => {
        const score = params.value as number | undefined
        return score !== undefined ? `${(score * 100).toFixed(0)}%` : EMPTY_PLACEHOLDER
      },
    },
    {
      field: 'timestamp',
      headerName: t('page.decisionReview.timestamp'),
      width: 180,
      renderCell: (params) => {
        const timestamp = params.value as string
        return new Date(timestamp).toLocaleString()
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
                  placeholder={t('page.decisionReview.searchPlaceholder')}
                  fullWidth
                  size="small"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t('page.decisionReview.filterType')}
                  fullWidth
                  size="small"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  <MenuItem value="all">{t('page.decisionReview.filterTypeAll')}</MenuItem>
                  <MenuItem value="NAVIGATION">{t('page.decisionReview.typeNavigation')}</MenuItem>
                  <MenuItem value="COMPARE">{t('page.decisionReview.typeCompare')}</MenuItem>
                  <MenuItem value="HEALTH">{t('page.decisionReview.typeHealth')}</MenuItem>
                </Select>
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  label={t('page.decisionReview.filterStatus')}
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value={STATUS_ALL}>{t('page.decisionReview.filterStatusAll')}</MenuItem>
                  <MenuItem value={STATUS_PENDING}>{t('page.decisionReview.statusPending')}</MenuItem>
                  <MenuItem value={STATUS_APPROVED}>{t('page.decisionReview.statusApproved')}</MenuItem>
                  <MenuItem value={STATUS_SIGNED}>{t('page.decisionReview.statusSigned')}</MenuItem>
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
        title: t('page.decisionReview.emptyTitle'),
        description: t('page.decisionReview.emptyDescription'),
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

      {/* Detail Drawer - Governance API Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false)
          setSelectedDetail(null)
          setReplayData(null)
        }}
        title={selectedDecision ? `${selectedDecision.decision_type}: ${selectedDecision.seed}` : ''}
        actions={
          selectedDetail?.final_verdict === VERDICT_REQUIRE_SIGNOFF &&
          selectedDetail?.status === STATUS_PENDING ? (
            <Button
              variant="contained"
              color="warning"
              disabled={actionLoading}
              onClick={() => setSignoffDialogOpen(true)}
            >
              {t('page.decisionReview.signoff')}
            </Button>
          ) : null
        }
      >
        {selectedDetail && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Basic Info */}
            <Box>
              <Typography variant="h6" gutterBottom>{t('page.decisionReview.basicInfo')}</Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('page.decisionReview.decisionId')}</Typography>
                  <Typography variant="body1">{selectedDetail.decision_id}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('page.decisionReview.seed')}</Typography>
                  <Typography variant="body1">{selectedDetail.seed}</Typography>
                </Box>
                <Box>
                  <Typography variant="body2" color="text.secondary">{t('page.decisionReview.timestamp')}</Typography>
                  <Typography variant="body1">{new Date(selectedDetail.timestamp).toLocaleString()}</Typography>
                </Box>
                {selectedDetail.confidence_score !== undefined && (
                  <Box>
                    <Typography variant="body2" color="text.secondary">{t('page.decisionReview.confidence')}</Typography>
                    <Typography variant="body1">{(selectedDetail.confidence_score * 100).toFixed(0)}%</Typography>
                  </Box>
                )}
              </Box>
            </Box>

            {/* Integrity Check */}
            {selectedDetail.integrity_check && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.integrityCheck')}</Typography>
                <Chip
                  label={selectedDetail.integrity_check.passed ? t('page.decisionReview.integrityPassed') : t('page.decisionReview.integrityFailed')}
                  color={selectedDetail.integrity_check.passed ? 'success' : 'error'}
                  icon={selectedDetail.integrity_check.passed ? <span>✅</span> : <span>❌</span>}
                />
              </Box>
            )}

            {/* Triggered Rules */}
            {selectedDetail.rules_triggered && selectedDetail.rules_triggered.length > 0 && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.triggeredRules')}</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {selectedDetail.rules_triggered.map((rule, idx) => (
                    <Box key={idx} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Typography variant="body1" fontWeight="bold">{rule.rule_name || rule.rule_id}</Typography>
                        <Chip label={rule.action} size="small" color={rule.action === 'BLOCK' ? 'error' : 'default'} />
                      </Box>
                      {rule.rationale && (
                        <Typography variant="body2" color="text.secondary">{rule.rationale}</Typography>
                      )}
                    </Box>
                  ))}
                </Box>
              </Box>
            )}

            {/* Signoff Info */}
            {selectedDetail.signoff && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.signoffInfo')}</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="body2"><strong>{t('page.decisionReview.signedBy')}:</strong> {selectedDetail.signoff.signed_by}</Typography>
                  <Typography variant="body2"><strong>{t('page.decisionReview.signedAt')}:</strong> {new Date(selectedDetail.signoff.sign_timestamp).toLocaleString()}</Typography>
                  <Typography variant="body2"><strong>{t('page.decisionReview.signNote')}:</strong> {selectedDetail.signoff.sign_note}</Typography>
                </Box>
              </Box>
            )}

            {/* Cognitive Comparison (Replay) */}
            {replayLoading && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.cognitiveComparison')}</Typography>
                <Typography variant="body2">{t('common.loading')}</Typography>
              </Box>
            )}
            {replayData && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.cognitiveComparison')}</Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
                  <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>{t('page.decisionReview.thenState')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                      {replayData.then_state ? JSON.stringify(replayData.then_state, null, 2).substring(0, 500) : t('page.decisionReview.noData')}
                    </Typography>
                  </Box>
                  <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                    <Typography variant="subtitle2" gutterBottom>{t('page.decisionReview.nowState')}</Typography>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>
                      {replayData.now_state ? JSON.stringify(replayData.now_state, null, 2).substring(0, 500) : t('page.decisionReview.noData')}
                    </Typography>
                  </Box>
                </Box>
                {replayData.changed_facts && replayData.changed_facts.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>{t('page.decisionReview.changedFacts')}</Typography>
                    <Box component="ul" sx={{ m: 0, pl: 2 }}>
                      {replayData.changed_facts.map((fact, idx) => (
                        <li key={idx}><Typography variant="body2">{fact}</Typography></li>
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            )}

            {/* Audit Trail */}
            {selectedDetail.audit_trail && (
              <Box>
                <Typography variant="h6" gutterBottom>{t('page.decisionReview.auditTrail')}</Typography>
                <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1, fontFamily: 'monospace', fontSize: '0.85rem', overflow: 'auto', maxHeight: 300 }}>
                  <pre>{JSON.stringify(selectedDetail.audit_trail, null, 2)}</pre>
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DetailDrawer>

      {/* Sign-off Dialog - Governance API Integration */}
      <Dialog
        open={signoffDialogOpen}
        onClose={() => {
          setSignoffDialogOpen(false)
          setSignoffSigner('')
          setSignoffNote('')
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t('page.decisionReview.signoffDialogTitle')}</DialogTitle>
        <DialogContent>
          {selectedDetail && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              {/* Decision Summary */}
              <Box sx={{ p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
                <Typography variant="subtitle2" gutterBottom>{t('page.decisionReview.decisionSummary')}</Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  <Typography variant="body2"><strong>{t('page.decisionReview.decisionType')}:</strong> {selectedDetail.decision_type}</Typography>
                  <Typography variant="body2"><strong>{t('page.decisionReview.seed')}:</strong> {selectedDetail.seed}</Typography>
                  <Typography variant="body2"><strong>{t('page.decisionReview.verdict')}:</strong> {selectedDetail.final_verdict}</Typography>
                </Box>
              </Box>

              {/* Why Signoff Required */}
              {selectedDetail.rules_triggered && selectedDetail.rules_triggered.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>{t('page.decisionReview.whySignoffRequired')}</Typography>
                  <Box component="ul" sx={{ m: 0, pl: 2 }}>
                    {selectedDetail.rules_triggered.map((rule, idx) => (
                      <li key={idx}>
                        <Typography variant="body2">{rule.rule_name || rule.rule_id}</Typography>
                        {rule.rationale && <Typography variant="caption" color="text.secondary">{rule.rationale}</Typography>}
                      </li>
                    ))}
                  </Box>
                </Box>
              )}

              {/* Signoff Form */}
              <TextField
                label={t('page.decisionReview.signedBy')}
                required
                fullWidth
                value={signoffSigner}
                onChange={(e) => setSignoffSigner(e.target.value)}
                placeholder={t('page.decisionReview.signerPlaceholder')}
              />
              <TextField
                label={t('page.decisionReview.signNote')}
                required
                fullWidth
                multiline
                rows={4}
                value={signoffNote}
                onChange={(e) => setSignoffNote(e.target.value)}
                placeholder={t('page.decisionReview.signNotePlaceholder')}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setSignoffDialogOpen(false)
              setSignoffSigner('')
              setSignoffNote('')
            }}
            disabled={actionLoading}
          >
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleSignoff}
            variant="contained"
            color="warning"
            disabled={actionLoading || !signoffSigner.trim() || !signoffNote.trim()}
          >
            {t('page.decisionReview.confirmSignoff')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
