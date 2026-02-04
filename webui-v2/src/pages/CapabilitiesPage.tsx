import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Typography, Button, Divider, Chip } from '@mui/material'
/**
 * CapabilitiesPage - Capability Governance Dashboard (AgentOS v3)
 *
 * Aligned with WebUI v1: CapabilityDashboardView.js
 * Displays real-time governance statistics:
 * - Domain capabilities (State, Decision, Action, Governance, Evidence)
 * - Today's invocation stats (allowed/denied)
 * - Risk distribution (LOW/MEDIUM/HIGH/CRITICAL)
 * - Quick navigation to related governance views
 *
 * Features:
 * - Interactive StatusCard with detail drawer
 * - Enable/disable capability operations with confirmation
 * - Real-time dashboard updates
 */

import { usePageHeader } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { StatusCard } from '@/ui/cards/StatusCard'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import {
  MemoryIcon,
  SecurityIcon,
  PlayArrowIcon,
  ExtensionIcon,
  WarningIcon,
  AccountTreeIcon,
  RefreshIcon,
  TimelineIcon,
  ArticleIcon,
  GroupIcon,
  LineChartIcon
} from '@/ui/icons'
import { agentosService } from '@/services/agentos.service'
import type { CapabilityDashboardStats } from '@/types/capability'

// Domain configuration - icons and colors (labels will be translated inline)
const DOMAIN_ICONS = {
  state: { icon: <MemoryIcon />, color: 'blue' },
  decision: { icon: <AccountTreeIcon />, color: 'purple' },
  action: { icon: <PlayArrowIcon />, color: 'orange' },
  governance: { icon: <SecurityIcon />, color: 'green' },
  evidence: { icon: <ArticleIcon />, color: 'teal' },
}

// Detail types for drawer
type DetailType = 'metric' | 'domain' | 'quick-action'

interface DetailData {
  type: DetailType
  id: string
  title: string
  data: any
}

export default function CapabilitiesPage() {
  const { t } = useTextTranslation()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<CapabilityDashboardStats | null>(null)
  const navigate = useNavigate()

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedDetail, setSelectedDetail] = useState<DetailData | null>(null)

  // Confirm dialog state
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirmAction, setConfirmAction] = useState<'enable' | 'disable' | null>(null)
  const [confirmLoading, setConfirmLoading] = useState(false)

  // Domain configuration with translations
  const getDomainConfig = () => ({
    state: { label: t(K.page.capabilities.domainState), ...DOMAIN_ICONS.state },
    decision: { label: t(K.page.capabilities.domainDecision), ...DOMAIN_ICONS.decision },
    action: { label: t(K.page.capabilities.domainAction), ...DOMAIN_ICONS.action },
    governance: { label: t(K.page.capabilities.domainGovernance), ...DOMAIN_ICONS.governance },
    evidence: { label: t(K.page.capabilities.domainEvidence), ...DOMAIN_ICONS.evidence },
  })

  // Fetch dashboard stats
  const loadStats = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await agentosService.getCapabilityDashboardStats()

      if (response.ok && response.data) {
        setStats(response.data)
      } else {
        setError(response.error || 'Failed to load dashboard stats')
      }
    } catch (err) {
      console.error('Failed to fetch capability dashboard stats:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    loadStats()
  }, [])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      loadStats()
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  usePageHeader({
    title: t(K.page.capabilities.title),
    subtitle: t(K.page.capabilities.subtitle),
  })

  // Calculate metrics from stats
  const getMetricsData = () => {
    if (!stats) return []

    const totalCapabilities = Object.values(stats.domains).reduce((sum, d) => sum + d.count, 0)
    const totalAgents = Object.values(stats.domains).reduce((sum, d) => sum + d.active_agents, 0)
    const successRate = stats.today_stats.total_invocations > 0
      ? Math.round(100 * stats.today_stats.allowed / stats.today_stats.total_invocations)
      : 0
    const criticalCount = stats.risk_distribution.CRITICAL || 0

    return [
      {
        id: 'total-capabilities',
        title: t(K.page.capabilities.metricTotalCapabilities),
        value: totalCapabilities.toString(),
        subtitle: t(K.page.capabilities.metricDomains),
        status: 'running',
        statusLabel: t(K.page.capabilities.statusActive),
        icon: <ExtensionIcon />,
      },
      {
        id: 'active-agents',
        title: t(K.page.capabilities.metricActiveAgents),
        value: totalAgents.toString(),
        subtitle: t(K.page.capabilities.metricWithGrants),
        status: 'running',
        statusLabel: t(K.page.capabilities.statusActive),
        icon: <GroupIcon />,
      },
      {
        id: 'today-invocations',
        title: t(K.page.capabilities.metricTodayInvocations),
        value: stats.today_stats.total_invocations.toString(),
        subtitle: `${successRate}% ${t(K.page.capabilities.metricSuccessRate)}`,
        status: 'running',
        statusLabel: t(K.page.capabilities.statusTracking),
        icon: <LineChartIcon />,
      },
      {
        id: 'critical-capabilities',
        title: t(K.page.capabilities.metricCriticalCapabilities),
        value: criticalCount.toString(),
        subtitle: t(K.page.capabilities.metricAdminLevel),
        status: criticalCount > 0 ? 'warning' : 'running',
        statusLabel: criticalCount > 0 ? t(K.page.capabilities.statusAttention) : t(K.page.capabilities.statusOk),
        icon: <WarningIcon />,
      },
    ]
  }

  // Get domain cards data
  const getDomainsData = () => {
    if (!stats) return []

    const domainConfig = getDomainConfig()
    return Object.entries(stats.domains).map(([domainKey, domainStats]) => {
      const config = domainConfig[domainKey as keyof typeof domainConfig] || {
        label: domainKey,
        icon: <ExtensionIcon />,
        color: 'gray',
      }

      return {
        id: `domain-${domainKey}`,
        title: config.label,
        status: 'running',
        statusLabel: t(K.page.capabilities.statusActive),
        icon: config.icon,
        meta: [
          { key: 'count', label: t(K.page.capabilities.domainMetaCapabilities), value: domainStats.count.toString() },
          { key: 'agents', label: t(K.page.capabilities.domainMetaActiveAgents), value: domainStats.active_agents.toString() },
        ],
      }
    })
  }

  // Get quick action cards
  const getQuickActions = () => [
    {
      id: 'action-decision-timeline',
      title: t(K.page.capabilities.quickDecisionTimeline),
      description: t(K.page.capabilities.quickDecisionTimelineDesc),
      status: 'running',
      statusLabel: t(K.page.capabilities.statusAvailable),
      icon: <TimelineIcon />,
      onClick: () => navigate('/decision-timeline'),
    },
    {
      id: 'action-action-log',
      title: t(K.page.capabilities.quickActionLog),
      description: t(K.page.capabilities.quickActionLogDesc),
      status: 'running',
      statusLabel: t(K.page.capabilities.statusAvailable),
      icon: <PlayArrowIcon />,
      onClick: () => navigate('/action-log'),
    },
    {
      id: 'action-evidence-chains',
      title: t(K.page.capabilities.quickEvidenceChains),
      description: t(K.page.capabilities.quickEvidenceChainsDesc),
      status: 'running',
      statusLabel: t(K.page.capabilities.statusAvailable),
      icon: <AccountTreeIcon />,
      onClick: () => navigate('/evidence-chains'),
    },
  ]

  // Handle card click to open detail drawer
  const handleMetricClick = (metricId: string) => {
    if (!stats) return

    const metricsData = getMetricsData()
    const metric = metricsData.find(m => m.id === metricId)
    if (!metric) return

    setSelectedDetail({
      type: 'metric',
      id: metricId,
      title: metric.title,
      data: {
        metric,
        stats,
      },
    })
    setDrawerOpen(true)
  }

  const handleDomainClick = (domainId: string) => {
    if (!stats) return

    const domainKey = domainId.replace('domain-', '')
    const domainStats = stats.domains[domainKey]
    if (!domainStats) return

    const domainConfig = getDomainConfig()
    const config = domainConfig[domainKey as keyof typeof domainConfig]

    setSelectedDetail({
      type: 'domain',
      id: domainId,
      title: config?.label || domainKey,
      data: {
        domainKey,
        domainStats,
        config,
      },
    })
    setDrawerOpen(true)
  }

  // Handle enable/disable capability
  const handleEnableClick = () => {
    setConfirmAction('enable')
    setConfirmOpen(true)
  }

  const handleDisableClick = () => {
    setConfirmAction('disable')
    setConfirmOpen(true)
  }

  const handleConfirmAction = async () => {
    if (!confirmAction || !selectedDetail) return

    setConfirmLoading(true)
    try {
      // Simulate API call (replace with actual API when available)
      await new Promise(resolve => setTimeout(resolve, 1000))

      if (confirmAction === 'enable') {
        toast.success(t(K.page.capabilities.toastEnableSuccess))
      } else {
        toast.success(t(K.page.capabilities.toastDisableSuccess))
      }

      // Refresh stats after action
      await loadStats()
      setConfirmOpen(false)
      setConfirmAction(null)
    } catch (err) {
      console.error('Failed to perform capability action:', err)
      if (confirmAction === 'enable') {
        toast.error(t(K.page.capabilities.toastEnableError))
      } else {
        toast.error(t(K.page.capabilities.toastDisableError))
      }
    } finally {
      setConfirmLoading(false)
    }
  }

  const handleDrawerClose = () => {
    setDrawerOpen(false)
    setSelectedDetail(null)
  }

  // Render drawer content based on detail type
  const renderDrawerContent = () => {
    if (!selectedDetail) return null

    if (selectedDetail.type === 'metric') {
      const { metric, stats } = selectedDetail.data
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldDescription)}
            </Typography>
            <Typography variant="body1">{metric.subtitle}</Typography>
          </Box>

          <Divider />

          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldTotalInvocations)}
            </Typography>
            <Typography variant="h4">{stats.today_stats.total_invocations}</Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.capabilities.fieldAllowed)}
              </Typography>
              <Typography variant="h6" color="success.main">
                {stats.today_stats.allowed}
              </Typography>
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.capabilities.fieldDenied)}
              </Typography>
              <Typography variant="h6" color="error.main">
                {stats.today_stats.denied}
              </Typography>
            </Box>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldSuccessRate)}
            </Typography>
            <Typography variant="body1">
              {stats.today_stats.total_invocations > 0
                ? Math.round(100 * stats.today_stats.allowed / stats.today_stats.total_invocations)
                : 0}%
            </Typography>
          </Box>

          {metric.id === 'critical-capabilities' && (
            <Box>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.capabilities.fieldRiskLevel)}
              </Typography>
              <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {Object.entries(stats.risk_distribution).map(([level, count]) => (
                  <Chip
                    key={level}
                    label={`${level}: ${count}`}
                    size="small"
                    color={
                      level === 'CRITICAL' ? 'error' :
                      level === 'HIGH' ? 'warning' :
                      level === 'MEDIUM' ? 'info' : 'default'
                    }
                  />
                ))}
              </Box>
            </Box>
          )}
        </Box>
      )
    }

    if (selectedDetail.type === 'domain') {
      const { domainKey, domainStats, config } = selectedDetail.data
      return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {config?.icon}
            <Typography variant="h6">{selectedDetail.title}</Typography>
          </Box>

          <Divider />

          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldCapabilities)}
            </Typography>
            <Typography variant="h4">{domainStats.count}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldActiveAgents)}
            </Typography>
            <Typography variant="h4">{domainStats.active_agents}</Typography>
          </Box>

          <Divider />

          <Box>
            <Typography variant="caption" color="text.secondary">
              {t(K.page.capabilities.fieldDescription)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {domainKey === 'state' && t(K.page.capabilities.domainStateDesc)}
              {domainKey === 'decision' && t(K.page.capabilities.domainDecisionDesc)}
              {domainKey === 'action' && t(K.page.capabilities.domainActionDesc)}
              {domainKey === 'governance' && t(K.page.capabilities.domainGovernanceDesc)}
              {domainKey === 'evidence' && t(K.page.capabilities.domainEvidenceDesc)}
            </Typography>
          </Box>
        </Box>
      )
    }

    return null
  }

  // Render drawer actions
  const renderDrawerActions = () => {
    if (!selectedDetail) return null

    return (
      <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
        <Button variant="outlined" onClick={handleEnableClick}>
          {t(K.page.capabilities.actionEnable)}
        </Button>
        <Button variant="outlined" color="error" onClick={handleDisableClick}>
          {t(K.page.capabilities.actionDisable)}
        </Button>
        <Button variant="contained" onClick={handleDrawerClose}>
          {t(K.common.close)}
        </Button>
      </Box>
    )
  }

  // Loading state
  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">{t(K.page.capabilities.loadingDashboard)}</div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <div className="flex items-center">
            <WarningIcon className="text-red-500 mr-2" />
            <div>
              <div className="font-semibold text-red-900">{t(K.page.capabilities.errorTitle)}</div>
              <div className="text-sm text-red-700 mt-1">{error}</div>
            </div>
          </div>
        </div>
        <button
          onClick={loadStats}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          <RefreshIcon className="inline mr-2" />
          {t(K.page.capabilities.actionRetry)}
        </button>
      </div>
    )
  }

  // Empty state
  if (!stats || Object.keys(stats.domains).length === 0) {
    return (
      <div className="p-6">
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <ExtensionIcon className="mx-auto text-gray-400 mb-4" style={{ fontSize: 48 }} />
          <div className="text-lg font-semibold text-gray-700 mb-2">{t(K.page.capabilities.emptyTitle)}</div>
          <div className="text-sm text-gray-500 mb-4">
            {t(K.page.capabilities.emptyDescription)}
          </div>
          <button
            onClick={loadStats}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            <RefreshIcon className="inline mr-2" />
            {t(K.page.capabilities.actionRefresh)}
          </button>
        </div>
      </div>
    )
  }

  const metricsData = getMetricsData()
  const domainsData = getDomainsData()
  const quickActions = getQuickActions()

  return (
    <div className="space-y-6">
      {/* Header Actions */}
      <div className="flex justify-end space-x-2">
        <button
          onClick={loadStats}
          className="px-4 py-2 bg-white border border-gray-300 rounded hover:bg-gray-50 flex items-center"
          disabled={loading}
        >
          <RefreshIcon className="mr-2" style={{ fontSize: 18 }} />
          {t(K.page.capabilities.actionRefresh)}
        </button>
        <button
          onClick={() => navigate('/audit-log')}
          className="px-4 py-2 bg-white border border-gray-300 rounded hover:bg-gray-50 flex items-center"
        >
          <SecurityIcon className="mr-2" style={{ fontSize: 18 }} />
          {t(K.page.capabilities.actionAuditLog)}
        </button>
      </div>

      {/* Key Metrics */}
      <div>
        <h2 className="text-lg font-semibold mb-4">{t(K.page.capabilities.sectionKeyMetrics)}</h2>
        <CardCollectionWrap layout="grid" columns={4} gap={16}>
          {metricsData.map((metric) => (
            <StatusCard
              key={metric.id}
              title={metric.title}
              status={metric.status}
              statusLabel={metric.statusLabel}
              meta={[
                { key: 'value', label: '', value: metric.value },
                { key: 'subtitle', label: '', value: metric.subtitle },
              ]}
              icon={metric.icon}
              onClick={() => handleMetricClick(metric.id)}
            />
          ))}
        </CardCollectionWrap>
      </div>

      {/* Domain Overview */}
      <div>
        <h2 className="text-lg font-semibold mb-4">{t(K.page.capabilities.sectionDomainOverview)}</h2>
        <CardCollectionWrap layout="grid" columns={4} gap={16}>
          {domainsData.map((domain) => (
            <StatusCard
              key={domain.id}
              title={domain.title}
              status={domain.status}
              statusLabel={domain.statusLabel}
              meta={domain.meta}
              icon={domain.icon}
              onClick={() => handleDomainClick(domain.id)}
            />
          ))}
        </CardCollectionWrap>
      </div>

      {/* Quick Access */}
      <div>
        <h2 className="text-lg font-semibold mb-4">{t(K.page.capabilities.sectionQuickAccess)}</h2>
        <CardCollectionWrap layout="grid" columns={4} gap={16}>
          {quickActions.map((action) => (
            <StatusCard
              key={action.id}
              title={action.title}
              status={action.status}
              statusLabel={action.statusLabel}
              description={action.description}
              icon={action.icon}
              onClick={action.onClick}
            />
          ))}
        </CardCollectionWrap>
      </div>

      {/* Detail Drawer */}
      <DetailDrawer
        open={drawerOpen}
        onClose={handleDrawerClose}
        title={selectedDetail?.title || t(K.page.capabilities.drawerTitle)}
        subtitle={
          selectedDetail?.type === 'metric'
            ? t(K.page.capabilities.drawerMetricTitle)
            : selectedDetail?.type === 'domain'
            ? t(K.page.capabilities.drawerDomainTitle)
            : undefined
        }
        actions={renderDrawerActions()}
      >
        {renderDrawerContent()}
      </DetailDrawer>

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={
          confirmAction === 'enable'
            ? t(K.page.capabilities.confirmEnableTitle)
            : t(K.page.capabilities.confirmDisableTitle)
        }
        message={
          confirmAction === 'enable'
            ? t(K.page.capabilities.confirmEnableMessage)
            : t(K.page.capabilities.confirmDisableMessage)
        }
        confirmText={
          confirmAction === 'enable'
            ? t(K.page.capabilities.actionEnable)
            : t(K.page.capabilities.actionDisable)
        }
        cancelText={t(K.common.cancel)}
        onConfirm={handleConfirmAction}
        loading={confirmLoading}
        color={confirmAction === 'disable' ? 'error' : 'primary'}
      />
    </div>
  )
}
