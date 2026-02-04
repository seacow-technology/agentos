/**
 * OverviewPage - 系统概览页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Real API Integration: systemService.healthCheck()
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState, ErrorState, EmptyState } from '@/ui'
import { DashboardIcon, GroupIcon, CheckCircleIcon } from '@/ui/icons'
import { useTextTranslation } from '@/ui/text'
import { systemService } from '@/services'

/**
 * OverviewPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3 columns, 3 StatCard + 3 MetricCard
 */
export default function OverviewPage() {
  // ===================================
  // Hooks
  // ===================================
  const navigate = useNavigate()
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
      const response = await systemService.getOverview()
      setData(response)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load overview data'
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
    title: t('page.overview.title'),
    subtitle: t('page.overview.subtitle'),
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
    {
      key: 'settings',
      label: t('page.overview.settings'),
      variant: 'contained',
      onClick: () => {
        // Settings functionality will be implemented in future phase
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

  const formatUptime = (seconds?: number) => {
    if (!seconds && seconds !== 0) return 'N/A'
    if (seconds < 60) return `${seconds}s`
    const mins = Math.floor(seconds / 60)
    if (mins < 60) return `${mins}m`
    const hours = Math.floor(mins / 60)
    const remMins = mins % 60
    return `${hours}h ${remMins}m`
  }

  const metricsData = data?.metrics ?? {}

  // ===================================
  // StatCards with Navigation
  // ===================================
  const stats = [
    {
      title: t('page.overview.statTotalTasks'),
      value: metricsData.total_tasks ?? 'N/A',
      icon: <DashboardIcon />,
      path: '/tasks',
    },
    {
      title: t('page.overview.statActiveAgents'),
      value: metricsData.active_agents ?? 'N/A',
      icon: <GroupIcon />,
      path: '/sessions',
    },
    {
      title: t('page.overview.statSuccessRate'),
      value: metricsData.success_rate ?? (data?.status ? data.status.toUpperCase() : 'N/A'),
      icon: <CheckCircleIcon />,
      path: '/health',
    },
  ]

  // ===================================
  // MetricCards with Navigation
  // ===================================
  const metrics = [
    {
      title: t('page.overview.metricSystemStatus'),
      description: t('page.overview.metricSystemStatusDesc'),
      metrics: [
        { key: 'uptime', label: t('page.overview.metricUptime'), value: formatUptime(data?.uptime_seconds) },
        { key: 'cpu', label: t('page.overview.metricCpu'), value: metricsData.cpu_usage ?? metricsData.cpu ?? 'N/A' },
        { key: 'memory', label: t('page.overview.metricMemory'), value: metricsData.memory_usage ?? metricsData.memory ?? 'N/A' },
      ],
      path: '/runtime',
    },
    {
      title: t('page.overview.metricRecentActivity'),
      description: t('page.overview.metricRecentActivityDesc'),
      metrics: [
        { key: 'tasks', label: t('page.overview.metricTasks'), value: metricsData.recent_tasks ?? metricsData.tasks ?? 'N/A' },
        { key: 'agents', label: t('page.overview.metricAgents'), value: metricsData.recent_agents ?? metricsData.agents ?? 'N/A' },
        { key: 'skills', label: t('page.overview.metricSkills'), value: metricsData.skills ?? 'N/A' },
      ],
      path: '/history',
    },
    {
      title: t('page.overview.metricResourceUsage'),
      description: t('page.overview.metricResourceUsageDesc'),
      metrics: [
        { key: 'metric1', label: t('page.overview.metricDisk'), value: metricsData.disk_usage ?? 'N/A' },
        { key: 'metric2', label: t('page.overview.metricNetwork'), value: metricsData.network_usage ?? 'N/A' },
        { key: 'metric3', label: t('page.overview.metricDatabase'), value: metricsData.database_size ?? 'N/A' },
      ],
      path: '/runtime',
    },
  ]

  // ===================================
  // Render: DashboardGrid Pattern with Interactive Cards
  // ===================================
  return (
    <DashboardGrid columns={3} gap={16}>
      {/* Row 1: Stat Cards with Click Navigation */}
      {stats.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          icon={stat.icon}
          onClick={() => {
            // Navigate to the detail page
            navigate(stat.path)
          }}
        />
      ))}

      {/* Row 2: Metric Cards with View All Action */}
      {metrics.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          description={metric.description}
          metrics={metric.metrics}
          actions={[
            {
              key: 'view',
              label: t('common.viewAll'),
              onClick: () => {
                // Navigate to the detail page
                navigate(metric.path)
              },
            },
          ]}
          onClick={() => {
            // Also allow clicking the card itself
            navigate(metric.path)
          }}
        />
      ))}
    </DashboardGrid>
  )
}
