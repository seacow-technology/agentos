/**
 * RiskTimelinePage - Risk Timeline View
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Custom Layout: Chart + Stats + Table
 * - ✅ Phase 6 Integration: Real API with riskService.getRiskTimeline()
 *
 * Features:
 * - Risk score timeline chart (line visualization)
 * - Multiple risk dimensions (Overall, Execution, Trust, Policy, Capability)
 * - Stats summary cards
 * - Risk scores table
 * - Dimension selector
 * - Time comparison dialog
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Box,
  Typography,
  Grid,
  CardContent,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
} from '@mui/material'
import { Chip, Select, MenuItem, FormControl, InputLabel } from '@/ui'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { TrendingUpIcon, TrendingDownIcon, SwapIcon, CompareIcon } from '@/ui/icons'
import { AppCard, LoadingState, ErrorState, EmptyState } from '@/ui'
import { DialogForm } from '@/ui/interaction'
import { riskService, type RiskScore, type RiskTimelineData } from '@/services/risk.service'

// ===================================
// Types (Imported from risk.service)
// ===================================
// interface RiskScore - imported from service
// interface RiskTimelineData - imported from service

// ===================================
// Dimension Breakdown Component (P2-9)
// ===================================

interface DimensionBreakdownProps {
  score: RiskScore
}

function DimensionBreakdown({ score }: DimensionBreakdownProps) {
  const { t } = useTextTranslation()

  // Prepare radar chart data
  const radarData = [
    {
      dimension: t(K.page.riskTimeline.dimensionExecution),
      value: score.execution_risk * 100,
      fullMark: 100,
    },
    {
      dimension: t(K.page.riskTimeline.dimensionTrust),
      value: score.trust_risk * 100,
      fullMark: 100,
    },
    {
      dimension: t(K.page.riskTimeline.dimensionPolicy),
      value: score.policy_risk * 100,
      fullMark: 100,
    },
    {
      dimension: t(K.page.riskTimeline.dimensionCapability),
      value: score.capability_risk * 100,
      fullMark: 100,
    },
    {
      dimension: t(K.page.riskTimeline.dimensionOverall),
      value: score.overall_score * 100,
      fullMark: 100,
    },
  ]

  // Get color based on risk value
  const getRadarColor = (value: number): string => {
    if (value >= 70) return '#f44336' // red
    if (value >= 40) return '#ff9800' // orange
    return '#4caf50' // green
  }

  return (
    <AppCard>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t(K.page.riskTimeline.dimensionBreakdownTitle)}
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <RadarChart data={radarData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="dimension" />
            <PolarRadiusAxis angle={90} domain={[0, 100]} />
            <Radar
              name="Risk Score"
              dataKey="value"
              stroke="#1976d2"
              fill="#1976d2"
              fillOpacity={0.6}
            />
          </RadarChart>
        </ResponsiveContainer>
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
          {radarData.map((item) => (
            <Box key={item.dimension} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Box
                sx={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  bgcolor: getRadarColor(item.value),
                }}
              />
              <Typography variant="body2" sx={{ flex: 1 }}>
                {item.dimension}
              </Typography>
              <Typography variant="body2" fontWeight="medium">
                {item.value.toFixed(1)}%
              </Typography>
            </Box>
          ))}
        </Box>
      </CardContent>
    </AppCard>
  )
}

// ===================================
// Risk Timeline Chart Component (P1-27)
// ===================================

interface RiskTimelineChartProps {
  data: RiskScore[]
  dimension: string
}

function RiskTimelineChart({ data, dimension }: RiskTimelineChartProps) {
  const { t } = useTextTranslation()

  // Get risk values based on selected dimension
  const getRiskValue = (score: RiskScore): number => {
    switch (dimension) {
      case 'execution':
        return score.execution_risk
      case 'trust':
        return score.trust_risk
      case 'policy':
        return score.policy_risk
      case 'capability':
        return score.capability_risk
      case 'overall':
      default:
        return score.overall_score
    }
  }

  // Calculate chart dimensions
  const maxValue = Math.max(...data.map(getRiskValue))
  const minValue = Math.min(...data.map(getRiskValue))
  const range = maxValue - minValue || 1
  const chartHeight = 300
  const chartWidth = 800
  const padding = 40

  // Create SVG path for line chart
  const points = data.map((score, index) => {
    const x = padding + (index / (data.length - 1)) * (chartWidth - 2 * padding)
    const value = getRiskValue(score)
    const y = chartHeight - padding - ((value - minValue) / range) * (chartHeight - 2 * padding)
    return { x, y, value, timestamp: score.timestamp }
  })

  const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')

  // Get risk color based on value
  const getRiskColor = (value: number): string => {
    if (value >= 0.7) return '#f44336' // error
    if (value >= 0.4) return '#ff9800' // warning
    return '#4caf50' // success
  }

  return (
    <AppCard>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t(K.page.riskTimeline.chartTitle)}
        </Typography>
        <Box
          sx={{
            position: 'relative',
            width: '100%',
            height: chartHeight,
            overflow: 'auto',
          }}
        >
          <svg width={chartWidth} height={chartHeight} style={{ display: 'block' }}>
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
              const y = chartHeight - padding - (tick * (chartHeight - 2 * padding))
              return (
                <g key={tick}>
                  <line
                    x1={padding}
                    y1={y}
                    x2={chartWidth - padding}
                    y2={y}
                    stroke="#e0e0e0"
                    strokeWidth={1}
                  />
                  <text
                    x={padding - 10}
                    y={y + 4}
                    textAnchor="end"
                    fontSize={12}
                    fill="#666"
                  >
                    {(tick * 100).toFixed(0)}%
                  </text>
                </g>
              )
            })}

            {/* Line path */}
            <path
              d={pathData}
              fill="none"
              stroke={getRiskColor(points[points.length - 1].value)}
              strokeWidth={2}
            />

            {/* Data points */}
            {points.map((point, index) => (
              <g key={index}>
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={4}
                  fill={getRiskColor(point.value)}
                />
                {/* X-axis labels */}
                {index % Math.ceil(data.length / 6) === 0 && (
                  <text
                    x={point.x}
                    y={chartHeight - padding + 20}
                    textAnchor="middle"
                    fontSize={10}
                    fill="#666"
                  >
                    {point.timestamp.split(' ')[1]}
                  </text>
                )}
              </g>
            ))}
          </svg>
        </Box>
        <Box sx={{ mt: 2, display: 'flex', gap: 2, justifyContent: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 16, height: 16, bgcolor: '#4caf50', borderRadius: 1 }} />
            <Typography variant="caption">{t(K.page.riskTimeline.riskLow)}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 16, height: 16, bgcolor: '#ff9800', borderRadius: 1 }} />
            <Typography variant="caption">{t(K.page.riskTimeline.riskMedium)}</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 16, height: 16, bgcolor: '#f44336', borderRadius: 1 }} />
            <Typography variant="caption">{t(K.page.riskTimeline.riskHigh)}</Typography>
          </Box>
        </Box>
      </CardContent>
    </AppCard>
  )
}

// ===================================
// Time Comparison Dialog Component (P2-10)
// ===================================

interface TimeComparisonDialogProps {
  open: boolean
  onClose: () => void
  beforeScore: RiskScore
  afterScore: RiskScore
}

function TimeComparisonDialog({
  open,
  onClose,
  beforeScore,
  afterScore,
}: TimeComparisonDialogProps) {
  const { t } = useTextTranslation()

  // Calculate delta
  const calculateDelta = (before: number, after: number): { value: number; percentage: string } => {
    const delta = after - before
    const percentage = before !== 0 ? ((delta / before) * 100).toFixed(1) : '0.0'
    return { value: delta, percentage }
  }

  // Render delta indicator
  const renderDelta = (before: number, after: number) => {
    const { value, percentage } = calculateDelta(before, after)
    const isIncrease = value > 0
    const isDecrease = value < 0

    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        {isIncrease && (
          <>
            <TrendingUpIcon fontSize="small" color="error" />
            <Typography variant="body2" color="error.main">
              +{percentage}%
            </Typography>
          </>
        )}
        {isDecrease && (
          <>
            <TrendingDownIcon fontSize="small" color="success" />
            <Typography variant="body2" color="success.main">
              {percentage}%
            </Typography>
          </>
        )}
        {!isIncrease && !isDecrease && (
          <Typography variant="body2" color="text.secondary">
            {t('common.noChange')}
          </Typography>
        )}
      </Box>
    )
  }

  // Render comparison row
  const renderComparisonRow = (
    label: string,
    beforeValue: number,
    afterValue: number
  ) => (
    <Box sx={{ py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
      <Typography variant="body2" fontWeight="medium" gutterBottom>
        {label}
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={5}>
          <Typography variant="body2" color="text.secondary">
            {t(K.page.riskTimeline.compareBefore)}
          </Typography>
          <Typography variant="h6">{(beforeValue * 100).toFixed(1)}%</Typography>
        </Grid>
        <Grid item xs={2} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {renderDelta(beforeValue, afterValue)}
        </Grid>
        <Grid item xs={5}>
          <Typography variant="body2" color="text.secondary">
            {t(K.page.riskTimeline.compareAfter)}
          </Typography>
          <Typography variant="h6">{(afterValue * 100).toFixed(1)}%</Typography>
        </Grid>
      </Grid>
    </Box>
  )

  return (
    <DialogForm
      open={open}
      onClose={onClose}
      title={t(K.page.riskTimeline.compareDialogTitle)}
      maxWidth="md"
      submitText={t('common.close')}
      onSubmit={onClose}
      submitDisabled={false}
    >
      <Box>
        {/* Timestamps */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.riskTimeline.compareBefore)}
              </Typography>
              <Typography variant="body1" fontWeight="medium">
                {beforeScore.timestamp}
              </Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.riskTimeline.compareAfter)}
              </Typography>
              <Typography variant="body1" fontWeight="medium">
                {afterScore.timestamp}
              </Typography>
            </Grid>
          </Grid>
        </Box>

        {/* Dimension Comparisons */}
        <Box>
          {renderComparisonRow(
            t(K.page.riskTimeline.columnOverall),
            beforeScore.overall_score,
            afterScore.overall_score
          )}
          {renderComparisonRow(
            t(K.page.riskTimeline.columnExecution),
            beforeScore.execution_risk,
            afterScore.execution_risk
          )}
          {renderComparisonRow(
            t(K.page.riskTimeline.columnTrust),
            beforeScore.trust_risk,
            afterScore.trust_risk
          )}
          {renderComparisonRow(
            t(K.page.riskTimeline.columnPolicy),
            beforeScore.policy_risk,
            afterScore.policy_risk
          )}
          {renderComparisonRow(
            t(K.page.riskTimeline.columnCapability),
            beforeScore.capability_risk,
            afterScore.capability_risk
          )}
        </Box>
      </Box>
    </DialogForm>
  )
}

// ===================================
// Main Component (P1-23)
// ===================================

export default function RiskTimelinePage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [selectedDimension, setSelectedDimension] = useState<string>('overall')
  const [compareDialogOpen, setCompareDialogOpen] = useState(false)
  const [compareScores, setCompareScores] = useState<{
    before: RiskScore | null
    after: RiskScore | null
  }>({ before: null, after: null })

  // Phase 6: API State Management
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [riskData, setRiskData] = useState<RiskTimelineData | null>(null)

  // ===================================
  // API Data Loading
  // ===================================
  const loadRiskTimeline = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await riskService.getRiskTimeline({
        dimension: selectedDimension,
      })
      setRiskData(response.data)
    } catch (err) {
      console.error('Failed to load risk timeline:', err)
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      toast.error(t(K.page.riskTimeline.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [selectedDimension, t])

  useEffect(() => {
    loadRiskTimeline()
  }, [loadRiskTimeline])

  // ===================================
  // Calculate Summary Stats from API Data
  // ===================================
  const riskScores = riskData?.scores || []
  const currentRisk = riskData?.summary.current_risk || 0
  const avgRisk = riskData?.summary.avg_risk || 0
  const maxRisk = riskData?.summary.max_risk || 0
  const trend = riskData?.summary.trend || 'stable'

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.riskTimeline.title),
    subtitle: t(K.page.riskTimeline.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => {
        loadRiskTimeline()
      },
    },
    {
      key: 'export',
      label: t('common.export'),
      variant: 'contained',
      onClick: () => {
        try {
          // Export risk timeline data as JSON
          const dataStr = JSON.stringify(riskData, null, 2)
          const dataBlob = new Blob([dataStr], { type: 'application/json' })
          const url = URL.createObjectURL(dataBlob)
          const link = document.createElement('a')
          link.href = url
          link.download = `risk-timeline-${new Date().toISOString()}.json`
          link.click()
          URL.revokeObjectURL(url)
        } catch (err) {
          console.error('Failed to export risk timeline:', err)
          toast.error(t(K.page.riskTimeline.exportFailed))
        }
      },
    },
  ])

  // ===================================
  // Helpers
  // ===================================
  const getRiskColor = (value: number): 'error' | 'warning' | 'success' => {
    if (value >= 0.7) return 'error'
    if (value >= 0.4) return 'warning'
    return 'success'
  }

  const getTrendIcon = () => {
    if (trend === 'increasing') return <TrendingUpIcon color="error" />
    if (trend === 'decreasing') return <TrendingDownIcon color="success" />
    return <SwapIcon color="action" />
  }

  // ===================================
  // Handlers
  // ===================================
  const handleCompare = (currentIndex: number) => {
    if (currentIndex < riskScores.length - 1) {
      setCompareScores({
        before: riskScores[currentIndex],
        after: riskScores[currentIndex + 1],
      })
      setCompareDialogOpen(true)
    }
  }

  // ===================================
  // Render - State Handling
  // ===================================
  if (loading) {
    return <LoadingState message={t(K.page.riskTimeline.loadingMessage)} />
  }

  if (error) {
    return <ErrorState error={error} onRetry={loadRiskTimeline} retryText={t('common.retry')} />
  }

  if (!riskData || riskScores.length === 0) {
    return <EmptyState message={t(K.page.riskTimeline.emptyDescription)} />
  }

  // ===================================
  // Render - Main Content
  // ===================================
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Summary Stats */}
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <AppCard>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.riskTimeline.statCurrentRisk)}
              </Typography>
              <Typography variant="h4">
                {(currentRisk * 100).toFixed(1)}%
              </Typography>
              <Chip
                label={t(K.page.riskTimeline[`risk${getRiskColor(currentRisk) === 'success' ? 'Low' : getRiskColor(currentRisk) === 'warning' ? 'Medium' : 'High'}` as keyof typeof K.page.riskTimeline])}
                color={getRiskColor(currentRisk)}
                size="small"
                sx={{ mt: 1 }}
              />
            </CardContent>
          </AppCard>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <AppCard>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.riskTimeline.statAvgRisk)}
              </Typography>
              <Typography variant="h4">
                {(avgRisk * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </AppCard>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <AppCard>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.riskTimeline.statMaxRisk)}
              </Typography>
              <Typography variant="h4">
                {(maxRisk * 100).toFixed(1)}%
              </Typography>
            </CardContent>
          </AppCard>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <AppCard>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.riskTimeline.statTrend)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                {getTrendIcon()}
                <Typography variant="h6">
                  {t(K.page.riskTimeline[`trend${trend.charAt(0).toUpperCase() + trend.slice(1)}` as keyof typeof K.page.riskTimeline])}
                </Typography>
              </Box>
            </CardContent>
          </AppCard>
        </Grid>
      </Grid>

      {/* Dimension Selector */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>{t(K.page.riskTimeline.selectDimension)}</InputLabel>
          <Select
            value={selectedDimension}
            label={t(K.page.riskTimeline.selectDimension)}
            onChange={(e) => setSelectedDimension(e.target.value)}
          >
            <MenuItem value="overall">{t(K.page.riskTimeline.dimensionOverall)}</MenuItem>
            <MenuItem value="execution">{t(K.page.riskTimeline.dimensionExecution)}</MenuItem>
            <MenuItem value="trust">{t(K.page.riskTimeline.dimensionTrust)}</MenuItem>
            <MenuItem value="policy">{t(K.page.riskTimeline.dimensionPolicy)}</MenuItem>
            <MenuItem value="capability">{t(K.page.riskTimeline.dimensionCapability)}</MenuItem>
          </Select>
        </FormControl>
        <Typography variant="body2" color="text.secondary">
          {t(K.page.riskTimeline.chartDescription)}
        </Typography>
      </Box>

      {/* Chart and Dimension Breakdown (P2-9) */}
      <Grid container spacing={2}>
        <Grid item xs={12} lg={8}>
          <RiskTimelineChart data={riskScores} dimension={selectedDimension} />
        </Grid>
        <Grid item xs={12} lg={4}>
          <DimensionBreakdown score={riskScores[riskScores.length - 1]} />
        </Grid>
      </Grid>

      {/* Risk Scores Table with Compare (P2-10) */}
      <AppCard>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t(K.page.riskTimeline.tableTitle)}
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t(K.page.riskTimeline.columnTimestamp)}</TableCell>
                  <TableCell align="right">{t(K.page.riskTimeline.columnOverall)}</TableCell>
                  <TableCell align="right">{t(K.page.riskTimeline.columnExecution)}</TableCell>
                  <TableCell align="right">{t(K.page.riskTimeline.columnTrust)}</TableCell>
                  <TableCell align="right">{t(K.page.riskTimeline.columnPolicy)}</TableCell>
                  <TableCell align="right">{t(K.page.riskTimeline.columnCapability)}</TableCell>
                  <TableCell align="center">{t(K.page.riskTimeline.columnActions)}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {riskScores
                  .slice()
                  .reverse()
                  .map((score, reversedIndex) => {
                    const originalIndex = riskScores.length - 1 - reversedIndex
                    const hasNext = originalIndex < riskScores.length - 1
                    return (
                      <TableRow key={reversedIndex}>
                        <TableCell>{score.timestamp}</TableCell>
                        <TableCell align="right">
                          <Chip
                            label={`${(score.overall_score * 100).toFixed(1)}%`}
                            color={getRiskColor(score.overall_score)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">
                          {(score.execution_risk * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell align="right">{(score.trust_risk * 100).toFixed(1)}%</TableCell>
                        <TableCell align="right">
                          {(score.policy_risk * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell align="right">
                          {(score.capability_risk * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell align="center">
                          {hasNext && (
                            <IconButton
                              size="small"
                              onClick={() => handleCompare(originalIndex)}
                              title={t(K.page.riskTimeline.compareTooltip)}
                            >
                              <CompareIcon fontSize="small" />
                            </IconButton>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </AppCard>

      {/* Time Comparison Dialog (P2-10) */}
      {compareScores.before && compareScores.after && (
        <TimeComparisonDialog
          open={compareDialogOpen}
          onClose={() => setCompareDialogOpen(false)}
          beforeScore={compareScores.before}
          afterScore={compareScores.after}
        />
      )}
    </Box>
  )
}
