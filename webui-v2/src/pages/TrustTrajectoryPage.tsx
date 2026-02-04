/**
 * TrustTrajectoryPage - Trust Trajectory View
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Phase 6: 真实API集成（getTrustTrajectory）
 * - ✅ State Handling: Loading/Success/Error/Empty states
 *
 * Features:
 * - Trust score timeline chart (line visualization)
 * - Trust state transitions table
 * - Current trust status card
 * - Entity search and time range selector
 * - Export trajectory data
 */

import { useState, useEffect } from 'react'
import { Box, Typography } from '@mui/material'
import { TextField, Select, MenuItem, FormControl, InputLabel, Chip } from '@/ui'
// eslint-disable-next-line no-restricted-imports
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { StatusCard, ErrorState, DashboardGrid, AppCard } from '@/ui'
import { DownloadIcon, TrendingUpIcon } from '@/ui/icons'
import { networkosService, type TrustTrajectory, type GetTrustTrajectoryRequest } from '@/services/networkos.service'

/**
 * TrustTrajectoryPage 组件
 *
 * 📊 Pattern: Custom Layout（Timeline + Stats + Table）
 * 🔌 API: GET /api/trust/trajectory/:entityId → networkosService.getTrustTrajectory()
 */
export default function TrustTrajectoryPage() {
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [trajectory, setTrajectory] = useState<TrustTrajectory | null>(null)
  const [entityId, setEntityId] = useState<string>('test_extension')
  const [searchInput, setSearchInput] = useState<string>('test_extension')
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d')

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.trustTrajectory.title),
    subtitle: t(K.page.trustTrajectory.subtitle),
  })

  // ===================================
  // Data Fetching
  // ===================================
  const fetchTrajectory = async (params?: GetTrustTrajectoryRequest) => {
    const targetEntityId = params?.entityId || entityId
    const targetTimeRange = params?.timeRange || timeRange

    if (!targetEntityId.trim()) {
      toast.error(t(K.page.trustTrajectory.searchPlaceholder))
      return
    }

    try {
      setLoading(true)
      setError(null)
      const response = await networkosService.getTrustTrajectory({
        entityId: targetEntityId,
        timeRange: targetTimeRange,
      })
      setTrajectory(response.trajectory)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t(K.page.trustTrajectory.loadFailed)
      setError(errorMessage)
      setTrajectory(null)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // Initial load with default entity
  useEffect(() => {
    fetchTrajectory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Event Handlers
  // ===================================
  const handleSearch = () => {
    if (searchInput.trim()) {
      setEntityId(searchInput.trim())
      fetchTrajectory({ entityId: searchInput.trim(), timeRange })
    }
  }

  const handleTimeRangeChange = (newTimeRange: '7d' | '30d' | '90d' | 'all') => {
    setTimeRange(newTimeRange)
    fetchTrajectory({ entityId, timeRange: newTimeRange })
  }

  const handleExport = () => {
    if (!trajectory) {
      toast.error(t(K.page.trustTrajectory.exportFailed))
      return
    }

    try {
      const dataStr = JSON.stringify(trajectory, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement('a')
      link.href = url
      link.download = `trust_trajectory_${entityId}_${new Date().toISOString()}.json`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(t(K.page.trustTrajectory.exportFailed))
    }
  }

  // ===================================
  // Page Actions
  // ===================================
  usePageActions([
    {
      key: 'refresh',
      label: t(K.page.trustTrajectory.refresh),
      variant: 'outlined',
      onClick: () => fetchTrajectory(),
    },
    {
      key: 'export',
      label: t(K.page.trustTrajectory.export),
      variant: 'outlined',
      onClick: handleExport,
      icon: <DownloadIcon />,
      disabled: !trajectory,
    },
  ])

  // ===================================
  // Helper Functions
  // ===================================
  const getStateColor = (state: 'EARNING' | 'STABLE' | 'DEGRADING'): 'running' | 'warning' | 'error' => {
    const colorMap: Record<string, 'running' | 'warning' | 'error'> = {
      EARNING: 'warning',
      STABLE: 'running',
      DEGRADING: 'error',
    }
    return colorMap[state] || 'warning'
  }

  const getStateLabel = (state: 'EARNING' | 'STABLE' | 'DEGRADING'): string => {
    const labelMap: Record<string, string> = {
      EARNING: t(K.page.trustTrajectory.stateEarning),
      STABLE: t(K.page.trustTrajectory.stateStable),
      DEGRADING: t(K.page.trustTrajectory.stateDegrading),
    }
    return labelMap[state] || state
  }

  const formatTimestamp = (timestamp_ms: number): string => {
    return new Date(timestamp_ms).toLocaleString()
  }

  const formatDuration = (hours: number): string => {
    if (hours < 24) {
      return `${Math.round(hours)}h`
    }
    const days = Math.floor(hours / 24)
    const remainingHours = Math.round(hours % 24)
    return `${days}d ${remainingHours}h`
  }

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading && !trajectory) {
    return (
      <Box>
        <DashboardGrid loading columns={3} gap={16}>
          {null}
        </DashboardGrid>
      </Box>
    )
  }

  // ===================================
  // Render: Error State
  // ===================================
  if (error && !trajectory) {
    return (
      <ErrorState
        error={error}
        onRetry={() => fetchTrajectory()}
        retryText={t('common.retry')}
      />
    )
  }

  // ===================================
  // Render: Empty State
  // ===================================
  if (!loading && !trajectory) {
    const h5Variant = 'h5'
    const body2Variant = 'body2'
    const textSecondary = 'text.secondary'
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant={h5Variant} gutterBottom>
          {t(K.page.trustTrajectory.emptyTitle)}
        </Typography>
        <Typography variant={body2Variant} color={textSecondary}>
          {t(K.page.trustTrajectory.emptyDescription)}
        </Typography>
      </Box>
    )
  }

  // ===================================
  // Render: Success State
  // ===================================
  if (!trajectory) return null

  const { current_state, score_history, transitions, stats } = trajectory

  // Prepare chart data
  const chartData = score_history.map((point) => ({
    timestamp: new Date(point.timestamp).toLocaleTimeString(),
    score: point.trust_score,
    state: point.state,
  }))

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Search and Filters */}
      <AppCard>
        <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            label={t(K.page.trustTrajectory.searchEntity)}
            placeholder={t(K.page.trustTrajectory.searchPlaceholder)}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') handleSearch()
            }}
            sx={{ flex: 1 }}
            size={'small' as const}
          />
          <FormControl size={'small' as const} sx={{ minWidth: 150 }}>
            <InputLabel>{t(K.page.trustTrajectory.timeRange)}</InputLabel>
            <Select
              value={timeRange}
              label={t(K.page.trustTrajectory.timeRange)}
              onChange={(e) => handleTimeRangeChange(e.target.value as '7d' | '30d' | '90d' | 'all')}
            >
              <MenuItem value={'7d' as const}>{t(K.page.trustTrajectory.last7Days)}</MenuItem>
              <MenuItem value={'30d' as const}>{t(K.page.trustTrajectory.last30Days)}</MenuItem>
              <MenuItem value={'90d' as const}>{t(K.page.trustTrajectory.last90Days)}</MenuItem>
              <MenuItem value={'all' as const}>{t(K.page.trustTrajectory.allTime)}</MenuItem>
            </Select>
          </FormControl>
        </Box>
      </AppCard>

      {/* Current Trust Status */}
      <DashboardGrid columns={4} gap={16}>
        <StatusCard
          title={t(K.page.trustTrajectory.currentTrust)}
          status={getStateColor(current_state.current_state)}
          statusLabel={getStateLabel(current_state.current_state)}
          description={t(K.page.trustTrajectory.trustScore) + ': ' + (stats.success_rate * 100).toFixed(1) + '%'}
          meta={[
            {
              key: 'timeInState',
              label: t(K.page.trustTrajectory.timeInState),
              value: formatDuration(stats.time_in_current_state_hours),
            },
            {
              key: 'successRate',
              label: t(K.page.trustTrajectory.successRate),
              value: (stats.success_rate * 100).toFixed(1) + '%',
            },
          ]}
          icon={<TrendingUpIcon />}
        />
        <StatusCard
          title={t(K.page.trustTrajectory.consecutiveSuccesses)}
          status={'running' as const}
          statusLabel={String(current_state.consecutive_successes)}
          description={t(K.page.trustTrajectory.successfulExecutions)}
        />
        <StatusCard
          title={t(K.page.trustTrajectory.policyViolations)}
          status={current_state.policy_rejections > 0 ? 'error' : 'running'}
          statusLabel={String(current_state.policy_rejections)}
          description={t(K.page.trustTrajectory.totalViolations)}
        />
        <StatusCard
          title={t(K.page.trustTrajectory.totalTransitions)}
          status={'running' as const}
          statusLabel={String(stats.total_transitions)}
          description={t(K.page.trustTrajectory.stateChanges)}
        />
      </DashboardGrid>

      {/* Trust Score Timeline */}
      <AppCard>
        <Box sx={{ p: 2 }}>
          <Typography variant={'h6' as const} gutterBottom>
            {t(K.page.trustTrajectory.scoreTimeline)}
          </Typography>
          <ResponsiveContainer width={'100%' as const} height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray={"3 3" as const} />
              <XAxis dataKey={"timestamp" as const} />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <ReferenceLine y={0.85} stroke={"green" as const} strokeDasharray={"3 3" as const} label={"STABLE threshold" as const} />
              <ReferenceLine y={0.5} stroke={"orange" as const} strokeDasharray={"3 3" as const} label={"EARNING threshold" as const} />
              <Line type={"monotone" as const} dataKey={"score" as const} stroke={"#1976d2" as const} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </Box>
      </AppCard>

      {/* Tier Changes Table */}
      <AppCard>
        <Box sx={{ p: 2 }}>
          <Typography variant={"h6" as const} gutterBottom>
            {t(K.page.trustTrajectory.tierChanges)}
          </Typography>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>{t(K.page.trustTrajectory.tableTimestamp)}</TableCell>
                  <TableCell>{t(K.page.trustTrajectory.tableOldState)}</TableCell>
                  <TableCell>{t(K.page.trustTrajectory.tableNewState)}</TableCell>
                  <TableCell>{t(K.page.trustTrajectory.tableTrigger)}</TableCell>
                  <TableCell>{t(K.page.trustTrajectory.tableExplain)}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {transitions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align={"center" as const}>
                      <Typography variant={"body2" as const} color={"text.secondary" as const}>
                        {t(K.page.trustTrajectory.noTransitions)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  transitions.map((transition) => (
                    <TableRow key={transition.transition_id}>
                      <TableCell>{formatTimestamp(transition.created_at_ms)}</TableCell>
                      <TableCell>
                        <Chip
                          label={getStateLabel(transition.old_state)}
                          color={getStateColor(transition.old_state) === 'running' ? 'success' : getStateColor(transition.old_state) === 'error' ? 'error' : 'warning'}
                          size={'small' as const}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={getStateLabel(transition.new_state)}
                          color={getStateColor(transition.new_state) === 'running' ? 'success' : getStateColor(transition.new_state) === 'error' ? 'error' : 'warning'}
                          size={'small' as const}
                        />
                      </TableCell>
                      <TableCell>{transition.trigger_event}</TableCell>
                      <TableCell>{transition.explain}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </AppCard>
    </Box>
  )
}
