/**
 * HomePage - System Overview Dashboard
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.home.xxx)
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Pattern Components: DashboardGrid + StatCard + StatusCard + MetricCard
 * - ✅ Real API Integration: systemService + riskService
 *
 * 📊 设计参考: WebUI v1 Overview 页面
 * - 双列网格布局展示系统状态
 * - 5 个核心卡片：System Status, Resource Usage, Components, System Info, Governance
 * - 快速操作按钮：Refresh
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, StatusCard, MetricCard, AppCard, AppCardHeader, AppCardBody, Chip, LoadingState } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
// eslint-disable-next-line no-restricted-imports -- G3 Exception: useTheme and alpha are MUI utilities (not components) needed for theme token access
import { Box, Typography, useTheme, alpha } from '@mui/material'
import { RefreshIcon, CheckCircleIcon, WarningIcon, ErrorIcon } from '@/ui/icons'
import { systemService } from '@/services/system.service'
import { riskService } from '@/services/risk.service'
import { useSnackbar } from 'notistack'

// Typography variants and colors to avoid string literals
const BODY2_VARIANT = 'body2' as const
const TEXT_SECONDARY = 'text.secondary' as const
const COLOR_PRIMARY = 'primary' as const
const SIZE_SMALL = 'small' as const
const TEXT_ALIGN_CENTER = 'center' as const
const LOADING_ELLIPSIS = '...'

export default function HomePage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()
  const theme = useTheme()
  const navigate = useNavigate()
  const { enqueueSnackbar } = useSnackbar()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [runtimeInfo, setRuntimeInfo] = useState<{
    version: string
    uptime: number
    environment: string
    features: string[]
    pid: number
  } | null>(null)
  const [metrics, setMetrics] = useState<{
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    network_rx: number
    network_tx: number
  } | null>(null)
  const [healthCheck, setHealthCheck] = useState<{
    status: 'ok' | 'degraded' | 'error' | 'warn'
    components: Record<string, { status: string; message?: string }>
    timestamp: string
    uptime_seconds?: number
    metrics?: Record<string, any>
  } | null>(null)
  const [riskStatus, setRiskStatus] = useState<{
    overall_risk: number
    execution_risk: number
    trust_risk: number
    policy_risk: number
    capability_risk: number
  } | null>(null)

  // ===================================
  // Theme Tokens with Fallback
  // ===================================
  const agentosRaw: {
    bg?: Record<string, string>
    border?: Record<string, string>
    shape?: { radius: { sm: number; md: number; lg: number } }
  } | null = (theme as { agentos?: Record<string, unknown> }).agentos ?? (theme.palette as { agentos?: Record<string, unknown> }).agentos ?? null

  const bg = agentosRaw?.bg ?? {
    canvas: theme.palette.background.default,
    surface: alpha(theme.palette.background.default, 0.9),
    paper: theme.palette.background.paper,
    section: alpha(theme.palette.background.paper, 0.55),
    elevated: alpha(theme.palette.background.paper, 0.8),
  }

  const border = agentosRaw?.border ?? {
    subtle: theme.palette.mode === 'light' ? 'rgba(0,0,0,0.08)' : 'rgba(255,255,255,0.06)',
    strong: theme.palette.mode === 'light' ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.10)',
  }

  const shape = agentosRaw?.shape ?? {
    radius: { sm: 10, md: 14, lg: 18 },
  }

  const agentos = {
    bg,
    border,
    shape,
    ...agentosRaw,
  }

  // ===================================
  // Data Fetching
  // ===================================
  const fetchData = async () => {
    try {
      setLoading(true)

      // Real API calls: await systemService.getRuntimeInfo(), await systemService.getMetricsJson(),
      // await systemService.healthCheck(), await riskService.getCurrentRiskStatus()
      const [runtimeRes, metricsRes, healthRes, riskRes] = await Promise.all([
        systemService.getRuntimeInfo().catch(err => ({ error: err })),
        systemService.getMetricsJson().catch(err => ({ error: err })),
        systemService.healthCheck().catch(err => ({ error: err })),
        riskService.getCurrentRiskStatus().catch(err => ({ error: err })),
      ])

      // Handle runtime info
      if (runtimeRes && typeof runtimeRes === 'object' && !('error' in runtimeRes)) {
        setRuntimeInfo(runtimeRes)
      } else {
        console.error('Failed to fetch runtime info:', runtimeRes)
      }

      // Handle metrics
      if (metricsRes && typeof metricsRes === 'object' && !('error' in metricsRes)) {
        // getMetricsJson() returns { timestamp, metrics: {...} }
        // Extract the nested metrics object
        const metricsData = metricsRes.metrics || metricsRes
        setMetrics(metricsData as typeof metrics)
      } else {
        console.error('Failed to fetch metrics:', metricsRes)
      }

      // Handle health check
      if (healthRes && typeof healthRes === 'object' && !('error' in healthRes)) {
        setHealthCheck(healthRes)
      } else {
        console.error('Failed to fetch health check:', healthRes)
      }

      // Handle risk status
      if (riskRes && typeof riskRes === 'object' && !('error' in riskRes)) {
        setRiskStatus(riskRes)
      } else {
        console.error('Failed to fetch risk status:', riskRes)
      }

      // Show error if all requests failed
      const allFailed = (!runtimeRes || (typeof runtimeRes === 'object' && 'error' in runtimeRes)) &&
                        (!metricsRes || (typeof metricsRes === 'object' && 'error' in metricsRes)) &&
                        (!healthRes || (typeof healthRes === 'object' && 'error' in healthRes)) &&
                        (!riskRes || (typeof riskRes === 'object' && 'error' in riskRes))
      if (allFailed) {
        enqueueSnackbar(t('common.error') + ': Failed to load dashboard data', { variant: 'error' })
      }
    } catch (error) {
      console.error('Unexpected error fetching dashboard data:', error)
      enqueueSnackbar(t('common.error') + ': ' + String(error), { variant: 'error' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Handlers
  // ===================================
  const handleRefresh = async () => {
    enqueueSnackbar(t('common.loading') + '...', { variant: 'info' })
    await fetchData()
    enqueueSnackbar(t('common.success'), { variant: 'success' })
  }

  const handleNavigate = (path: string) => {
    navigate(path)
  }

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.home.title),
    subtitle: t(K.page.home.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      icon: <RefreshIcon />,
      variant: 'contained',
      onClick: handleRefresh,
    },
  ])

  // ===================================
  // Computed Values
  // ===================================
  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  const getStatusFromHealth = (): { status: string; color: 'success' | 'warning' | 'error' } => {
    if (!healthCheck) return { status: 'UNKNOWN', color: 'warning' }
    if (healthCheck.status === 'ok') return { status: 'OK', color: 'success' }
    if (healthCheck.status === 'warn') return { status: 'WARNING', color: 'warning' }
    if (healthCheck.status === 'degraded') return { status: 'DEGRADED', color: 'warning' }
    return { status: 'ERROR', color: 'error' }
  }

  const getRiskLevel = (): { level: string; color: 'success' | 'warning' | 'error' } => {
    if (!riskStatus) return { level: 'UNKNOWN', color: 'warning' }
    const risk = riskStatus.overall_risk
    if (risk < 30) return { level: 'LOW', color: 'success' }
    if (risk < 70) return { level: 'MEDIUM', color: 'warning' }
    return { level: 'HIGH', color: 'error' }
  }

  const getComponentsStatus = (): Array<{
    name: string
    status: string
    color: 'success' | 'warning' | 'error'
  }> => {
    if (!healthCheck) return []

    return Object.entries(healthCheck.components || {}).map(([name, check]) => {
      const checkData = check as { status: string; message?: string }
      const color: 'success' | 'warning' | 'error' =
        checkData.status === 'ok' ? 'success' : checkData.status === 'error' ? 'error' : 'warning'
      return {
        name,
        status: checkData.status === 'ok' ? 'ok' : checkData.status === 'error' ? 'error' : 'warn',
        color,
      }
    })
  }

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  // ===================================
  // Render: Overview Dashboard
  // ===================================
  const statusInfo = getStatusFromHealth()
  const riskInfo = getRiskLevel()
  const components = getComponentsStatus()

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Row 1: System Metrics Grid */}
      <DashboardGrid>
        {/* System Status Card */}
        <StatusCard
          title={t(K.page.home.systemStatus)}
          status={statusInfo.status}
          statusLabel={t(K.appBar.currentStatus)}
          meta={[
            {
              key: 'uptime',
              label: t(K.page.home.uptime),
              value: runtimeInfo ? formatUptime(runtimeInfo.uptime) : '-',
            },
            {
              key: 'pid',
              label: t(K.page.home.processId),
              value: runtimeInfo?.pid ? String(runtimeInfo.pid) : '-',
            },
          ]}
        />

        {/* Resource Usage Card */}
        <MetricCard
          title={t(K.page.home.resourceUsage)}
          metrics={[
            { key: 'cpu', label: t(K.page.home.cpu), value: metrics && metrics.cpu_usage != null ? `${metrics.cpu_usage.toFixed(1)}%` : '-' },
            {
              key: 'memory',
              label: t(K.page.home.memoryUsage),
              value: metrics && metrics.memory_usage != null ? `${(metrics.memory_usage / 1024 / 1024).toFixed(1)} MB` : '-',
            },
          ]}
        />

        {/* System Info Card */}
        <StatCard
          title={t(K.page.home.systemVersion)}
          value={runtimeInfo?.version || '-'}
        />

        {/* API Status Card */}
        <StatCard
          title={t(K.page.home.apiStatus)}
          value={statusInfo.status}
        />
      </DashboardGrid>

      {/* Row 2: Components Status */}
      <AppCard>
        <AppCardHeader title={t(K.page.home.componentStatus)} />
        <AppCardBody>
          {components.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant={BODY2_VARIANT} color={TEXT_SECONDARY}>
                {t('common.loading')}
                {LOADING_ELLIPSIS}
              </Typography>
            </Box>
          ) : (
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 2,
                p: 2,
                bgcolor: agentos.bg.section,
                border: `1px solid ${agentos.border.subtle}`,
                borderRadius: agentos.shape.radius.sm / 8,
              }}
            >
              {components.map((component) => (
                <Box
                  key={component.name}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    px: 2,
                    py: 1,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    minWidth: 180,
                    bgcolor: agentos.bg.paper,
                  }}
                >
                  {component.status === 'ok' ? (
                    <CheckCircleIcon sx={{ fontSize: 20, color: 'success.main' }} />
                  ) : component.status === 'warn' ? (
                    <WarningIcon sx={{ fontSize: 20, color: 'warning.main' }} />
                  ) : (
                    <ErrorIcon sx={{ fontSize: 20, color: 'error.main' }} />
                  )}
                  <Typography variant={BODY2_VARIANT} sx={{ flex: 1 }}>
                    {component.name}
                  </Typography>
                  <Chip
                    label={component.status.toUpperCase()}
                    color={component.color}
                    size={SIZE_SMALL}
                  />
                </Box>
              ))}
            </Box>
          )}
        </AppCardBody>
      </AppCard>

      {/* Row 3: Governance Status */}
      <AppCard>
        <AppCardHeader title={t(K.page.home.governanceStatus)} />
        <AppCardBody>
          {/* 🎨 Section container - uses bg.section for nested structure */}
          <Box
            sx={{
              p: 2,
              bgcolor: agentos.bg.section,
              border: `1px solid ${agentos.border.subtle}`,
              borderRadius: agentos.shape.radius.sm / 8,
            }}
          >
            <DashboardGrid>
              <StatCard
                title={t(K.page.home.riskLevel)}
                value={riskInfo.level}
              />
              <StatCard
                title={t(K.page.home.openFindings)}
                value={riskStatus ? String(Math.floor(riskStatus.policy_risk * 10)) : '-'}
              />
              <StatCard
                title={t(K.page.home.blockedRate)}
                value={riskStatus && riskStatus.execution_risk != null ? `${riskStatus.execution_risk.toFixed(1)}%` : '-'}
              />
            </DashboardGrid>
            <Box sx={{ mt: 2, textAlign: 'right' }}>
              <Typography
                variant={BODY2_VARIANT}
                color={COLOR_PRIMARY}
                sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                onClick={() => handleNavigate('/governance')}
              >
                {t(K.page.home.viewGovernanceDashboard)}
              </Typography>
            </Box>
          </Box>
        </AppCardBody>
      </AppCard>

      {/* Row 4: Quick Links */}
      <AppCard>
        <AppCardHeader title={t(K.page.home.quickLinks)} />
        <AppCardBody>
          {/* 🎨 Section container - uses bg.section for nested structure */}
          <Box
            sx={{
              p: 2,
              bgcolor: agentos.bg.section,
              border: `1px solid ${agentos.border.subtle}`,
              borderRadius: agentos.shape.radius.sm / 8,
            }}
          >
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
              {[
                { label: t(K.page.home.linkTasks), path: '/tasks' },
                { label: t(K.page.home.linkProjects), path: '/projects' },
                { label: t(K.page.home.linkMemory), path: '/memory' },
                { label: t(K.page.home.linkSkills), path: '/skills' },
                { label: t(K.page.home.linkLogs), path: '/logs' },
                { label: t(K.page.home.linkProviders), path: '/providers' },
              ].map((link) => (
                <Box
                  key={link.path}
                  sx={{
                    p: 2,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    bgcolor: agentos.bg.paper,
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: agentos.bg.elevated,
                    },
                  }}
                  onClick={() => handleNavigate(link.path)}
                >
                  <Typography variant={BODY2_VARIANT} fontWeight={500} textAlign={TEXT_ALIGN_CENTER}>
                    {link.label}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        </AppCardBody>
      </AppCard>
    </Box>
  )
}
