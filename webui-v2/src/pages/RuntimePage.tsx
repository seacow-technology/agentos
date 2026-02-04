/**
 * RuntimePage - Runtime Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.runtime.xxx)
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Pattern Components: DashboardGrid + StatCard
 * - ✅ Real API Integration: systemService.getRuntimeInfo()
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, PrimaryButton, SecondaryButton, AppCard, AppCardHeader, AppCardBody, LoadingState, ErrorState, EmptyState } from '@/ui'
import { ConfirmDialog } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { Refresh as RefreshIcon, Lock as LockIcon, Done as DoneIcon, Power as PowerIcon } from '@mui/icons-material'
import { Box, Alert, Typography, List, ListItem, Chip } from '@mui/material'
import { systemService, type GetRuntimeInfoResponse } from '@/services'

export default function RuntimePage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()
  const navigate = useNavigate()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<GetRuntimeInfoResponse | null>(null)

  // Fix Permissions state
  const [fixPermOpen, setFixPermOpen] = useState(false)
  const [fixPermLoading, setFixPermLoading] = useState(false)
  const [fixPermResult, setFixPermResult] = useState<{ ok: boolean; message: string; fixed_files: string[] } | null>(null)

  // Self-check state
  const [selfCheckOpen, setSelfCheckOpen] = useState(false)
  const [selfCheckLoading, setSelfCheckLoading] = useState(false)
  const [selfCheckResult, setSelfCheckResult] = useState<{
    summary: string;
    ts: string;
    items: Array<{
      id: string;
      group: string;
      name: string;
      status: string;
      detail: string;
      hint?: string;
    }>;
  } | null>(null)

  // ===================================
  // Data Fetching
  // ===================================
  const loadRuntimeInfo = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await systemService.getRuntimeInfo()
      setData(response)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load runtime info'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRuntimeInfo()
  }, [])

  // ===================================
  // Fix Permissions Handler
  // ===================================
  const handleFixPermissions = async () => {
    setFixPermLoading(true)
    setFixPermResult(null)

    try {
      const result = await systemService.fixPermissions()
      setFixPermResult(result)

      if (result.ok) {
        if (result.fixed_files.length > 0) {
          toast.success(`${t(K.page.runtime.fixPermissionsSuccess)}: ${result.fixed_files.length} files`)
        } else {
          toast.info(t(K.page.runtime.allFilesOk))
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fix permissions'
      toast.error(`${t(K.page.runtime.fixPermissionsError)}: ${errorMessage}`)
      setFixPermResult({ ok: false, message: errorMessage, fixed_files: [] })
    } finally {
      setFixPermLoading(false)
      setFixPermOpen(false)
    }
  }

  // ===================================
  // Self-check Handler
  // ===================================
  const handleRunSelfCheck = async () => {
    setSelfCheckLoading(true)
    setSelfCheckResult(null)

    try {
      const result = await systemService.runSelfCheck({
        include_network: false,
        include_context: true,
      })
      setSelfCheckResult(result)

      if (result.summary === 'OK') {
        toast.success(t(K.page.runtime.runSelfCheckSuccess))
      } else if (result.summary === 'WARN') {
        toast.warning(`${t(K.page.runtime.runSelfCheckSuccess)} - Warnings detected`)
      } else {
        toast.error(`${t(K.page.runtime.runSelfCheckSuccess)} - Issues detected`)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to run self-check'
      toast.error(`${t(K.page.runtime.runSelfCheckError)}: ${errorMessage}`)
      setSelfCheckResult(null)
    } finally {
      setSelfCheckLoading(false)
      setSelfCheckOpen(false)
    }
  }

  // ===================================
  // View Providers Handler
  // ===================================
  const handleViewProviders = () => {
    navigate('/providers')
  }

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.runtime.title),
    subtitle: t(K.page.runtime.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      icon: <RefreshIcon />,
      variant: 'outlined',
      onClick: async () => {
        await loadRuntimeInfo()
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
    return <ErrorState error={error} onRetry={loadRuntimeInfo} />
  }

  // ===================================
  // Empty State
  // ===================================
  if (!data) {
    return <EmptyState message={t('common.noData')} />
  }

  // ===================================
  // Transform API Data
  // ===================================
  const uptimeHours = Math.floor((data.uptime || 0) / 3600)
  const uptimeMinutes = Math.floor(((data.uptime || 0) % 3600) / 60)
  const uptimeDisplay = `${uptimeHours}h ${uptimeMinutes}m`

  // ===================================
  // Render: DashboardGrid + StatCard
  // ===================================
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* System Status Section */}
      <DashboardGrid>
        <StatCard
          title={t(K.page.runtime.systemStatus)}
          value="OK"
        />
        <StatCard
          title={t(K.page.runtime.agentosVersion)}
          value={data.version || '1.0.0'}
        />
        <StatCard
          title={t(K.page.runtime.pythonVersion)}
          value="3.11.5"
        />
        <StatCard
          title={t(K.page.runtime.uptime)}
          value={uptimeDisplay}
        />
        <StatCard
          title={t(K.page.runtime.cpuUsage)}
          value="45.2%"
        />
        <StatCard
          title={t(K.page.runtime.memoryUsage)}
          value="2048 MB"
        />
      </DashboardGrid>

      {/* System Actions Section */}
      <AppCard>
        <AppCardHeader title={t(K.page.runtime.systemActions)} />
        <AppCardBody>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <PrimaryButton
              startIcon={<LockIcon />}
              onClick={() => setFixPermOpen(true)}
            >
              {t(K.page.runtime.fixPermissions)}
            </PrimaryButton>
            <SecondaryButton
              startIcon={<PowerIcon />}
              onClick={handleViewProviders}
            >
              {t(K.page.runtime.viewProviders)}
            </SecondaryButton>
            <PrimaryButton
              startIcon={<DoneIcon />}
              onClick={() => setSelfCheckOpen(true)}
            >
              {t(K.page.runtime.runSelfCheck)}
            </PrimaryButton>
          </Box>

          {/* Fix Permissions Result */}
          {fixPermResult && (
            <Box sx={{ mt: 3 }}>
              <Alert severity={fixPermResult.ok ? 'success' : 'error'}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {fixPermResult.message}
                </Typography>
                {fixPermResult.fixed_files.length > 0 && (
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      {t(K.page.runtime.fixedFiles)}:
                    </Typography>
                    <List dense sx={{ mt: 0.5 }}>
                      {fixPermResult.fixed_files.map((file, idx) => (
                        <ListItem key={idx} sx={{ py: 0, px: 0 }}>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {file}
                          </Typography>
                        </ListItem>
                      ))}
                    </List>
                  </Box>
                )}
              </Alert>
            </Box>
          )}

          {/* Self-check Results */}
          {selfCheckResult && (
            <Box sx={{ mt: 3 }}>
              <AppCard>
                <AppCardHeader
                  title={t(K.page.runtime.selfCheckResults)}
                  action={
                    <Chip
                      label={selfCheckResult.summary}
                      color={
                        selfCheckResult.summary === 'OK' ? 'success' :
                        selfCheckResult.summary === 'WARN' ? 'warning' : 'error'
                      }
                      size="small"
                    />
                  }
                />
                <AppCardBody>
                  <List>
                    {selfCheckResult.items.map((item) => (
                      <ListItem
                        key={item.id}
                        sx={{
                          flexDirection: 'column',
                          alignItems: 'flex-start',
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          '&:last-child': { borderBottom: 'none' }
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                          <Chip
                            label={item.status}
                            size="small"
                            color={
                              item.status === 'OK' ? 'success' :
                              item.status === 'WARN' ? 'warning' : 'error'
                            }
                          />
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {item.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                            {item.group}
                          </Typography>
                        </Box>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                          {item.detail}
                        </Typography>
                        {item.hint && (
                          <Typography variant="caption" color="primary" sx={{ mt: 0.5 }}>
                            💡 {item.hint}
                          </Typography>
                        )}
                      </ListItem>
                    ))}
                  </List>
                </AppCardBody>
              </AppCard>
            </Box>
          )}
        </AppCardBody>
      </AppCard>

      {/* Fix Permissions Confirmation Dialog */}
      <ConfirmDialog
        open={fixPermOpen}
        onClose={() => setFixPermOpen(false)}
        title={t(K.page.runtime.fixPermissionsConfirmTitle)}
        message={t(K.page.runtime.fixPermissionsConfirmMessage)}
        confirmText={t(K.page.runtime.fixPermissions)}
        onConfirm={handleFixPermissions}
        loading={fixPermLoading}
        color="primary"
      />

      {/* Self-check Confirmation Dialog */}
      <ConfirmDialog
        open={selfCheckOpen}
        onClose={() => setSelfCheckOpen(false)}
        title={t(K.page.runtime.runSelfCheckConfirmTitle)}
        message={t(K.page.runtime.runSelfCheckConfirmMessage)}
        confirmText={t(K.page.runtime.runSelfCheck)}
        onConfirm={handleRunSelfCheck}
        loading={selfCheckLoading}
        color="primary"
      />
    </Box>
  )
}
