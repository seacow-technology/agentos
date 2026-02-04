/**
 * BrainDashboardPage - Brain 控制面板
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard/StatusCard
 * - ✅ Phase 6: 真实API集成（getBrainDashboard）
 * - ✅ State Handling: Loading/Success/Error states
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, StatusCard, ErrorState } from '@/ui'
import { StorageIcon, MemoryIcon, SpeedIcon } from '@/ui/icons'
import { useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { brainosService, type BrainDashboardData } from '@/services/brainos.service'

/**
 * BrainDashboardPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard/StatusCard）
 * 🔌 API: GET /api/brain/dashboard → brainosService.getBrainDashboard()
 */
export default function BrainDashboardPage() {
  const navigate = useNavigate()
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dashboard, setDashboard] = useState<BrainDashboardData | null>(null)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.brainDashboard.title'),
    subtitle: t('page.brainDashboard.subtitle'),
  })

  // ===================================
  // Data Fetching
  // ===================================
  const fetchDashboard = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await brainosService.getBrainDashboard()
      setDashboard(response.dashboard)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('page.brainDashboard.loadFailed')
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboard()
  }, [])

  // ===================================
  // Auto-refresh (30 seconds)
  // ===================================
  useEffect(() => {
    const interval = setInterval(() => {
      fetchDashboard()
    }, 30000) // 30 seconds
    return () => clearInterval(interval)
  }, [])

  // ===================================
  // Page Actions
  // ===================================
  usePageActions([
    {
      key: 'refresh',
      label: t('page.brainDashboard.refresh'),
      variant: 'outlined',
      onClick: fetchDashboard,
    },
    {
      key: 'query-console',
      label: t('page.brainDashboard.queryConsole'),
      variant: 'contained',
      onClick: () => navigate('/query-playground'),
    },
  ])

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading) {
    return <DashboardGrid loading columns={3} gap={16}>{null}</DashboardGrid>
  }

  // ===================================
  // Render: Error State
  // ===================================
  if (error || !dashboard) {
    return (
      <ErrorState
        error={error || t('page.brainDashboard.loadFailed')}
        onRetry={fetchDashboard}
        retryText={t('common.retry')}
      />
    )
  }

  // ===================================
  // Helper Functions
  // ===================================
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
  }

  const formatNumber = (num: number): string => {
    return new Intl.NumberFormat('en-US').format(num)
  }

  const getStatusLabel = (status: string): string => {
    const statusMap: Record<string, string> = {
      healthy: t('page.brainDashboard.statusHealthy'),
      degraded: t('page.brainDashboard.statusDegraded'),
      offline: t('page.brainDashboard.statusOffline'),
    }
    return statusMap[status] || status
  }

  // ===================================
  // Render: Success State
  // ===================================
  const stats = [
    {
      title: t('page.brainDashboard.knowledgeSources'),
      value: formatNumber(dashboard.knowledge_sources_count),
      icon: <StorageIcon />,
      onClick: () => navigate('/sources'),
    },
    {
      title: t('page.brainDashboard.memoryEntries'),
      value: formatNumber(dashboard.memory_entries_count),
      icon: <MemoryIcon />,
      onClick: () => navigate('/memory-proposals'),
    },
    {
      title: t('page.brainDashboard.avgQueryTime'),
      value: `${dashboard.avg_query_time}ms`,
      icon: <SpeedIcon />,
      onClick: () => navigate('/knowledge-health'),
    },
  ]

  const metrics = [
    {
      title: t('page.brainDashboard.ragSuccessRate'),
      description: 'RAG query success rate and performance metrics',
      metrics: [
        {
          key: 'success_rate',
          label: t('page.brainDashboard.ragSuccessRate'),
          value: `${dashboard.rag_success_rate.toFixed(1)}%`,
          valueColor: dashboard.rag_success_rate >= 90 ? 'success.main' : dashboard.rag_success_rate >= 70 ? 'warning.main' : 'error.main'
        },
        {
          key: 'embedding_calls',
          label: t('page.brainDashboard.embeddingCalls'),
          value: formatNumber(dashboard.embedding_calls_count)
        },
      ],
    },
    {
      title: t('page.brainDashboard.indexCoverage'),
      description: 'Vector index coverage and size metrics',
      metrics: [
        {
          key: 'coverage',
          label: t('page.brainDashboard.indexCoverage'),
          value: `${dashboard.index_coverage.toFixed(1)}%`,
          valueColor: dashboard.index_coverage >= 90 ? 'success.main' : dashboard.index_coverage >= 70 ? 'warning.main' : 'error.main'
        },
        {
          key: 'size',
          label: t('page.brainDashboard.vectorIndexSize'),
          value: formatBytes(dashboard.vector_index_size)
        },
      ],
    },
  ]

  const services = [
    {
      title: t('page.brainDashboard.indexServiceStatus'),
      status: dashboard.index_service_status,
      statusLabel: getStatusLabel(dashboard.index_service_status),
      description: 'Vector index management and search service',
      onClick: () => navigate('/knowledge-health'),
    },
    {
      title: t('page.brainDashboard.embeddingServiceStatus'),
      status: dashboard.embedding_service_status,
      statusLabel: getStatusLabel(dashboard.embedding_service_status),
      description: 'Text embedding generation service',
      onClick: () => navigate('/knowledge-health'),
    },
    {
      title: t('page.brainDashboard.retrievalServiceStatus'),
      status: dashboard.retrieval_service_status,
      statusLabel: getStatusLabel(dashboard.retrieval_service_status),
      description: 'Knowledge retrieval and RAG service',
      onClick: () => navigate('/knowledge-health'),
    },
  ]

  return (
    <DashboardGrid columns={3} gap={16}>
      {/* Row 1: Stat Cards */}
      {stats.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          icon={stat.icon}
          onClick={stat.onClick}
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

      {/* Row 3: Status Cards */}
      {services.map((service, index) => (
        <StatusCard
          key={index}
          title={service.title}
          status={service.status}
          statusLabel={service.statusLabel}
          description={service.description}
          onClick={service.onClick}
        />
      ))}
    </DashboardGrid>
  )
}
