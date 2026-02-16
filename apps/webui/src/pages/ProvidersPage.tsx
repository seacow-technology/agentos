/**
 * ProvidersPage - 提供商管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ CardGrid Pattern: CardCollectionWrap + ItemCard
 * - ✅ P0 Implementation: Real API integration
 *
 * P0 Features Implemented:
 * - P0-17: List Providers API (GET /api/providers)
 * - P0-18: Add Provider Wizard (multi-step DialogForm)
 * - P0-19: Configuration Dialog (DetailDrawer)
 * - P0-20: Start/Stop Service Buttons (conditional actions)
 * - P0-21: Status Refresh (manual + polling)
 */

import { useState } from 'react'
import { Box, Button, CircularProgress, Typography, List, ListItem, ListItemText, Checkbox, FormControlLabel } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useText } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { useProviders, type ProviderCardData } from '@/hooks/useProviders'
import { ProviderConfigDrawer } from '@/components/providers/ProviderConfigDrawer'
import { CloudProviderConfigDrawer } from '@/components/providers/CloudProviderConfigDrawer'
import { ExecutableConfigDialog } from '@/components/providers/ExecutableConfigDialog'
import { ProviderDiagnosticsDialog } from '@/components/providers/ProviderDiagnosticsDialog'
import { InstallCliDialog } from '@/components/providers/InstallCliDialog'
import { ProviderLogsDrawer } from '@/components/providers/ProviderLogsDrawer'
import { ModelPricingDialog } from '@/components/providers/ModelPricingDialog'
import { DetailDrawer } from '@/ui/interaction'
import { providersApi } from '@/api/providers'
import type { ModelInfoResponse, ModelPricingRow } from '@/api/providers'
import { CloudIcon, StorageIcon, CodeIcon as ApiIcon, VisibilityIcon, EditIcon, BugIcon, SettingsIcon, PlayArrowIcon, StopIcon, RestartAltIcon, TerminalIcon, DownloadIcon, SearchIcon, HelpOutlineIcon } from '@/ui/icons'
import { useWriteGate } from '@/ui/guards/useWriteGate'
import { notifyWriteGateBlocked } from '@/ui/guards/writeGateNotice'
import { WriteGateBanner } from '@/components/gates/WriteGateBanner'

// Constants
const ICON_SIZE_SMALL = 'small' as const
const VARIANT_H6 = 'h6' as const
const VARIANT_BODY2 = 'body2' as const
const COLOR_ERROR = 'error' as const
const COLOR_TEXT_SECONDARY = 'text.secondary' as const
// Constants moved to i18n

// Icon mapping by type
const getProviderIcon = (type: string) => {
  const iconMap: Record<string, JSX.Element> = {
    api: <ApiIcon />,
    cloud: <ApiIcon />,
    local: <StorageIcon />,
  }
  return iconMap[type.toLowerCase()] || <CloudIcon />
}

// State color mapping
const getStateColor = (state: string): 'success' | 'error' | 'warning' | 'default' => {
  const stateMap: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    available: 'success',
    connected: 'success',
    running: 'success',
    stopped: 'default',
    unavailable: 'error',
    error: 'error',
    unknown: 'warning',
  }
  return stateMap[state.toLowerCase()] || 'default'
}

// State translation mapping
const getStateTranslation = (state: string, t: (key: string) => string): string => {
  const stateMap: Record<string, string> = {
    available: t(K.common.available),
    connected: t(K.common.connected),
    running: t(K.common.running),
    stopped: t(K.common.stopped),
    unavailable: t(K.common.unavailable),
    error: t(K.common.error),
    unknown: t(K.common.unknown),
  }
  return stateMap[state.toLowerCase()] || state
}

/**
 * ProvidersPage 组件
 *
 * P0 Implementation Complete
 */
export default function ProvidersPage() {
  const { t } = useText()
  const writeGate = useWriteGate('FEATURE_PROVIDERS_CONTROL')

  // P0-17: Load providers data
  const { localProviders, cloudProviders, allProviders, loading, error, refresh } =
    useProviders()

  // P0-19: Config Drawer state
  const [configDrawerState, setConfigDrawerState] = useState<{
    open: boolean
    providerId: string
    instanceId: string
    currentEndpoint: string
    currentEnabled: boolean
  }>({
    open: false,
    providerId: '',
    instanceId: '',
    currentEndpoint: '',
    currentEnabled: true,
  })

  // Step 3: Cloud credentials drawer state
  const [cloudConfigState, setCloudConfigState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
  })

  // P1-21: Models View state
  const [modelsViewState, setModelsViewState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
    loading: boolean
    models: ModelInfoResponse[]
    error: string | null
    pricingByModel: Record<string, ModelPricingRow>
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
    loading: false,
    models: [],
    error: null,
    pricingByModel: {},
  })

  const [pricingDialogState, setPricingDialogState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
    modelId: string
    modelLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
    modelId: '',
    modelLabel: '',
  })

  // P2-23: Diagnostic Dialog state
  const [diagnosticDialogState, setDiagnosticDialogState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
  })

  // P2-24: Executable Config Dialog state
  const [executableConfigState, setExecutableConfigState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
  })

  // P2-25: Advanced Diagnostics Dialog state
  const [advancedDiagnosticsState, setAdvancedDiagnosticsState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
  })

  // Local CLI install dialog state
  const [installCliState, setInstallCliState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
  })

  // Local logs drawer state
  const [logsState, setLogsState] = useState<{
    open: boolean
    providerId: string
    instanceId: string
    providerLabel: string
  }>({
    open: false,
    providerId: '',
    instanceId: 'default',
    providerLabel: '',
  })

  // Page Header
  usePageHeader({
    title: t(K.page.providers.title),
    subtitle: t(K.page.providers.subtitle),
  })

  // P0-21: Refresh and P0-18: Add Provider actions
  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        try {
          await refresh()
        } catch (err) {
          toast.error(t(K.page.providers.failedRefresh))
        }
      },
    },
  ])

  // P0-19: Open config drawer
  const handleConfigure = (provider: ProviderCardData) => {
    // Parse instance ID from provider.id (format: "provider:instance")
    const [providerId, instanceId] = provider.id.split(':')
    setConfigDrawerState({
      open: true,
      providerId: providerId || provider.id,
      instanceId: instanceId || 'default',
      currentEndpoint: provider.endpoint || '',
      currentEnabled: true,
    })
  }

  const handleConfigureCloud = (provider: ProviderCardData) => {
    const providerId = provider.id.split(':')[0] || provider.id
    setCloudConfigState({
      open: true,
      providerId,
      providerLabel: provider.label,
    })
  }

  const handleStartLocal = async (provider: ProviderCardData) => {
    if (!writeGate.allowed) {
      notifyWriteGateBlocked(writeGate, t)
      return
    }
    const [providerId, instanceId] = provider.id.split(':')
    try {
      const res = await providersApi.startInstance(providerId || provider.id, instanceId || 'default')
      toast.success(res.message || t(K.page.providers.started))
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedStart))
    }
  }

  const handleStopLocal = async (provider: ProviderCardData) => {
    if (!writeGate.allowed) {
      notifyWriteGateBlocked(writeGate, t)
      return
    }
    const [providerId, instanceId] = provider.id.split(':')
    try {
      const res = await providersApi.stopInstance(providerId || provider.id, instanceId || 'default')
      toast.success(res.message || t(K.page.providers.stopped))
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedStop))
    }
  }

  const handleRestartLocal = async (provider: ProviderCardData) => {
    if (!writeGate.allowed) {
      notifyWriteGateBlocked(writeGate, t)
      return
    }
    const [providerId, instanceId] = provider.id.split(':')
    try {
      const res = await providersApi.restartInstance(providerId || provider.id, instanceId || 'default')
      toast.success(res.message || t(K.page.providers.restarted))
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedRestart))
    }
  }

  const handleDetectCli = async (provider: ProviderCardData) => {
    if (!writeGate.allowed) {
      notifyWriteGateBlocked(writeGate, t)
      return
    }
    const providerId = provider.id.split(':')[0] || provider.id
    try {
      const res = await providersApi.detectExecutable(providerId)
      if (res.detected && res.resolved_path) {
        toast.success(
          t(K.page.providers.executableDetectedToast, { provider: provider.label, path: res.resolved_path })
        )
      } else {
        toast.warning(t(K.page.providers.executableNotFoundToast, { provider: provider.label }))
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.executableDetectFailed))
    }
  }

  const handleOpenInstallCli = (provider: ProviderCardData) => {
    const providerId = provider.id.split(':')[0] || provider.id
    setInstallCliState({ open: true, providerId, providerLabel: provider.label })
  }

  const handleOpenLogs = (provider: ProviderCardData) => {
    const [providerId, instanceId] = provider.id.split(':')
    setLogsState({
      open: true,
      providerId: providerId || provider.id,
      instanceId: instanceId || 'default',
      providerLabel: provider.label,
    })
  }

  // P1-21: View Models Handler
  const handleViewModels = async (provider: ProviderCardData) => {
    const providerId = provider.id.split(':')[0] || provider.id

    setModelsViewState({
      open: true,
      providerId: providerId,
      providerLabel: provider.label,
      loading: true,
      models: [],
      error: null,
      pricingByModel: {},
    })

    try {
      const response = await providersApi.getProviderModels(providerId)
      let pricingByModel: Record<string, ModelPricingRow> = {}
      try {
        const pricingRes = await providersApi.getProviderModelPricing(providerId)
        pricingByModel = Object.fromEntries(
          (pricingRes.pricing || []).map((p) => [String(p.model), p])
        )
      } catch {
        pricingByModel = {}
      }
      setModelsViewState((prev) => ({
        ...prev,
        loading: false,
        models: response.models,
        pricingByModel,
      }))
    } catch (err) {
      setModelsViewState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : t(K.page.providers.failedLoadModels),
      }))
    }
  }

  const handleToggleModelUsed = async (modelId: string, used: boolean) => {
    if (!writeGate.allowed) {
      notifyWriteGateBlocked(writeGate, t)
      return
    }
    const providerId = modelsViewState.providerId
    if (!providerId) return

    // Optimistic update
    setModelsViewState((prev) => ({
      ...prev,
      models: prev.models.map((m) => (m.id === modelId ? { ...m, used } : m)),
    }))

    try {
      await providersApi.setModelUsed(providerId, modelId, used)
    } catch (err) {
      // Rollback
      setModelsViewState((prev) => ({
        ...prev,
        models: prev.models.map((m) => (m.id === modelId ? { ...m, used: !used } : m)),
      }))
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedUpdateModel))
    }
  }

  // P2-23: Diagnostic Dialog Handler
  const handleOpenDiagnostics = (provider: ProviderCardData) => {
    const providerId = provider.id.split(':')[0] || provider.id

    setDiagnosticDialogState({
      open: true,
      providerId: providerId,
      providerLabel: provider.label,
    })
  }

  // P1-21: Get View Models action (conditional)
  const getViewModelsAction = (provider: ProviderCardData) => {
    // Only show for providers that support models
    if (!provider.supports_models) {
      return null
    }

    return {
      key: 'view-models',
      label: t(K.page.providers.viewModels),
      variant: 'outlined' as const,
      icon: <VisibilityIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: t(K.page.providers.viewModels),
      onClick: () => handleViewModels(provider),
    }
  }

  // P2-23: Get Diagnostics action
  const getDiagnosticsAction = (provider: ProviderCardData) => {
    return {
      key: 'diagnostics',
      label: t(K.page.providers.diagnostics),
      variant: 'outlined' as const,
      icon: <BugIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: t(K.page.providers.diagnostics),
      onClick: () => handleOpenDiagnostics(provider),
    }
  }

  // P2-24: Get Detect Executable action (for local providers)
  const getDetectExecutableAction = (provider: ProviderCardData) => {
    // Only show for local providers that support executables
    if (provider.type !== 'local') {
      return null
    }

    const providerId = provider.id.split(':')[0] || provider.id
    const supportsExecutable = ['ollama', 'llamacpp', 'lmstudio'].includes(providerId)

    if (!supportsExecutable) {
      return null
    }

    return {
      key: 'detect-executable',
      label: t(K.page.providers.configureCli),
      variant: 'outlined' as const,
      icon: <SettingsIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: t(K.page.providers.detectConfigureExecutablePath),
      onClick: () => {
        setExecutableConfigState({
          open: true,
          providerId,
          providerLabel: provider.label,
        })
      },
    }
  }

  const getLocalCoreActions = (provider: ProviderCardData) => {
    if (provider.type !== 'local') return []
    const baseId = provider.id.split(':')[0] || provider.id
    const isLmStudio = baseId === 'lmstudio'
    const state = provider.state.toLowerCase()

    const actions = [
      {
        key: 'cli-detect',
        label: t(K.page.providers.detectCli),
        variant: 'outlined' as const,
        icon: <SearchIcon fontSize={ICON_SIZE_SMALL} />,
        tooltip: t(K.page.providers.detectCli),
        onClick: () => handleDetectCli(provider),
      },
      {
        key: 'cli-install',
        label: t(K.page.providers.installCli),
        variant: 'outlined' as const,
        icon: <DownloadIcon fontSize={ICON_SIZE_SMALL} />,
        tooltip: t(K.page.providers.installCli),
        onClick: () => handleOpenInstallCli(provider),
      },
      {
        key: 'logs',
        label: t(K.page.providers.logs),
        variant: 'outlined' as const,
        icon: <TerminalIcon fontSize={ICON_SIZE_SMALL} />,
        tooltip: t(K.page.providers.logs),
        disabled: isLmStudio,
        onClick: () => handleOpenLogs(provider),
      },
      {
        key: 'troubleshoot',
        label: t(K.page.providers.troubleshooting),
        variant: 'outlined' as const,
        icon: <HelpOutlineIcon fontSize={ICON_SIZE_SMALL} />,
        tooltip: t(K.page.providers.troubleshooting),
        onClick: () => handleOpenDiagnostics(provider),
      },
    ]

    // Start/Stop/Restart controls (manual lifecycle gets best-effort start only)
    if (state === 'stopped' || state === 'unavailable' || state === 'error') {
      actions.unshift({
        key: 'start',
        label: t('common.start') || 'Start',
        variant: 'outlined' as const,
        icon: <PlayArrowIcon fontSize={ICON_SIZE_SMALL} />,
        tooltip: t('common.start') || 'Start',
        onClick: () => handleStartLocal(provider),
      })
    } else if (state === 'running' || state === 'available' || state === 'connected') {
      actions.unshift(
        {
          key: 'stop',
          label: t('common.stop') || 'Stop',
          variant: 'outlined' as const,
          icon: <StopIcon fontSize={ICON_SIZE_SMALL} />,
          tooltip: t('common.stop') || 'Stop',
          disabled: isLmStudio,
          onClick: () => handleStopLocal(provider),
        },
        {
          key: 'restart',
          label: t('common.restart') || 'Restart',
          variant: 'outlined' as const,
          icon: <RestartAltIcon fontSize={ICON_SIZE_SMALL} />,
          tooltip: t('common.restart') || 'Restart',
          disabled: isLmStudio,
          onClick: () => handleRestartLocal(provider),
        }
      )
    }

    return actions
  }

  // P2-25: Get Advanced Diagnostics action
  const getAdvancedDiagnosticsAction = (provider: ProviderCardData) => {
    const providerId = provider.id.split(':')[0] || provider.id
    const supportsAdvancedDiag = ['ollama', 'llamacpp', 'lmstudio'].includes(providerId)

    if (!supportsAdvancedDiag) {
      return null
    }

    return {
      key: 'advanced-diagnostics',
      label: t(K.page.providers.advancedDiagnostics),
      variant: 'outlined' as const,
      icon: <SettingsIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: t(K.page.providers.viewAdvancedDiagnostics),
      onClick: () => {
        setAdvancedDiagnosticsState({
          open: true,
          providerId,
          providerLabel: provider.label,
        })
      },
    }
  }

  // Loading state
  if (loading && allProviders.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    )
  }

  // Error state
  if (error && allProviders.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant={VARIANT_H6} color={COLOR_ERROR} gutterBottom>
          {t(K.page.providers.failedLoadProviders)}
        </Typography>
        <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
          {error.message}
        </Typography>
      </Box>
    )
  }

  return (
    <>
      <WriteGateBanner
        featureKey="FEATURE_PROVIDERS_CONTROL"
        reason={writeGate.reason}
        missingOperations={writeGate.missingOperations}
      />

      {/* Local providers section */}
      <Box sx={{ mt: 2 }}>
        <Typography variant={VARIANT_H6} sx={{ mb: 1 }}>
          {t(K.page.providers.sectionLocalTitle, { count: localProviders.length })}
        </Typography>
        {localProviders.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6 }}>
            <Typography variant={VARIANT_H6} gutterBottom>
              {t(K.page.providers.localEmptyTitle)}
            </Typography>
            <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
              {t(K.page.providers.localEmptySubtitle)}
            </Typography>
          </Box>
        ) : (
          <CardCollectionWrap layout="grid" columns={3} gap={16}>
            {localProviders.map((provider) => {
              const viewModelsAction = getViewModelsAction(provider)
              const detectExecutableAction = getDetectExecutableAction(provider)
              const advancedDiagnosticsAction = getAdvancedDiagnosticsAction(provider)

              return (
                <ItemCard
                  key={provider.id}
                  title={provider.label}
                  description={provider.type}
                  meta={[
                    {
                      key: 'state',
                      label: t('form.field.status'),
                      value: (
                        <Typography
                          variant="caption"
                          sx={{
                            display: 'inline-block',
                            px: 1,
                            py: 0.5,
                            borderRadius: 1,
                            backgroundColor:
                              getStateColor(provider.state) === 'success'
                                ? '#4caf50'
                                : getStateColor(provider.state) === 'error'
                                ? '#f44336'
                                : getStateColor(provider.state) === 'warning'
                                ? '#ff9800'
                                : '#9e9e9e',
                            color: '#fff',
                            fontWeight: 500,
                          }}
                        >
                          {getStateTranslation(provider.state, t)}
                        </Typography>
                      ),
                    },
                    {
                      key: 'endpoint',
                      label: t(K.page.providers.columnApiEndpoint),
                      value: provider.endpoint || 'N/A',
                    },
                    ...(provider.latency_ms !== null
                      ? [
                          {
                            key: 'latency',
                            label: t(K.page.providers.latency),
                            value: `${provider.latency_ms.toFixed(0)}ms`,
                          },
                        ]
                      : []),
                    ...(provider.last_error
                      ? [
                          {
                            key: 'error',
                            label: t(K.page.providers.error),
                            value: provider.last_error,
                          },
                        ]
                      : []),
                  ]}
                  icon={getProviderIcon(provider.type)}
                  actions={[
                    ...getLocalCoreActions(provider),
                    ...(detectExecutableAction ? [detectExecutableAction] : []),
                    ...(advancedDiagnosticsAction ? [advancedDiagnosticsAction] : []),
                    ...(viewModelsAction ? [viewModelsAction] : []),
                    {
                      key: 'configure',
                      label: t('common.edit'),
                      variant: 'outlined' as const,
                      icon: <EditIcon fontSize={ICON_SIZE_SMALL} />,
                      tooltip: t('common.edit'),
                      onClick: () => {
                        if (!writeGate.allowed) {
                          notifyWriteGateBlocked(writeGate, t)
                          return
                        }
                        handleConfigure(provider)
                      },
                    },
                  ]}
                />
              )
            })}
          </CardCollectionWrap>
        )}
      </Box>

      {/* Cloud providers section */}
      <Box sx={{ mt: 4 }}>
        <Typography variant={VARIANT_H6} sx={{ mb: 1 }}>
          {t(K.page.providers.sectionCloudTitle, { count: cloudProviders.length })}
        </Typography>
        {cloudProviders.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6 }}>
            <Typography variant={VARIANT_H6} gutterBottom>
              {t(K.page.providers.cloudEmptyTitle)}
            </Typography>
            <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
              {t(K.page.providers.cloudEmptySubtitle)}
            </Typography>
          </Box>
        ) : (
          <CardCollectionWrap layout="grid" columns={3} gap={16}>
            {cloudProviders.map((provider) => {
              const viewModelsAction = getViewModelsAction(provider)
              const diagnosticsAction = getDiagnosticsAction(provider)

              return (
                <ItemCard
                  key={provider.id}
                  title={provider.label}
                  description={provider.type}
                  meta={[
                    {
                      key: 'state',
                      label: t('form.field.status'),
                      value: (
                        <Typography
                          variant="caption"
                          sx={{
                            display: 'inline-block',
                            px: 1,
                            py: 0.5,
                            borderRadius: 1,
                            backgroundColor:
                              getStateColor(provider.state) === 'success'
                                ? '#4caf50'
                                : getStateColor(provider.state) === 'error'
                                ? '#f44336'
                                : getStateColor(provider.state) === 'warning'
                                ? '#ff9800'
                                : '#9e9e9e',
                            color: '#fff',
                            fontWeight: 500,
                          }}
                        >
                          {getStateTranslation(provider.state, t)}
                        </Typography>
                      ),
                    },
                    {
                      key: 'endpoint',
                      label: t(K.page.providers.columnApiEndpoint),
                      value: provider.endpoint || 'N/A',
                    },
                    ...(provider.latency_ms !== null
                      ? [
                          {
                            key: 'latency',
                            label: t(K.page.providers.latency),
                            value: `${provider.latency_ms.toFixed(0)}ms`,
                          },
                        ]
                      : []),
                    ...(provider.last_error
                      ? [
                          {
                            key: 'error',
                            label: t(K.page.providers.error),
                            value: provider.last_error,
                          },
                        ]
                      : []),
                  ]}
                  icon={getProviderIcon(provider.type)}
                  actions={[
                    diagnosticsAction,
                    ...(viewModelsAction ? [viewModelsAction] : []),
                    {
                      key: 'cloud-config',
                      label: t(K.page.providers.configureApiKey),
                      variant: 'outlined' as const,
                      icon: <SettingsIcon fontSize={ICON_SIZE_SMALL} />,
                      tooltip: t(K.page.providers.configureApiKey),
                      onClick: () => {
                        if (!writeGate.allowed) {
                          notifyWriteGateBlocked(writeGate, t)
                          return
                        }
                        handleConfigureCloud(provider)
                      },
                    },
                  ]}
                />
              )
            })}
          </CardCollectionWrap>
        )}
      </Box>

      {/* P0-19: Config Drawer */}
      <ProviderConfigDrawer
        open={configDrawerState.open}
        onClose={() => setConfigDrawerState((prev) => ({ ...prev, open: false }))}
        onSuccess={() => {
          refresh()
        }}
        providerId={configDrawerState.providerId}
        instanceId={configDrawerState.instanceId}
        currentEndpoint={configDrawerState.currentEndpoint}
        currentEnabled={configDrawerState.currentEnabled}
      />

      {/* Step 3: Cloud credentials drawer */}
      <CloudProviderConfigDrawer
        open={cloudConfigState.open && writeGate.allowed}
        onClose={() => setCloudConfigState((prev) => ({ ...prev, open: false }))}
        onSuccess={() => {
          refresh()
        }}
        providerId={cloudConfigState.providerId}
        providerLabel={cloudConfigState.providerLabel}
      />

      {/* Local: Install CLI dialog */}
      <InstallCliDialog
        open={installCliState.open && writeGate.allowed}
        onClose={() => setInstallCliState((prev) => ({ ...prev, open: false }))}
        providerId={installCliState.providerId}
        providerLabel={installCliState.providerLabel}
      />

      {/* Local: Logs drawer */}
      <ProviderLogsDrawer
        open={logsState.open && writeGate.allowed}
        onClose={() => setLogsState((prev) => ({ ...prev, open: false }))}
        providerId={logsState.providerId}
        instanceId={logsState.instanceId}
        providerLabel={logsState.providerLabel}
      />

      {/* P1-21: Models View Drawer */}
      <DetailDrawer
        open={modelsViewState.open}
        onClose={() =>
          setModelsViewState({
            open: false,
            providerId: '',
            providerLabel: '',
            loading: false,
            models: [],
            error: null,
            pricingByModel: {},
          })
        }
        title={t(K.page.providers.modelsTitle) + ` - ${modelsViewState.providerLabel}`}
        subtitle={t(K.page.providers.modelsSubtitle) + `: ${modelsViewState.providerId}`}
      >
        {modelsViewState.loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : modelsViewState.error ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body1" color="error" gutterBottom>
              {t(K.page.providers.failedLoadModels)}
            </Typography>
            <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
              {modelsViewState.error}
            </Typography>
          </Box>
        ) : modelsViewState.models.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body1" color="text.secondary">
              {t(K.page.providers.noModelsAvailable)}
            </Typography>
          </Box>
        ) : (
          <List>
            {modelsViewState.models.map((model, index) => (
              <ListItem
                key={model.id}
                sx={{
                  borderBottom:
                    index < modelsViewState.models.length - 1 ? '1px solid' : 'none',
                  borderColor: 'divider',
                  py: 2,
                }}
              >
                <ListItemText
                  primary={model.label}
                  secondary={
                    <>
                      <Typography variant="caption" component="span" color="text.secondary">
                        ID: {model.id}
                      </Typography>
                      {modelsViewState.pricingByModel[model.id] && (
                        <>
                          <br />
                          <Typography variant="caption" component="span" color="text.secondary">
                            {t(K.page.providers.modelPricingLabel)}: $
                            {Number(modelsViewState.pricingByModel[model.id].input_per_1m).toFixed(4)}/$
                            {Number(modelsViewState.pricingByModel[model.id].output_per_1m).toFixed(4)}{' '}
                            {t(K.page.providers.modelPricingPer1m)}
                          </Typography>
                        </>
                      )}
                      {model.context_window && (
                        <>
                          <br />
                          <Typography
                            variant="caption"
                            component="span"
                            color="text.secondary"
                          >
                            {t(K.page.providers.contextWindow)}: {model.context_window.toLocaleString()} {t(K.page.providers.tokens)}
                          </Typography>
                        </>
                      )}
                    </>
                  }
                />
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, ml: 2 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() =>
                      setPricingDialogState({
                        open: true,
                        providerId: modelsViewState.providerId,
                        providerLabel: modelsViewState.providerLabel,
                        modelId: model.id,
                        modelLabel: model.label || model.id,
                      })
                    }
                    disabled={!writeGate.allowed}
                  >
                    {modelsViewState.pricingByModel[model.id]
                      ? t(K.page.providers.modelPricingEdit)
                      : t(K.page.providers.modelPricingSet)}
                  </Button>
                  <FormControlLabel
                    sx={{ whiteSpace: 'nowrap' }}
                    control={
                      <Checkbox
                        checked={Boolean((model as ModelInfoResponse).used)}
                        onChange={(e) => handleToggleModelUsed(model.id, e.target.checked)}
                        disabled={!writeGate.allowed}
                      />
                    }
                    label={t(K.page.providers.modelUsed)}
                  />
                </Box>
              </ListItem>
            ))}
          </List>
        )}
      </DetailDrawer>

      <ModelPricingDialog
        open={pricingDialogState.open && writeGate.allowed}
        onClose={() =>
          setPricingDialogState({
            open: false,
            providerId: '',
            providerLabel: '',
            modelId: '',
            modelLabel: '',
          })
        }
        providerId={pricingDialogState.providerId}
        providerLabel={pricingDialogState.providerLabel}
        modelId={pricingDialogState.modelId}
        modelLabel={pricingDialogState.modelLabel}
        current={modelsViewState.pricingByModel[pricingDialogState.modelId] || null}
        onSaved={(row) => {
          setModelsViewState((prev) => {
            const next = { ...(prev.pricingByModel || {}) }
            if (row) next[String(row.model)] = row
            else delete next[String(pricingDialogState.modelId)]
            return { ...prev, pricingByModel: next }
          })
        }}
      />

      {/* P2-23: Diagnostic Dialog */}
      <ProviderDiagnosticsDialog
        open={diagnosticDialogState.open}
        onClose={() =>
          setDiagnosticDialogState({
            open: false,
            providerId: '',
            providerLabel: '',
          })
        }
        providerId={diagnosticDialogState.providerId}
        providerLabel={diagnosticDialogState.providerLabel}
      />

      {/* P2-24: Executable Configuration Dialog */}
      <ExecutableConfigDialog
        open={executableConfigState.open}
        onClose={() =>
          setExecutableConfigState({
            open: false,
            providerId: '',
            providerLabel: '',
          })
        }
        onSuccess={() => {
          refresh()
        }}
        providerId={executableConfigState.providerId}
        providerLabel={executableConfigState.providerLabel}
      />

      {/* P2-25: Advanced Diagnostics Dialog */}
      <ProviderDiagnosticsDialog
        open={advancedDiagnosticsState.open}
        onClose={() =>
          setAdvancedDiagnosticsState({
            open: false,
            providerId: '',
            providerLabel: '',
          })
        }
        providerId={advancedDiagnosticsState.providerId}
        providerLabel={advancedDiagnosticsState.providerLabel}
      />
    </>
  )
}
