/**
 * HealthPage - 系统健康度页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard } from '@/ui'
import { HealthIcon, SpeedIcon, ErrorIcon, CheckCircleIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'

/**
 * HealthPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 4 columns, 4 StatCard + 4 MetricCard
 */
export default function HealthPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // ===================================
  // Data Fetching - Real API
  // ===================================
  useEffect(() => {
    const fetchHealth = async () => {
      setLoading(true)
      setError(null)
      try {
        // Ready for real API integration
      } catch (err) {
        console.error('Failed to fetch health metrics:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.health.title),
    subtitle: t(K.page.health.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'contained',
      onClick: async () => {
        setLoading(true)
        setError(null)
        try {
          // API refresh
        } catch (err) {
          setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
          setLoading(false)
        }
      },
    },
  ])

  // ===================================
  // Mock Data - StatCards
  // ===================================
  const stats = [
    {
      title: t('page.health.statSystemHealth'),
      value: '98%',
      change: '+2%',
      changeType: 'increase' as const,
      icon: <HealthIcon />,
    },
    {
      title: t('page.health.statApiLatency'),
      value: '45ms',
      change: '-5ms',
      changeType: 'increase' as const, // decrease is good
      icon: <SpeedIcon />,
    },
    {
      title: t('page.health.statErrorRate'),
      value: '0.2%',
      change: '-0.1%',
      changeType: 'increase' as const, // decrease is good
      icon: <ErrorIcon />,
    },
    {
      title: t('page.health.statUptime'),
      value: '99.9%',
      change: '+0.1%',
      changeType: 'increase' as const,
      icon: <CheckCircleIcon />,
    },
  ]

  // ===================================
  // Mock Data - MetricCards
  // ===================================
  const metrics = [
    {
      title: t('page.health.metricServiceStatus'),
      description: t('page.health.metricServiceStatusDesc'),
      metrics: [
        { key: 'api', label: t('page.health.metricApiStatus'), value: 'Healthy', valueColor: 'success.main' },
        { key: 'database', label: t('page.health.metricDatabaseStatus'), value: 'Healthy', valueColor: 'success.main' },
        { key: 'cache', label: t('page.health.metricCacheStatus'), value: 'Degraded', valueColor: 'warning.main' },
      ],
    },
    {
      title: t('page.health.metricPerformanceMetrics'),
      description: t('page.health.metricPerformanceMetricsDesc'),
      metrics: [
        { key: 'throughput', label: t('page.health.metricThroughput'), value: '1,247 req/s' },
        { key: 'latency', label: t('page.health.metricLatency'), value: '45ms', valueColor: 'success.main' },
        { key: 'errors', label: t('page.health.metricErrors'), value: '0.2%', valueColor: 'success.main' },
      ],
    },
    {
      title: t('page.health.metricResourceUtilization'),
      description: t('page.health.metricResourceUtilizationDesc'),
      metrics: [
        { key: 'cpu', label: t('page.health.metricCpu'), value: '42%', valueColor: 'success.main' },
        { key: 'memory', label: t('page.health.metricMemory'), value: '68%', valueColor: 'warning.main' },
        { key: 'disk', label: t('page.health.metricDisk'), value: '54%', valueColor: 'success.main' },
      ],
    },
    {
      title: t('page.health.metricRecentIssues'),
      description: t('page.health.metricRecentIssuesDesc'),
      metrics: [
        { key: 'critical', label: t('page.health.metricCriticalIssues'), value: '0', valueColor: 'success.main' },
        { key: 'warnings', label: t('page.health.metricWarnings'), value: '3', valueColor: 'warning.main' },
        { key: 'resolved', label: t('page.health.metricResolvedIssues'), value: '12', valueColor: 'success.main' },
      ],
    },
  ]

  // ===================================
  // Render: DashboardGrid Pattern with Four States
  // ===================================
  if (loading) {
    return <DashboardGrid columns={4} gap={16}>
      <StatCard title={t(K.common.loading)} value="..." />
    </DashboardGrid>
  }

  if (error) {
    return <DashboardGrid columns={4} gap={16}>
      <StatCard title={t(K.common.error)} value={error} />
    </DashboardGrid>
  }

  return (
    <DashboardGrid columns={4} gap={16}>
      {/* Row 1: Stat Cards */}
      {stats.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          change={stat.change}
          changeType={stat.changeType}
          icon={stat.icon}
          onClick={() => console.log('Stat clicked:', stat.title)}
        />
      ))}

      {/* Row 2: Metric Cards */}
      {metrics.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          description={metric.description}
          metrics={metric.metrics}
          actions={[
            {
              key: 'view',
              label: t('common.view'),
              onClick: () => {}, // 🔒 No-Interaction: 空函数
            },
          ]}
        />
      ))}
    </DashboardGrid>
  )
}
