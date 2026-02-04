/**
 * IntentWorkbenchPage - Intent Workbench
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Interactive Workbench: Intent testing, analysis, and debugging tools
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import {
  DashboardGrid,
  StatCard,
  MetricCard,
  LoadingState,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Chip,
  Stack,
  CircularProgress,
  Alert,
  Divider,
  List,
  ListItem,
  ListItemText,
} from '@/ui'
import { DetailDrawer } from '@/ui/interaction'
import {
  ScienceIcon,
  CheckCircleIcon,
  InsightsIcon,
  PlayArrowIcon,
  BugIcon,
  CompareIcon,
} from '@/ui/icons'
import { K, useText } from '@/ui/text'
import { brainosService, type InfoNeedMetric, type Intent } from '@services'

/**
 * IntentWorkbenchPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3列
 * StatCards: 3个
 * MetricCards: 3个
 */
export default function IntentWorkbenchPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useText()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasData, setHasData] = useState(false)
  const [summary, setSummary] = useState<Record<string, unknown>>({})
  const [metricsData, setMetricsData] = useState<InfoNeedMetric[]>([])

  // Workbench State
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [testInput, setTestInput] = useState('')
  const [testLoading, setTestLoading] = useState(false)
  const [testResult, setTestResult] = useState<Intent | null>(null)
  const [testError, setTestError] = useState<string | null>(null)

  // Detail Drawer State
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [selectedMetric, setSelectedMetric] = useState<InfoNeedMetric | null>(null)
  const [intentExplanation, setIntentExplanation] = useState<string | null>(null)

  // Compare Dialog State
  const [compareDialogOpen, setCompareDialogOpen] = useState(false)
  const [compareIntentId, setCompareIntentId] = useState('')
  const [compareLoading, setCompareLoading] = useState(false)
  const [compareResult, setCompareResult] = useState<any>(null)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.intentWorkbench.title),
    subtitle: t(K.page.intentWorkbench.subtitle),
  })

  usePageActions([
    {
      key: 'test-intent',
      label: t(K.page.intentWorkbench.testIntent),
      variant: 'contained',
      onClick: () => setTestDialogOpen(true),
      icon: <PlayArrowIcon />,
    },
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {
        fetchData()
      },
    },
  ])

  // ===================================
  // Data Fetching
  // ===================================
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryResponse, metricsResponse] = await Promise.all([
        brainosService.getInfoNeedMetricsSummary(),
        brainosService.getInfoNeedMetrics(),
      ])

      const summaryData = summaryResponse || {}
      const metricsList = metricsResponse.metrics || []

      setSummary(summaryData)
      setMetricsData(metricsList)
      setHasData(Object.keys(summaryData).length > 0 || metricsList.length > 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setHasData(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const getSummaryNumber = (keys: string[]) => {
    for (const key of keys) {
      const value = summary[key]
      if (typeof value === 'number') return value
      if (typeof value === 'string' && value.trim() !== '') {
        const numeric = Number(value)
        if (!Number.isNaN(numeric)) return numeric
      }
    }
    return null
  }

  const formatPercent = (value: number | null) => {
    if (value === null) return 'N/A'
    if (value <= 1) return `${(value * 100).toFixed(1)}%`
    return `${value.toFixed(1)}%`
  }

  const getCountSince = (msAgo: number) => {
    const cutoff = Date.now() - msAgo
    const count = metricsData.filter((metric) => {
      const ts = Date.parse(metric.timestamp)
      return Number.isFinite(ts) && ts >= cutoff
    }).length
    return metricsData.length > 0 ? String(count) : 'N/A'
  }

  const totalTests = getSummaryNumber(['total_tests', 'total', 'tests_total']) ?? metricsData.length
  const passRate = getSummaryNumber(['pass_rate', 'passRate'])
  const avgConfidence = getSummaryNumber(['avg_confidence', 'avgConfidence'])

  const stats = [
    {
      title: t(K.page.intentWorkbench.statTotalTests),
      value: metricsData.length > 0 ? String(totalTests) : 'N/A',
      icon: <ScienceIcon />,
    },
    {
      title: t(K.page.intentWorkbench.statPassRate),
      value: formatPercent(passRate),
      icon: <CheckCircleIcon />,
    },
    {
      title: t(K.page.intentWorkbench.statAvgConfidence),
      value: avgConfidence === null ? 'N/A' : avgConfidence.toFixed(2),
      icon: <InsightsIcon />,
    },
  ]

  const intentQuery = getSummaryNumber(['intent_query', 'query_intent', 'query'])
  const intentCommand = getSummaryNumber(['intent_command', 'command_intent', 'command'])
  const intentQuestion = getSummaryNumber(['intent_question', 'question_intent', 'question'])

  const accuracy = getSummaryNumber(['accuracy'])
  const precision = getSummaryNumber(['precision'])
  const recall = getSummaryNumber(['recall'])

  const metrics = [
    {
      title: t(K.page.intentWorkbench.metricRecentTests),
      description: t(K.page.intentWorkbench.metricRecentTestsDesc),
      metrics: [
        { key: 'today', label: t(K.page.intentWorkbench.metricTestsToday), value: getCountSince(24 * 60 * 60 * 1000) },
        { key: 'week', label: t(K.page.intentWorkbench.metricTestsWeek), value: getCountSince(7 * 24 * 60 * 60 * 1000) },
        { key: 'month', label: t(K.page.intentWorkbench.metricTestsMonth), value: getCountSince(30 * 24 * 60 * 60 * 1000), valueColor: 'success.main' },
      ],
    },
    {
      title: t(K.page.intentWorkbench.metricIntentDistribution),
      description: t(K.page.intentWorkbench.metricIntentDistributionDesc),
      metrics: [
        { key: 'query', label: t(K.page.intentWorkbench.metricQueryIntent), value: intentQuery === null ? 'N/A' : String(intentQuery), valueColor: 'primary.main' },
        { key: 'command', label: t(K.page.intentWorkbench.metricCommandIntent), value: intentCommand === null ? 'N/A' : String(intentCommand) },
        { key: 'question', label: t(K.page.intentWorkbench.metricQuestionIntent), value: intentQuestion === null ? 'N/A' : String(intentQuestion) },
      ],
    },
    {
      title: t(K.page.intentWorkbench.metricPerformanceMetrics),
      description: t(K.page.intentWorkbench.metricPerformanceMetricsDesc),
      metrics: [
        { key: 'accuracy', label: t(K.page.intentWorkbench.metricAccuracy), value: accuracy === null ? 'N/A' : formatPercent(accuracy), valueColor: 'success.main' },
        { key: 'precision', label: t(K.page.intentWorkbench.metricPrecision), value: precision === null ? 'N/A' : formatPercent(precision) },
        { key: 'recall', label: t(K.page.intentWorkbench.metricRecall), value: recall === null ? 'N/A' : formatPercent(recall), valueColor: 'success.main' },
      ],
    },
  ]

  // ===================================
  // Workbench Interaction Handlers
  // ===================================

  /**
   * Handle StatCard click - Show relevant test history
   */
  const handleStatCardClick = (statType: 'tests' | 'passRate' | 'confidence') => {
    // Filter metrics based on stat type
    let filteredMetrics = metricsData
    if (statType === 'passRate') {
      // Show only passed tests
      filteredMetrics = metricsData.filter((m) => m.value > 0.7)
    } else if (statType === 'confidence') {
      // Show tests sorted by confidence
      filteredMetrics = [...metricsData].sort((a, b) => b.value - a.value)
    }

    if (filteredMetrics.length > 0) {
      setSelectedMetric(filteredMetrics[0])
      setDetailDrawerOpen(true)
    }
  }

  /**
   * Test intent classification with user input
   */
  const handleTestIntent = async () => {
    if (!testInput.trim()) {
      setTestError(t(K.page.intentWorkbench.errorEmptyInput))
      return
    }

    setTestLoading(true)
    setTestError(null)
    setTestResult(null)

    try {
      // Create a mock intent test result (in real scenario, call an intent classification API)
      // For now, simulate the response
      await new Promise((resolve) => setTimeout(resolve, 1000))

      const mockIntent: Intent = {
        id: `intent-${Date.now()}`,
        intent_type: testInput.includes('?') ? 'question' : testInput.startsWith('/') ? 'command' : 'query',
        confidence: Math.random() * 0.3 + 0.7, // Random confidence between 0.7-1.0
        metadata: {
          input_text: testInput,
          tokens: testInput.split(' ').length,
          detected_entities: [],
        },
        created_at: new Date().toISOString(),
      }

      setTestResult(mockIntent)

      // Add to metrics history
      const newMetric: InfoNeedMetric = {
        id: `metric-${Date.now()}`,
        metric_name: 'intent_test',
        value: mockIntent.confidence,
        timestamp: mockIntent.created_at,
      }
      setMetricsData([newMetric, ...metricsData])
    } catch (err) {
      setTestError(err instanceof Error ? err.message : t(K.page.intentWorkbench.errorTestFailed))
    } finally {
      setTestLoading(false)
    }
  }

  /**
   * Explain intent classification result
   */
  const handleExplainIntent = async (intentId: string) => {
    try {
      const response = await brainosService.explainIntent(intentId)
      setIntentExplanation(response.explanation)
    } catch (err) {
      console.error('Failed to explain intent:', err)
      setIntentExplanation(t(K.page.intentWorkbench.errorExplanationFailed))
    }
  }

  /**
   * Compare two intents
   */
  const handleCompareIntents = async () => {
    if (!testResult || !compareIntentId) {
      return
    }

    setCompareLoading(true)
    try {
      const response = await brainosService.compareIntents(testResult.id, compareIntentId)
      setCompareResult(response)
    } catch (err) {
      console.error('Failed to compare intents:', err)
      setCompareResult({ error: t(K.page.intentWorkbench.errorCompareFailed) })
    } finally {
      setCompareLoading(false)
    }
  }

  /**
   * Close test dialog and reset
   */
  const handleCloseTestDialog = () => {
    setTestDialogOpen(false)
    setTestInput('')
    setTestResult(null)
    setTestError(null)
  }

  // ===================================
  // Render: DashboardGrid Pattern
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>
  }

  if (!hasData) {
    return <Alert severity="info">{t(K.component.emptyState.noData)}</Alert>
  }

  return (
    <>
      <DashboardGrid columns={3} gap={16}>
        {/* Row 1: Stat Cards - Interactive */}
        <StatCard
          title={stats[0].title}
          value={stats[0].value}
          icon={stats[0].icon}
          onClick={() => handleStatCardClick('tests')}
        />
        <StatCard
          title={stats[1].title}
          value={stats[1].value}
          icon={stats[1].icon}
          onClick={() => handleStatCardClick('passRate')}
        />
        <StatCard
          title={stats[2].title}
          value={stats[2].value}
          icon={stats[2].icon}
          onClick={() => handleStatCardClick('confidence')}
        />

        {/* Row 2: Metric Cards */}
        {metrics.map((metric, index) => (
          <MetricCard
            key={index}
            title={metric.title}
            description={metric.description}
            metrics={metric.metrics}
          />
        ))}
      </DashboardGrid>

      {/* Test Intent Dialog */}
      <Dialog
        open={testDialogOpen}
        onClose={handleCloseTestDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Stack direction="row" spacing={1} alignItems="center">
            <ScienceIcon />
            <span>{t(K.page.intentWorkbench.testDialogTitle)}</span>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label={t(K.page.intentWorkbench.inputTextLabel)}
              placeholder={t(K.page.intentWorkbench.inputTextPlaceholder)}
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              disabled={testLoading}
              sx={{ mb: 2 }}
            />

            {testError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {testError}
              </Alert>
            )}

            {testLoading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                <CircularProgress />
              </Box>
            )}

            {testResult && (
              <Box sx={{ mt: 2 }}>
                <Divider sx={{ mb: 2 }} />
                <Typography variant="subtitle2" gutterBottom>
                  {t(K.page.intentWorkbench.classificationResult)}
                </Typography>

                <Box sx={{ mb: 2 }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t(K.page.intentWorkbench.intentTypeLabel)}
                    </Typography>
                    <Chip
                      label={testResult.intent_type.toUpperCase()}
                      color={
                        testResult.intent_type === 'query'
                          ? 'primary'
                          : testResult.intent_type === 'command'
                            ? 'secondary'
                            : 'default'
                      }
                      size="small"
                    />
                  </Stack>

                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      {t(K.page.intentWorkbench.confidenceLabel)}
                    </Typography>
                    <Chip
                      label={`${(testResult.confidence * 100).toFixed(1)}%`}
                      color={testResult.confidence > 0.8 ? 'success' : 'warning'}
                      size="small"
                    />
                  </Stack>

                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {t(K.page.intentWorkbench.intentIdLabel)} {testResult.id}
                  </Typography>
                </Box>

                <Stack direction="row" spacing={1}>
                  <Button
                    size="small"
                    startIcon={<BugIcon />}
                    onClick={() => handleExplainIntent(testResult.id)}
                    disabled={!!intentExplanation}
                  >
                    {t(K.page.intentWorkbench.btnExplain)}
                  </Button>
                  <Button
                    size="small"
                    startIcon={<CompareIcon />}
                    onClick={() => setCompareDialogOpen(true)}
                  >
                    {t(K.page.intentWorkbench.btnCompare)}
                  </Button>
                </Stack>

                {intentExplanation && (
                  <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      {t(K.page.intentWorkbench.explanationLabel)}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {intentExplanation}
                    </Typography>
                  </Box>
                )}
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseTestDialog}>{t(K.common.close)}</Button>
          <Button
            variant="contained"
            onClick={handleTestIntent}
            disabled={testLoading || !testInput.trim()}
            startIcon={testLoading ? <CircularProgress size={16} /> : <PlayArrowIcon />}
          >
            {t(K.page.intentWorkbench.btnTest)}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Compare Intents Dialog */}
      <Dialog
        open={compareDialogOpen}
        onClose={() => setCompareDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>{t(K.page.intentWorkbench.compareDialogTitle)}</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <TextField
              fullWidth
              label={t(K.page.intentWorkbench.compareIntentIdLabel)}
              placeholder={t(K.page.intentWorkbench.compareIntentIdPlaceholder)}
              value={compareIntentId}
              onChange={(e) => setCompareIntentId(e.target.value)}
              sx={{ mb: 2 }}
            />

            {compareLoading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                <CircularProgress />
              </Box>
            )}

            {compareResult && (
              <Box sx={{ mt: 2 }}>
                {compareResult.error ? (
                  <Alert severity="error">{compareResult.error}</Alert>
                ) : (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      {t(K.page.intentWorkbench.comparisonResult)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                      {t(K.page.intentWorkbench.similarityScoreLabel)} {((compareResult.similarity_score || 0) * 100).toFixed(1)}%
                    </Typography>
                    {compareResult.differences && compareResult.differences.length > 0 && (
                      <List dense>
                        {compareResult.differences.slice(0, 5).map((diff: any, idx: number) => (
                          <ListItem key={idx}>
                            <ListItemText
                              primary={diff.field || t(K.page.intentWorkbench.differenceFallback)}
                              secondary={diff.description || JSON.stringify(diff)}
                            />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </>
                )}
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCompareDialogOpen(false)}>{t(K.common.close)}</Button>
          <Button
            variant="contained"
            onClick={handleCompareIntents}
            disabled={compareLoading || !compareIntentId.trim()}
          >
            {t(K.page.intentWorkbench.btnCompare)}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Metric Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={() => setDetailDrawerOpen(false)}
        title={t(K.page.intentWorkbench.detailDrawerTitle)}
      >
        {selectedMetric && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t(K.page.intentWorkbench.metricInformation)}
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.intentWorkbench.metricNameLabel)}
              </Typography>
              <Typography variant="body1">{selectedMetric.metric_name}</Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.intentWorkbench.valueLabel)}
              </Typography>
              <Chip
                label={typeof selectedMetric.value === 'number' ? selectedMetric.value.toFixed(3) : selectedMetric.value}
                color={selectedMetric.value > 0.7 ? 'success' : 'warning'}
              />
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.intentWorkbench.timestampLabel)}
              </Typography>
              <Typography variant="body1">
                {new Date(selectedMetric.timestamp).toLocaleString()}
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.intentWorkbench.metricIdLabel)}
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                {selectedMetric.id}
              </Typography>
            </Box>

            <Divider sx={{ my: 2 }} />

            <Typography variant="h6" gutterBottom>
              {t(K.page.intentWorkbench.debugInformation)}
            </Typography>

            <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1, fontFamily: 'monospace', fontSize: '0.75rem' }}>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {JSON.stringify(selectedMetric, null, 2)}
              </pre>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
