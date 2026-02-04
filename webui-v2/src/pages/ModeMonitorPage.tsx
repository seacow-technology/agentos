/**
 * ModeMonitorPage - 模式监控页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Real API Integration: systemService.getModeStats() + getModeAlerts()
 * - ✅ State Handling: Loading/Success/Error/Empty
 */

import { useState, useEffect, useCallback } from 'react'
import { Box, Typography, Chip, Divider } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState } from '@/ui'
import { DashboardIcon, WarningIcon, TimelineIcon, InfoIcon } from '@/ui/icons'
import { K, useText } from '@/ui/text'
import { DetailDrawer } from '@/ui/interaction'
import { systemService } from '@/services/system.service'
import { useSnackbar } from 'notistack'

// Constants to avoid string literals
const INCREASE_TYPE = 'increase' as const
const PRIMARY_COLOR = 'primary.main'
const INFO_COLOR = 'info.main'
const SUCCESS_COLOR = 'success.main'
const WARNING_COLOR = 'warning.main'

/**
 * ModeMonitorPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * API Integration: getModeStats() + getModeAlerts()
 */
export default function ModeMonitorPage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useText()
  const { enqueueSnackbar } = useSnackbar()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [modeStats, setModeStats] = useState<{
    total_alerts: number
    recent_count: number
    severity_breakdown: Record<string, number>
  } | null>(null)
  const [modeAlerts, setModeAlerts] = useState<Array<{
    timestamp: string
    severity: string
    mode_id: string
    operation: string
    message: string
    context: Record<string, any>
  }>>([])

  // ===================================
  // Drawer State - Mode Details
  // ===================================
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerContent, setDrawerContent] = useState<{
    type: 'stat' | 'metric'
    title: string
    data: any
  } | null>(null)

  // ===================================
  // Data Fetching
  // ===================================
  const fetchData = useCallback(async () => {
    try {
      setLoading(true)

      // Fetch mode stats and alerts in parallel
      const [statsRes, alertsRes] = await Promise.allSettled([
        systemService.getModeStats(),
        systemService.getModeAlerts(),
      ])

      // Handle mode stats
      if (statsRes.status === 'fulfilled') {
        // Backend returns { status: "ok", stats: { total_alerts, recent_count, severity_breakdown, ... } }
        const apiStats = (statsRes.value as any).stats
        setModeStats({
          total_alerts: apiStats.total_alerts || 0,
          recent_count: apiStats.recent_count || 0,
          severity_breakdown: apiStats.severity_breakdown || {},
        })
      } else {
        console.error('Failed to fetch mode stats:', statsRes.reason)
      }

      // Handle mode alerts
      if (alertsRes.status === 'fulfilled') {
        // Backend returns { status: "ok", alerts: [...] }
        const apiAlerts = (alertsRes.value as any).alerts || []
        setModeAlerts(apiAlerts)
      } else {
        console.error('Failed to fetch mode alerts:', alertsRes.reason)
      }

      // Show error only if both failed
      if (statsRes.status === 'rejected' && alertsRes.status === 'rejected') {
        enqueueSnackbar(t(K.page.modeMonitor.loadFailed), { variant: 'error' })
      }
    } catch (error) {
      console.error('Failed to fetch mode data:', error)
      enqueueSnackbar(t(K.page.modeMonitor.loadFailed), { variant: 'error' })
    } finally {
      setLoading(false)
    }
  }, [enqueueSnackbar, t])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // ===================================
  // Handlers
  // ===================================
  const handleRefresh = async () => {
    try {
      await fetchData()
      enqueueSnackbar(t(K.page.modeMonitor.refreshSuccess), { variant: 'success' })
    } catch (error) {
      console.error('Failed to refresh mode stats:', error)
      enqueueSnackbar(t(K.page.modeMonitor.refreshFailed), { variant: 'error' })
    }
  }

  const handleAnalyze = () => {
    // TODO: Implement analyze functionality in Phase 7
    enqueueSnackbar('Analyze functionality coming soon', { variant: 'info' })
  }

  // ===================================
  // Drawer Handlers - Mode Details
  // ===================================
  const handleStatClick = (statTitle: string, statData: any) => {
    setDrawerContent({
      type: 'stat',
      title: statTitle,
      data: statData,
    })
    setDrawerOpen(true)
  }

  const handleMetricClick = (metricTitle: string, metricData: any) => {
    setDrawerContent({
      type: 'metric',
      title: metricTitle,
      data: metricData,
    })
    setDrawerOpen(true)
  }

  const handleDrawerClose = () => {
    setDrawerOpen(false)
    // Delay clearing content until drawer animation completes
    setTimeout(() => {
      setDrawerContent(null)
    }, 300)
  }

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.modeMonitor.title),
    subtitle: t(K.page.modeMonitor.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: handleRefresh,
    },
    {
      key: 'analyze',
      label: t(K.page.modeMonitor.analyze),
      variant: 'contained',
      onClick: handleAnalyze,
    },
  ])

  // ===================================
  // Data Transformation
  // ===================================

  // Get severity breakdown
  const severityBreakdown = modeStats?.severity_breakdown || {}

  // Group alerts by mode_id
  const alertsByMode = modeAlerts.reduce((acc, alert) => {
    const mode = alert.mode_id || 'unknown'
    acc[mode] = (acc[mode] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // Calculate stats from API data
  const stats = [
    {
      title: t(K.page.modeMonitor.alertCount),
      value: modeStats?.total_alerts?.toString() || '0',
      change: `${modeStats?.recent_count || 0} recent`,
      changeType: INCREASE_TYPE,
      icon: <WarningIcon />,
      detailData: {
        totalAlerts: modeStats?.total_alerts || 0,
        recentAlerts: modeStats?.recent_count || 0,
        alerts: modeAlerts,
        severityBreakdown,
      },
    },
    {
      title: 'Critical Alerts',
      value: severityBreakdown.critical?.toString() || '0',
      change: severityBreakdown.critical > 0 ? 'Needs attention' : 'None',
      changeType: INCREASE_TYPE,
      icon: <WarningIcon />,
      detailData: {
        critical: severityBreakdown.critical || 0,
        alerts: modeAlerts.filter((alert) => alert.severity === 'critical'),
      },
    },
    {
      title: 'Active Alerts',
      value: modeAlerts.length.toString(),
      change: modeAlerts.length > 0 ? `${modeAlerts.length} active` : 'No alerts',
      changeType: INCREASE_TYPE,
      icon: <DashboardIcon />,
      detailData: {
        activeCount: modeAlerts.length,
        alerts: modeAlerts,
        byMode: alertsByMode,
      },
    },
  ]

  const metrics = [
    {
      title: 'Alert Severity Distribution',
      description: 'Distribution of alerts by severity level',
      metrics: [
        { key: 'critical', label: 'Critical', value: severityBreakdown.critical?.toString() || '0', valueColor: 'error.main' },
        { key: 'error', label: 'Error', value: severityBreakdown.error?.toString() || '0', valueColor: WARNING_COLOR },
        { key: 'warning', label: 'Warning', value: severityBreakdown.warning?.toString() || '0', valueColor: INFO_COLOR },
        { key: 'info', label: 'Info', value: severityBreakdown.info?.toString() || '0', valueColor: SUCCESS_COLOR },
      ],
      detailData: {
        severityBreakdown,
        alerts: modeAlerts,
        bySeverity: {
          critical: modeAlerts.filter((a) => a.severity === 'critical'),
          error: modeAlerts.filter((a) => a.severity === 'error'),
          warning: modeAlerts.filter((a) => a.severity === 'warning'),
          info: modeAlerts.filter((a) => a.severity === 'info'),
        },
      },
    },
    {
      title: 'Alert Statistics',
      description: 'Overview of mode alerts',
      metrics: [
        { key: 'total', label: 'Total Alerts', value: modeStats?.total_alerts?.toString() || '0', valueColor: PRIMARY_COLOR },
        { key: 'recent', label: 'Recent Alerts', value: modeStats?.recent_count?.toString() || '0', valueColor: INFO_COLOR },
        { key: 'active', label: 'Active Alerts', value: modeAlerts.length.toString(), valueColor: modeAlerts.length > 0 ? WARNING_COLOR : SUCCESS_COLOR },
      ],
      detailData: {
        stats: modeStats,
        alerts: modeAlerts,
        timeline: modeAlerts.sort((a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        ).slice(0, 10),
      },
    },
    {
      title: 'Alerts by Mode',
      description: 'Alert distribution across different modes',
      metrics: Object.keys(alertsByMode).length > 0
        ? Object.entries(alertsByMode).slice(0, 3).map(([mode, count]) => ({
            key: mode,
            label: mode,
            value: count.toString(),
            valueColor: INFO_COLOR,
          }))
        : [
            { key: 'none', label: 'No Alerts', value: '0', valueColor: SUCCESS_COLOR },
          ],
      detailData: {
        byMode: alertsByMode,
        modeDetails: Object.entries(alertsByMode).map(([mode, count]) => ({
          mode,
          count,
          alerts: modeAlerts.filter((a) => a.mode_id === mode),
        })),
      },
    },
  ]

  // ===================================
  // Helper: Render Drawer Content
  // ===================================
  const renderDrawerContent = () => {
    if (!drawerContent) return null

    const { type, data } = drawerContent

    if (type === 'stat') {
      return renderStatDetails(data)
    }

    if (type === 'metric') {
      return renderMetricDetails(data)
    }

    return null
  }

  /**
   * Render Stat Card Details
   */
  const renderStatDetails = (data: any) => {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Summary */}
        <Box>
          <Typography variant="caption" color="text.secondary" gutterBottom>
            {t(K.page.modeMonitor.summaryLabel)}
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
            {data.totalAlerts !== undefined && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{t(K.page.modeMonitor.alertTotal)}</Typography>
                <Typography variant="body1" fontWeight={600}>
                  {data.totalAlerts}
                </Typography>
              </Box>
            )}
            {data.recentAlerts !== undefined && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{t(K.page.modeMonitor.alertRecent)}</Typography>
                <Typography variant="body1" fontWeight={600}>
                  {data.recentAlerts}
                </Typography>
              </Box>
            )}
            {data.activeCount !== undefined && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{t(K.page.modeMonitor.alertActive)}</Typography>
                <Typography variant="body1" fontWeight={600}>
                  {data.activeCount}
                </Typography>
              </Box>
            )}
            {data.critical !== undefined && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2">{t(K.page.modeMonitor.alertCriticalCount)}</Typography>
                <Typography variant="body1" fontWeight={600} color="error.main">
                  {data.critical}
                </Typography>
              </Box>
            )}
          </Box>
        </Box>

        <Divider />

        {/* Severity Breakdown */}
        {data.severityBreakdown && (
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Severity Breakdown
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
              {Object.entries(data.severityBreakdown).map(([severity, count]) => (
                <Box
                  key={severity}
                  sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <Chip
                    label={severity}
                    size="small"
                    color={
                      severity === 'critical'
                        ? 'error'
                        : severity === 'error'
                        ? 'warning'
                        : severity === 'warning'
                        ? 'info'
                        : 'success'
                    }
                  />
                  <Typography variant="body1" fontWeight={600}>
                    {count as number}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}

        {data.byMode && (
          <>
            <Divider />
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Alerts by Mode
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                {Object.entries(data.byMode).map(([mode, count]) => (
                  <Box
                    key={mode}
                    sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                  >
                    <Typography variant="body2">{mode}</Typography>
                    <Chip label={count as number} size="small" />
                  </Box>
                ))}
              </Box>
            </Box>
          </>
        )}

        <Divider />

        {/* Alert Timeline */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <TimelineIcon sx={{ fontSize: 18, color: 'primary.main' }} />
            <Typography variant="caption" color="text.secondary">
              Recent Alerts Timeline
            </Typography>
          </Box>
          {data.alerts && data.alerts.length > 0 ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
              {data.alerts.slice(0, 10).map((alert: any, index: number) => (
                <Box
                  key={index}
                  sx={{
                    p: 2,
                    bgcolor: 'background.default',
                    borderRadius: 1,
                    borderLeft: (theme) =>
                      `4px solid ${
                        alert.severity === 'critical'
                          ? theme.palette.error.main
                          : alert.severity === 'error'
                          ? theme.palette.warning.main
                          : alert.severity === 'warning'
                          ? theme.palette.info.main
                          : theme.palette.success.main
                      }`,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Chip
                      label={alert.severity}
                      size="small"
                      color={
                        alert.severity === 'critical'
                          ? 'error'
                          : alert.severity === 'error'
                          ? 'warning'
                          : alert.severity === 'warning'
                          ? 'info'
                          : 'success'
                      }
                    />
                    <Typography variant="caption" color="text.secondary">
                      {new Date(alert.timestamp).toLocaleString()}
                    </Typography>
                  </Box>
                  <Typography variant="body2" fontWeight={600} gutterBottom>
                    {alert.mode_id} - {alert.operation}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {alert.message}
                  </Typography>
                  {alert.context && Object.keys(alert.context).length > 0 && (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        Context:
                      </Typography>
                      <Box
                        component="pre"
                        sx={{
                          mt: 0.5,
                          p: 1,
                          bgcolor: 'action.hover',
                          borderRadius: 0.5,
                          fontSize: '0.75rem',
                          overflow: 'auto',
                        }}
                      >
                        {JSON.stringify(alert.context, null, 2)}
                      </Box>
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <InfoIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                No alerts available
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    )
  }

  /**
   * Render Metric Card Details
   */
  const renderMetricDetails = (data: any) => {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Severity Distribution Details */}
        {data.bySeverity && (
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Severity Distribution Details
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
              {Object.entries(data.bySeverity).map(([severity, alerts]) => (
                <Box key={severity}>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mb: 1,
                    }}
                  >
                    <Chip
                      label={severity}
                      size="small"
                      color={
                        severity === 'critical'
                          ? 'error'
                          : severity === 'error'
                          ? 'warning'
                          : severity === 'warning'
                          ? 'info'
                          : 'success'
                      }
                    />
                    <Typography variant="body2" fontWeight={600}>
                      {(alerts as any[]).length} alerts
                    </Typography>
                  </Box>
                  {(alerts as any[]).length > 0 && (
                    <Box sx={{ pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}>
                      {(alerts as any[]).slice(0, 3).map((alert: any, idx: number) => (
                        <Box key={idx} sx={{ mb: 1 }}>
                          <Typography variant="caption" color="text.secondary">
                            {new Date(alert.timestamp).toLocaleString()}
                          </Typography>
                          <Typography variant="body2">{alert.message}</Typography>
                        </Box>
                      ))}
                      {(alerts as any[]).length > 3 && (
                        <Typography variant="caption" color="primary.main">
                          +{(alerts as any[]).length - 3} more...
                        </Typography>
                      )}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          </Box>
        )}

        {/* Timeline Details */}
        {data.timeline && (
          <>
            <Divider />
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TimelineIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                <Typography variant="caption" color="text.secondary">
                  Alert Timeline (Last 10)
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {data.timeline.map((alert: any, index: number) => (
                  <Box
                    key={index}
                    sx={{
                      p: 2,
                      bgcolor: 'background.default',
                      borderRadius: 1,
                      borderLeft: (theme) =>
                        `4px solid ${
                          alert.severity === 'critical'
                            ? theme.palette.error.main
                            : alert.severity === 'error'
                            ? theme.palette.warning.main
                            : alert.severity === 'warning'
                            ? theme.palette.info.main
                            : theme.palette.success.main
                        }`,
                    }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                          label={alert.severity}
                          size="small"
                          color={
                            alert.severity === 'critical'
                              ? 'error'
                              : alert.severity === 'error'
                              ? 'warning'
                              : alert.severity === 'warning'
                              ? 'info'
                              : 'success'
                          }
                        />
                        <Chip label={alert.mode_id} size="small" variant="outlined" />
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {new Date(alert.timestamp).toLocaleString()}
                      </Typography>
                    </Box>
                    <Typography variant="body2" fontWeight={600} gutterBottom>
                      {alert.operation}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {alert.message}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          </>
        )}

        {/* Mode Distribution Details */}
        {data.modeDetails && (
          <>
            <Divider />
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                Mode Distribution Details
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {data.modeDetails.map((modeDetail: any) => (
                  <Box key={modeDetail.mode}>
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 1,
                      }}
                    >
                      <Typography variant="body2" fontWeight={600}>
                        {modeDetail.mode}
                      </Typography>
                      <Chip label={`${modeDetail.count} alerts`} size="small" color="primary" />
                    </Box>
                    {modeDetail.alerts.length > 0 && (
                      <Box sx={{ pl: 2, borderLeft: '2px solid', borderColor: 'divider' }}>
                        {modeDetail.alerts.slice(0, 3).map((alert: any, idx: number) => (
                          <Box key={idx} sx={{ mb: 1 }}>
                            <Box sx={{ display: 'flex', gap: 1, mb: 0.5 }}>
                              <Chip
                                label={alert.severity}
                                size="small"
                                color={
                                  alert.severity === 'critical'
                                    ? 'error'
                                    : alert.severity === 'error'
                                    ? 'warning'
                                    : alert.severity === 'warning'
                                    ? 'info'
                                    : 'success'
                                }
                              />
                              <Typography variant="caption" color="text.secondary">
                                {new Date(alert.timestamp).toLocaleString()}
                              </Typography>
                            </Box>
                            <Typography variant="body2">{alert.message}</Typography>
                          </Box>
                        ))}
                        {modeDetail.alerts.length > 3 && (
                          <Typography variant="caption" color="primary.main">
                            +{modeDetail.alerts.length - 3} more...
                          </Typography>
                        )}
                      </Box>
                    )}
                  </Box>
                ))}
              </Box>
            </Box>
          </>
        )}

        {/* Stats Overview */}
        {data.stats && (
          <>
            <Divider />
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.modeMonitor.statsOverviewLabel)}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">{t(K.page.modeMonitor.alertTotal)}</Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {data.stats.total_alerts}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">{t(K.page.modeMonitor.alertRecent)}</Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {data.stats.recent_count}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">{t(K.page.modeMonitor.alertActive)}</Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {data.alerts?.length || 0}
                  </Typography>
                </Box>
              </Box>
            </Box>
          </>
        )}
      </Box>
    )
  }

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  // ===================================
  // Render: DashboardGrid Pattern
  // ===================================
  return (
    <>
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
            onClick={() => handleStatClick(stat.title, stat.detailData)}
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
                label: t(K.common.view),
                onClick: () => handleMetricClick(metric.title, metric.detailData),
              },
            ]}
          />
        ))}
      </DashboardGrid>

      {/* Detail Drawer */}
      <DetailDrawer
        open={drawerOpen}
        onClose={handleDrawerClose}
        title={drawerContent?.title || ''}
        subtitle={drawerContent?.type === 'stat' ? 'Statistics Details' : 'Metric Details'}
        width={700}
      >
        {drawerContent && renderDrawerContent()}
      </DetailDrawer>
    </>
  )
}
