/**
 * KnowledgeHealthPage - 知识库健康度监控
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Real API: brainosService.getKnowledgeHealth()（Phase 6）
 * - ✅ State Handling: Loading/Success/Error/Empty states
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions, EmptyState } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, CircularProgress } from '@/ui'
import { Box, Typography } from '@mui/material'
import {
  StorageIcon,
  CheckCircleIcon,
  ErrorIcon,
  WarningIcon,
  RefreshIcon,
  DownloadIcon,
  BuildIcon,
  InboxIcon
} from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { brainosService, type KnowledgeHealth } from '@/services/brainos.service'

/**
 * KnowledgeHealthPage 组件
 *
 * 📊 Pattern: DashboardPage with Real API Integration
 */
export default function KnowledgeHealthPage() {
  // ===================================
  // State Management
  // ===================================
  const [health, setHealth] = useState<KnowledgeHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // Data Fetching
  // ===================================
  const fetchKnowledgeHealth = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await brainosService.getKnowledgeHealth()
      setHealth(response.health)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      toast.error(t(K.page.knowledgeHealth.loadFailed))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchKnowledgeHealth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Actions
  // ===================================
  const handleRefresh = () => {
    fetchKnowledgeHealth()
  }

  const handleRepair = async () => {
    try {
      // TODO: Implement repair API when available
      // await brainosService.repairKnowledgeHealth()
      // await fetchKnowledgeHealth()
      toast.info(t(K.page.knowledgeHealth.repair))
    } catch (err) {
      toast.error(t(K.page.knowledgeHealth.repairFailed))
    }
  }

  const handleExport = () => {
    if (!health) return
    const data = JSON.stringify(health, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `knowledge-health-${new Date().toISOString()}.json`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(t(K.page.knowledgeHealth.exportSuccess))
  }

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.knowledgeHealth.title),
    subtitle: t(K.page.knowledgeHealth.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.page.knowledgeHealth.refresh),
      variant: 'outlined',
      icon: <RefreshIcon />,
      onClick: handleRefresh,
    },
    {
      key: 'repair',
      label: t(K.page.knowledgeHealth.repair),
      variant: 'outlined',
      icon: <BuildIcon />,
      onClick: handleRepair,
    },
    {
      key: 'export',
      label: t(K.page.knowledgeHealth.export),
      variant: 'contained',
      icon: <DownloadIcon />,
      onClick: handleExport,
    },
  ])

  // ===================================
  // Render States
  // ===================================
  if (loading && !health) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress />
          <Typography sx={{ mt: 2 }} color="text.secondary">
            {t('common.loading')}
          </Typography>
        </Box>
      </Box>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={<ErrorIcon sx={{ fontSize: 64 }} />}
        title={t('common.error')}
        description={error}
        actions={[
          {
            label: t('common.retry'),
            onClick: handleRefresh,
            variant: 'contained',
          },
        ]}
      />
    )
  }

  if (!health) {
    return (
      <EmptyState
        icon={<InboxIcon sx={{ fontSize: 64 }} />}
        title={t(K.page.knowledgeHealth.emptyTitle)}
        description={t(K.page.knowledgeHealth.emptyDescription)}
      />
    )
  }

  // ===================================
  // Calculate Overall Health Status
  // ===================================
  const getHealthStatus = (): 'success' | 'warning' | 'error' => {
    if (health.index_health_score >= 80) return 'success'
    if (health.index_health_score >= 60) return 'warning'
    return 'error'
  }

  const getHealthLabel = (): string => {
    const status = getHealthStatus()
    if (status === 'success') return 'Healthy'
    if (status === 'warning') return 'Warning'
    return 'Critical'
  }

  // ===================================
  // Prepare Data
  // ===================================
  const stats = [
    {
      title: t(K.page.knowledgeHealth.indexHealthScore),
      value: `${health.index_health_score.toFixed(1)}%`,
      change: undefined,
      changeType: undefined as any,
      icon: getHealthStatus() === 'success' ? <CheckCircleIcon /> :
            getHealthStatus() === 'warning' ? <WarningIcon /> : <ErrorIcon />,
    },
    {
      title: t(K.page.knowledgeHealth.orphanedNodes),
      value: health.orphaned_nodes.toString(),
      change: undefined,
      changeType: undefined as any,
      icon: <StorageIcon />,
    },
    {
      title: t(K.page.knowledgeHealth.brokenLinks),
      value: health.broken_links.toString(),
      change: undefined,
      changeType: undefined as any,
      icon: <ErrorIcon />,
    },
  ]

  const metrics = [
    {
      title: t(K.page.knowledgeHealth.overallHealth),
      description: 'General health indicators',
      metrics: [
        {
          key: 'status',
          label: 'Status',
          value: getHealthLabel(),
          valueColor: getHealthStatus() === 'success' ? 'success.main' :
                     getHealthStatus() === 'warning' ? 'warning.main' : 'error.main'
        },
        {
          key: 'score',
          label: 'Health Score',
          value: `${health.index_health_score.toFixed(1)}%`,
          valueColor: getHealthStatus() === 'success' ? 'success.main' :
                     getHealthStatus() === 'warning' ? 'warning.main' : 'error.main'
        },
      ],
    },
    {
      title: 'Data Quality Issues',
      description: 'Issues requiring attention',
      metrics: [
        {
          key: 'stale',
          label: t(K.page.knowledgeHealth.staleKnowledge),
          value: health.stale_knowledge.toString(),
          valueColor: health.stale_knowledge > 0 ? 'warning.main' : 'success.main'
        },
        {
          key: 'duplicate',
          label: t(K.page.knowledgeHealth.duplicateEntries),
          value: health.duplicate_entries.toString(),
          valueColor: health.duplicate_entries > 0 ? 'warning.main' : 'success.main'
        },
      ],
    },
    {
      title: 'Vector Quality',
      description: 'Embedding and vector metrics',
      metrics: [
        {
          key: 'quality',
          label: t(K.page.knowledgeHealth.embeddingQuality),
          value: `${health.embedding_quality.toFixed(1)}%`,
          valueColor: health.embedding_quality >= 80 ? 'success.main' : 'warning.main'
        },
        {
          key: 'coverage',
          label: t(K.page.knowledgeHealth.vectorCoverage),
          value: `${health.vector_coverage.toFixed(1)}%`,
          valueColor: health.vector_coverage >= 80 ? 'success.main' : 'warning.main'
        },
        {
          key: 'accuracy',
          label: t(K.page.knowledgeHealth.retrievalAccuracy),
          value: `${health.retrieval_accuracy.toFixed(1)}%`,
          valueColor: health.retrieval_accuracy >= 80 ? 'success.main' : 'warning.main'
        },
      ],
    },
  ]

  // ===================================
  // Issues List
  // ===================================
  const hasIssues = health.issues && health.issues.length > 0

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
          actions={[]}
        />
      ))}

      {/* Row 3: Issues List (Full Width) */}
      {hasIssues && (
        <Box
          sx={{
            gridColumn: '1 / -1',
            p: 3,
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            bgcolor: 'background.paper',
          }}
        >
          <Typography variant="h6" sx={{ mb: 2 }}>
            {t(K.page.knowledgeHealth.issuesList)}
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {health.issues!.map((issue) => (
              <Box
                key={issue.id}
                sx={{
                  p: 2,
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="subtitle2">
                    {issue.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      px: 1,
                      py: 0.5,
                      borderRadius: 1,
                      bgcolor: issue.severity === 'high' ? 'error.light' :
                              issue.severity === 'medium' ? 'warning.light' : 'info.light',
                      color: 'white',
                    }}
                  >
                    {issue.severity.toUpperCase()}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {issue.description}
                </Typography>
                <Typography variant="caption" color="text.disabled" sx={{ mt: 1, display: 'block' }}>
                  Detected: {new Date(issue.created_at).toLocaleString()}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </DashboardGrid>
  )
}
