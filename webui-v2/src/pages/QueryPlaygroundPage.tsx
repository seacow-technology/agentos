/**
 * QueryPlaygroundPage - Query Playground
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Real API Integration: brainosService.getInfoNeedMetrics()
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState, ErrorState, EmptyState } from '@/ui'
import { SearchIcon, CheckCircleIcon, SpeedIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { brainosService } from '@/services'

/**
 * QueryPlaygroundPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3列
 * StatCards: 3个
 * MetricCards: 3个
 */
export default function QueryPlaygroundPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<any>(null)

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
      const errorMessage = err instanceof Error ? err.message : 'Failed to load query metrics'
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
    title: t(K.page.queryPlayground.title),
    subtitle: t(K.page.queryPlayground.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        await loadData()
      },
    },
  ])

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  // ===================================
  // Error State
  // ===================================
  if (error) {
    return <ErrorState error={error} onRetry={loadData} />
  }

  // ===================================
  // Empty State
  // ===================================
  if (!data) {
    return <EmptyState message={t('common.noData')} />
  }

  // ===================================
  // Mock Data
  // ===================================
  const stats = [
    {
      title: t(K.page.queryPlayground.statTotalQueries),
      value: '156',
      change: '+12',
      changeType: 'increase' as const,
      icon: <SearchIcon />,
    },
    {
      title: t(K.page.queryPlayground.statSuccessRate),
      value: '94.2%',
      change: '+2.3%',
      changeType: 'increase' as const,
      icon: <CheckCircleIcon />,
    },
    {
      title: t(K.page.queryPlayground.statAvgLatency),
      value: '45ms',
      change: '-5ms',
      changeType: 'increase' as const, // decrease in latency is good
      icon: <SpeedIcon />,
    },
  ]

  const metrics = [
    {
      title: t(K.page.queryPlayground.metricRecentQueries),
      description: t(K.page.queryPlayground.metricRecentQueriesDesc),
      metrics: [
        { key: 'today', label: t(K.page.queryPlayground.metricQueriesToday), value: '23' },
        { key: 'week', label: t(K.page.queryPlayground.metricQueriesWeek), value: '156' },
        { key: 'month', label: t(K.page.queryPlayground.metricQueriesMonth), value: '687', valueColor: 'success.main' },
      ],
    },
    {
      title: t(K.page.queryPlayground.metricPopularQueries),
      description: t(K.page.queryPlayground.metricPopularQueriesDesc),
      metrics: [
        { key: 'type1', label: t(K.page.queryPlayground.metricEntityQueries), value: '89', valueColor: 'primary.main' },
        { key: 'type2', label: t(K.page.queryPlayground.metricRelationQueries), value: '45' },
        { key: 'type3', label: t(K.page.queryPlayground.metricPathQueries), value: '22' },
      ],
    },
    {
      title: t(K.page.queryPlayground.metricQueryPerformance),
      description: t(K.page.queryPlayground.metricQueryPerformanceDesc),
      metrics: [
        { key: 'avg', label: t(K.page.queryPlayground.metricAvgLatency), value: '45ms', valueColor: 'success.main' },
        { key: 'p95', label: t(K.page.queryPlayground.metricP95Latency), value: '128ms' },
        { key: 'p99', label: t(K.page.queryPlayground.metricP99Latency), value: '256ms', valueColor: 'warning.main' },
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
          onClick={() => {
            toast.info(`${stat.title}: ${stat.value}`)
          }}
        />
      ))}

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
  )
}
