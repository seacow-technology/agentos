/**
 * InfoNeedMetricsPage - 信息需求指标分析
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Phase 6: Real API Integration
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, EmptyState, ErrorState, LoadingState } from '@/ui'
import { TrendingUpIcon, CheckCircleIcon, QueryStatsIcon, RefreshIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { brainosService } from '@/services'
import type { GetInfoNeedMetricsResponse } from '@/services/brainos.service'

/**
 * InfoNeedMetricsPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 */
export default function InfoNeedMetricsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<GetInfoNeedMetricsResponse | null>(null)

  // ===================================
  // Data Fetching
  // ===================================
  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await brainosService.getInfoNeedMetrics()
      setData(response)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load info need metrics'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.infoNeedMetrics.title),
    subtitle: t(K.page.infoNeedMetrics.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      icon: <RefreshIcon />,
      onClick: async () => {
        await loadData()
      },
    },
    {
      key: 'export',
      label: t(K.page.infoNeedMetrics.exportReport),
      variant: 'contained',
      onClick: () => {
        // Export functionality will be implemented in future phase
      },
    },
  ])

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState message={t(K.page.infoNeedMetrics.loadingMessage)} />
  }

  // ===================================
  // Error State
  // ===================================
  if (error) {
    return (
      <ErrorState
        error={error}
        onRetry={loadData}
      />
    )
  }

  // ===================================
  // Empty State
  // ===================================
  if (!data || !data.metrics || data.metrics.length === 0) {
    return (
      <EmptyState
        message={t(K.page.infoNeedMetrics.emptyMessage)}
      />
    )
  }

  // ===================================
  // Transform API Data
  // ===================================
  const summary = data.summary as any || {}
  const totalQueries = (summary.total_queries as number) || 0
  const successRate = (summary.success_rate as number) || 0
  const avgResponseTime = (summary.avg_response_time as number) || 0

  const stats = [
    {
      title: t(K.page.infoNeedMetrics.statTotalQueries),
      value: totalQueries.toLocaleString(),
      change: summary.queries_change ? `+${summary.queries_change}` : '+0',
      changeType: 'increase' as const,
      icon: <QueryStatsIcon />,
    },
    {
      title: t(K.page.infoNeedMetrics.statSatisfactionRate),
      value: `${(successRate * 100).toFixed(1)}%`,
      change: summary.rate_change ? `${(summary.rate_change as number) > 0 ? '+' : ''}${((summary.rate_change as number) * 100).toFixed(1)}%` : '+0%',
      changeType: ((summary.rate_change as number) || 0) >= 0 ? 'increase' as const : 'decrease' as const,
      icon: <CheckCircleIcon />,
    },
    {
      title: t(K.page.infoNeedMetrics.statAvgResolutionTime),
      value: `${avgResponseTime.toFixed(1)}s`,
      change: summary.time_change ? `${(summary.time_change as number) > 0 ? '+' : ''}${(summary.time_change as number).toFixed(1)}s` : '0s',
      changeType: ((summary.time_change as number) || 0) <= 0 ? 'increase' as const : 'decrease' as const, // decrease in time is good
      icon: <TrendingUpIcon />,
    },
  ]

  const queryTypes = (summary.query_types || {}) as any
  const qualityMetrics = (summary.quality_metrics || {}) as any
  const sourceCoverage = (summary.source_coverage || {}) as any
  const resolutionPatterns = (summary.resolution_patterns || {}) as any
  const contextUsage = (summary.context_usage || {}) as any

  const metrics = [
    {
      title: t(K.page.infoNeedMetrics.cardQueryClassification),
      description: t(K.page.infoNeedMetrics.cardQueryClassificationDesc),
      metrics: [
        {
          key: 'factual',
          label: t(K.page.infoNeedMetrics.labelFactual),
          value: ((queryTypes.factual as number) || 0).toLocaleString(),
          valueColor: 'primary.main'
        },
        {
          key: 'analytical',
          label: t(K.page.infoNeedMetrics.labelAnalytical),
          value: ((queryTypes.analytical as number) || 0).toLocaleString()
        },
        {
          key: 'exploratory',
          label: t(K.page.infoNeedMetrics.labelExploratory),
          value: ((queryTypes.exploratory as number) || 0).toLocaleString()
        },
      ],
    },
    {
      title: t(K.page.infoNeedMetrics.cardQualityMetrics),
      description: t(K.page.infoNeedMetrics.cardQualityMetricsDesc),
      metrics: [
        {
          key: 'complete',
          label: t(K.page.infoNeedMetrics.labelComplete),
          value: `${(((qualityMetrics.completeness as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'success.main'
        },
        {
          key: 'accurate',
          label: t(K.page.infoNeedMetrics.labelAccurate),
          value: `${(((qualityMetrics.accuracy as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'success.main'
        },
        {
          key: 'relevant',
          label: t(K.page.infoNeedMetrics.labelRelevant),
          value: `${(((qualityMetrics.relevance as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'success.main'
        },
      ],
    },
    {
      title: t(K.page.infoNeedMetrics.cardSourceCoverage),
      description: t(K.page.infoNeedMetrics.cardSourceCoverageDesc),
      metrics: [
        {
          key: 'local',
          label: t(K.page.infoNeedMetrics.labelLocalKnowledge),
          value: ((sourceCoverage.local as number) || 0).toLocaleString()
        },
        {
          key: 'web',
          label: t(K.page.infoNeedMetrics.labelWebSearch),
          value: ((sourceCoverage.web as number) || 0).toLocaleString()
        },
        {
          key: 'external',
          label: t(K.page.infoNeedMetrics.labelExternalAPIs),
          value: ((sourceCoverage.external as number) || 0).toLocaleString()
        },
      ],
    },
    {
      title: t(K.page.infoNeedMetrics.cardResolutionPatterns),
      description: t(K.page.infoNeedMetrics.cardResolutionPatternsDesc),
      metrics: [
        {
          key: 'first',
          label: t(K.page.infoNeedMetrics.labelFirstResponse),
          value: `${(((resolutionPatterns.first_response as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'success.main'
        },
        {
          key: 'followup',
          label: t(K.page.infoNeedMetrics.labelFollowupNeeded),
          value: `${(((resolutionPatterns.followup_needed as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'warning.main'
        },
        {
          key: 'failed',
          label: t(K.page.infoNeedMetrics.labelUnresolved),
          value: `${(((resolutionPatterns.unresolved as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'error.main'
        },
      ],
    },
    {
      title: t(K.page.infoNeedMetrics.cardContextUsage),
      description: t(K.page.infoNeedMetrics.cardContextUsageDesc),
      metrics: [
        {
          key: 'avg',
          label: t(K.page.infoNeedMetrics.labelAvgContextSize),
          value: `${((contextUsage.avg_size as number) || 0).toLocaleString()} tokens`
        },
        {
          key: 'peak',
          label: t(K.page.infoNeedMetrics.labelPeakUsage),
          value: `${((contextUsage.peak_size as number) || 0).toLocaleString()} tokens`
        },
        {
          key: 'efficiency',
          label: t(K.page.infoNeedMetrics.labelEfficiency),
          value: `${(((contextUsage.efficiency as number) || 0) * 100).toFixed(0)}%`,
          valueColor: 'success.main'
        },
      ],
    },
  ]

  // ===================================
  // Render: DashboardGrid Pattern
  // ===================================
  return (
    <DashboardGrid columns={3} gap={16}>
      {/* Row 1: Stat Cards */}
      {stats.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          change={stat.change}
          changeType={stat.changeType}
          icon={stat.icon}
        />
      ))}

      {/* Row 2+: Metric Cards */}
      {metrics.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          description={metric.description}
          metrics={metric.metrics}
          actions={[
            {
              key: 'analyze',
              label: t(K.page.infoNeedMetrics.actionAnalyze),
              onClick: () => {
                // Analyze functionality will be implemented in future phase
              },
            },
          ]}
        />
      ))}
    </DashboardGrid>
  )
}
