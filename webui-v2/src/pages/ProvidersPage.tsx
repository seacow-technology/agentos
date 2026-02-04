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
import { Box, CircularProgress, Typography, List, ListItem, ListItemText } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useText } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { useProviders, type ProviderCardData } from '@/hooks/useProviders'
import { AddProviderWizard } from '@/components/providers/AddProviderWizard'
import { ProviderConfigDrawer } from '@/components/providers/ProviderConfigDrawer'
import { ExecutableConfigDialog } from '@/components/providers/ExecutableConfigDialog'
import { ProviderDiagnosticsDialog } from '@/components/providers/ProviderDiagnosticsDialog'
import { ConfirmDialog, DetailDrawer } from '@/ui/interaction'
import { providersApi } from '@/api/providers'
import type { ModelInfoResponse } from '@/api/providers'
import { CloudIcon, StorageIcon, CodeIcon as ApiIcon, PlayArrowIcon, StopIcon, RestartAltIcon, VisibilityIcon, EditIcon, DeleteIcon, BugIcon, SettingsIcon } from '@/ui/icons'

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

  // P0-17: Load providers data
  const { providers, loading, error, refresh, startOllama, stopOllama, restartOllama } =
    useProviders()

  // P0-18: Add Provider Wizard state
  const [wizardOpen, setWizardOpen] = useState(false)

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

  // P1-20: Delete Confirmation state
  const [deleteState, setDeleteState] = useState<{
    open: boolean
    providerId: string
    instanceId: string
    providerLabel: string
    loading: boolean
  }>({
    open: false,
    providerId: '',
    instanceId: '',
    providerLabel: '',
    loading: false,
  })

  // P1-21: Models View state
  const [modelsViewState, setModelsViewState] = useState<{
    open: boolean
    providerId: string
    providerLabel: string
    loading: boolean
    models: ModelInfoResponse[]
    error: string | null
  }>({
    open: false,
    providerId: '',
    providerLabel: '',
    loading: false,
    models: [],
    error: null,
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
    {
      key: 'add',
      label: t(K.page.providers.addProvider),
      variant: 'contained',
      onClick: () => {
        setWizardOpen(true)
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

  // P0-20 & P1-22: Lifecycle control handlers
  const handleStartOllama = async () => {
    try {
      await startOllama()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedStart))
    }
  }

  const handleStopOllama = async () => {
    try {
      await stopOllama()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedStop))
    }
  }

  const handleRestartOllama = async () => {
    try {
      await restartOllama()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedRestart))
    }
  }

  // P1-20: Delete Provider Handler
  const handleDeleteClick = (provider: ProviderCardData) => {
    const [providerId, instanceId] = provider.id.split(':')
    setDeleteState({
      open: true,
      providerId: providerId || provider.id,
      instanceId: instanceId || 'default',
      providerLabel: provider.label,
      loading: false,
    })
  }

  const handleDeleteConfirm = async () => {
    setDeleteState((prev) => ({ ...prev, loading: true }))
    try {
      // Real API: await systemService.deleteProviderInstance()
      await providersApi.deleteInstance(deleteState.providerId, deleteState.instanceId)
      setDeleteState({
        open: false,
        providerId: '',
        instanceId: '',
        providerLabel: '',
        loading: false,
      })
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t(K.page.providers.failedDelete))
      setDeleteState((prev) => ({ ...prev, loading: false }))
    }
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
    })

    try {
      const response = await providersApi.getProviderModels(providerId)
      setModelsViewState((prev) => ({
        ...prev,
        loading: false,
        models: response.models,
      }))
    } catch (err) {
      setModelsViewState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : t(K.page.providers.failedLoadModels),
      }))
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

  // P0-20 & P1-22: Get lifecycle actions for provider
  const getLifecycleActions = (provider: ProviderCardData) => {
    const actions = []

    // P1-22: Only show lifecycle controls for Ollama (supports_start)
    if (provider.supports_start && provider.id.startsWith('ollama')) {
      const state = provider.state.toLowerCase()

      // Start button (when stopped)
      if (state === 'stopped' || state === 'unavailable') {
        actions.push({
          key: 'start',
          label: t('common.start') || 'Start',
          variant: 'outlined' as const,
          icon: <PlayArrowIcon fontSize={ICON_SIZE_SMALL} />,
          tooltip: t('common.start') || 'Start',
          onClick: handleStartOllama,
        })
      }

      // Stop button (when running)
      if (state === 'running' || state === 'available') {
        actions.push({
          key: 'stop',
          label: t('common.stop') || 'Stop',
          variant: 'outlined' as const,
          icon: <StopIcon fontSize={ICON_SIZE_SMALL} />,
          tooltip: t('common.stop') || 'Stop',
          onClick: handleStopOllama,
        })
      }

      // Restart button (when running)
      if (state === 'running' || state === 'available') {
        actions.push({
          key: 'restart',
          label: t('common.restart') || 'Restart',
          variant: 'outlined' as const,
          icon: <RestartAltIcon fontSize={ICON_SIZE_SMALL} />,
          tooltip: t('common.restart') || 'Restart',
          onClick: handleRestartOllama,
        })
      }
    }

    return actions
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
      label: 'Configure Executable',
      variant: 'outlined' as const,
      icon: <SettingsIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: 'Detect and configure executable path',
      onClick: () => {
        setExecutableConfigState({
          open: true,
          providerId,
          providerLabel: provider.label,
        })
      },
    }
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
      label: 'Advanced Diagnostics',
      variant: 'outlined' as const,
      icon: <SettingsIcon fontSize={ICON_SIZE_SMALL} />,
      tooltip: 'View advanced diagnostics',
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
  if (loading && providers.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    )
  }

  // Error state
  if (error && providers.length === 0) {
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

  // Empty state
  if (!loading && providers.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant={VARIANT_H6} gutterBottom>
          {t(K.page.providers.noProviders)}
        </Typography>
        <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
          {t(K.page.providers.createFirstProvider)}
        </Typography>
      </Box>
    )
  }

  return (
    <>
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        {providers.map((provider) => {
          const lifecycleActions = getLifecycleActions(provider)
          const viewModelsAction = getViewModelsAction(provider)
          const diagnosticsAction = getDiagnosticsAction(provider)
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
                        backgroundColor: getStateColor(provider.state) === 'success' ? '#4caf50' : getStateColor(provider.state) === 'error' ? '#f44336' : getStateColor(provider.state) === 'warning' ? '#ff9800' : '#9e9e9e',
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
                // P1-22: Ollama lifecycle controls (conditional)
                ...lifecycleActions,
                // P2-24: Detect/Configure Executable action (conditional)
                ...(detectExecutableAction ? [detectExecutableAction] : []),
                // P2-23: Diagnostics action
                diagnosticsAction,
                // P2-25: Advanced Diagnostics action (conditional)
                ...(advancedDiagnosticsAction ? [advancedDiagnosticsAction] : []),
                // P1-21: View Models action (conditional)
                ...(viewModelsAction ? [viewModelsAction] : []),
                // P0-19: Configure action
                {
                  key: 'configure',
                  label: t('common.edit'),
                  variant: 'outlined' as const,
                  icon: <EditIcon fontSize={ICON_SIZE_SMALL} />,
                  tooltip: t('common.edit'),
                  onClick: () => handleConfigure(provider),
                },
                // P1-20: Delete action
                {
                  key: 'delete',
                  label: t('common.delete') || 'Delete',
                  variant: 'outlined' as const,
                  icon: <DeleteIcon fontSize={ICON_SIZE_SMALL} />,
                  tooltip: t('common.delete') || 'Delete',
                  onClick: () => handleDeleteClick(provider),
                },
              ]}
            />
          )
        })}
      </CardCollectionWrap>

      {/* P0-18: Add Provider Wizard */}
      <AddProviderWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onSuccess={() => {
          refresh()
        }}
        availableProviders={providers.map(p => ({
          id: p.id,
          label: p.label,
          type: p.type,
          supports_models: p.supports_models,
          supports_start: p.supports_start,
          supports_auth: [] as string[],
        }))}
      />

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

      {/* P1-20: Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteState.open}
        onClose={() =>
          setDeleteState({
            open: false,
            providerId: '',
            instanceId: '',
            providerLabel: '',
            loading: false,
          })
        }
        title={t(K.page.providers.deleteTitle)}
        message={t(K.page.providers.deleteMessage, { name: deleteState.providerLabel })}
        confirmText={t(K.page.providers.deleteConfirm)}
        onConfirm={handleDeleteConfirm}
        loading={deleteState.loading}
        color="error"
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
              </ListItem>
            ))}
          </List>
        )}
      </DetailDrawer>

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
