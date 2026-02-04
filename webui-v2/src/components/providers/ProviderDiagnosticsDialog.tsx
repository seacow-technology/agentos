/**
 * ProviderDiagnosticsDialog - Provider diagnostics panel
 *
 * Displays comprehensive diagnostic information for a provider:
 * - Platform and system info
 * - Executable detection status
 * - Version information
 * - Process status
 * - Configuration details
 */

import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  CircularProgress,
  Divider,
  Alert,
  List,
  ListItem,
  ListItemText,
} from '@/ui'
import { IconButton } from '@mui/material'
import { CloseIcon, RefreshIcon, CopyIcon } from '@/ui/icons'
import { providersApi, type ProviderDiagnosticsResponse } from '@/api/providers'
import { toast } from '@/ui/feedback'
import { K, useTextTranslation } from '@/ui/text'

interface ProviderDiagnosticsDialogProps {
  open: boolean
  onClose: () => void
  providerId: string
  providerLabel: string
}

export function ProviderDiagnosticsDialog({
  open,
  onClose,
  providerId,
  providerLabel,
}: ProviderDiagnosticsDialogProps) {
  const { t } = useTextTranslation()
  const [loading, setLoading] = useState(false)
  const [diagnostics, setDiagnostics] = useState<ProviderDiagnosticsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadDiagnostics = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await providersApi.getDiagnostics(providerId)
      setDiagnostics(data)
    } catch (err) {
      const message = err instanceof Error ? err.message : t(K.page.providers.failedLoadDiagnostics)
      setError(message)
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      loadDiagnostics()
    }
  }, [open, providerId])

  const handleCopyDiagnostics = async () => {
    if (!diagnostics) return

    const markdown = `## ${t(K.page.providers.diagnosticsDialogTitle, { provider: providerLabel })}

- **${t(K.page.providers.diagnosticsPlatformLabel)}**: ${diagnostics.platform}
- **${t(K.page.providers.diagnosticsDetectedPathLabel)}**: ${diagnostics.detected_executable || t(K.page.providers.diagnosticsValueNotFound)}
- **${t(K.page.providers.diagnosticsConfiguredPathLabel)}**: ${diagnostics.configured_executable || t(K.page.providers.diagnosticsValueAuto)}
- **${t(K.page.providers.diagnosticsResolvedPathLabel)}**: ${diagnostics.resolved_executable || t(K.page.providers.diagnosticsValueNotResolved)}
- **${t(K.page.providers.diagnosticsDetectionSourceLabel)}**: ${diagnostics.detection_source || t(K.page.providers.diagnosticsValueDash)}
- **${t(K.page.providers.diagnosticsVersionLabel)}**: ${diagnostics.version || t(K.page.providers.diagnosticsValueUnknown)}
- **${t(K.page.providers.diagnosticsSupportedActionsLabel)}**: ${diagnostics.supported_actions.join(', ') || t(K.page.providers.diagnosticsValueNone)}
- **${t(K.page.providers.diagnosticsStatusLabel)}**: ${diagnostics.current_status || t(K.page.providers.diagnosticsValueUnknown)}
- **${t(K.page.providers.diagnosticsPidLabel)}**: ${diagnostics.pid || t(K.page.providers.diagnosticsValueNA)}
- **${t(K.page.providers.diagnosticsPortLabel)}**: ${diagnostics.port || t(K.page.providers.diagnosticsValueNA)}
- **${t(K.page.providers.diagnosticsPortListeningLabel)}**: ${diagnostics.port_listening ?? t(K.page.providers.diagnosticsValueNA)}
- **${t(K.page.providers.diagnosticsModelsDirectoryLabel)}**: ${diagnostics.models_directory || t(K.page.providers.diagnosticsValueNA)}
- **${t(K.page.providers.diagnosticsModelsCountLabel)}**: ${diagnostics.models_count ?? t(K.page.providers.diagnosticsValueNA)}
- **${t(K.page.providers.diagnosticsErrorLabel)}**: ${diagnostics.last_error || t(K.page.providers.diagnosticsValueNone)}
`

    try {
      await navigator.clipboard.writeText(markdown)
      toast.success(t(K.page.providers.diagnosticsCopied))
    } catch (err) {
      toast.error(t(K.page.providers.diagnosticsCopyFailed))
    }
  }

  const getStatusColor = (status: string | null): 'success' | 'error' | 'warning' | 'info' => {
    if (!status) return 'info'
    const statusLower = status.toLowerCase()
    if (statusLower === 'running') return 'success'
    if (statusLower === 'stopped') return 'warning'
    if (statusLower === 'error') return 'error'
    return 'info'
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="h6">
              {t(K.page.providers.diagnosticsDialogTitle, { provider: providerLabel })}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {providerId}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <IconButton onClick={loadDiagnostics} size="small" disabled={loading}>
              <RefreshIcon />
            </IconButton>
            <IconButton onClick={handleCopyDiagnostics} size="small" disabled={!diagnostics}>
              <CopyIcon />
            </IconButton>
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {error && !loading && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {diagnostics && !loading && (
          <Box>
            {/* Status Section */}
            {diagnostics.current_status && (
              <Box sx={{ mb: 3 }}>
                <Alert severity={getStatusColor(diagnostics.current_status)}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {t(K.page.providers.diagnosticsStatusLabel)}: {diagnostics.current_status}
                  </Typography>
                  {diagnostics.last_error && (
                    <Typography variant="caption" color="error">
                      {t(K.page.providers.diagnosticsErrorLabel)}: {diagnostics.last_error}
                    </Typography>
                  )}
                </Alert>
              </Box>
            )}

            {/* System Information */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                {t(K.page.providers.diagnosticsSystemInfoTitle)}
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsPlatformLabel)}
                    secondary={diagnostics.platform}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsVersionLabel)}
                    secondary={diagnostics.version || t(K.page.providers.diagnosticsValueUnknown)}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsSupportedActionsLabel)}
                    secondary={diagnostics.supported_actions.join(', ') || t(K.page.providers.diagnosticsValueNone)}
                  />
                </ListItem>
              </List>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Executable Paths */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                {t(K.page.providers.diagnosticsExecutableConfigTitle)}
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsDetectedPathLabel)}
                    secondary={diagnostics.detected_executable || t(K.page.providers.diagnosticsValueDash)}
                    secondaryTypographyProps={{
                      sx: { fontFamily: 'monospace', fontSize: '0.75rem' },
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsConfiguredPathLabel)}
                    secondary={diagnostics.configured_executable || t(K.page.providers.diagnosticsValueAuto)}
                    secondaryTypographyProps={{
                      sx: { fontFamily: 'monospace', fontSize: '0.75rem' },
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsResolvedPathLabel)}
                    secondary={diagnostics.resolved_executable || t(K.page.providers.diagnosticsValueNotResolved)}
                    secondaryTypographyProps={{
                      sx: { fontFamily: 'monospace', fontSize: '0.75rem' },
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsDetectionSourceLabel)}
                    secondary={diagnostics.detection_source || t(K.page.providers.diagnosticsValueDash)}
                  />
                </ListItem>
              </List>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Process Information */}
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                {t(K.page.providers.diagnosticsProcessInfoTitle)}
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsPidLabel)}
                    secondary={diagnostics.pid ?? t(K.page.providers.diagnosticsValueNA)}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsPortLabel)}
                    secondary={diagnostics.port ?? t(K.page.providers.diagnosticsValueNA)}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsPortListeningLabel)}
                    secondary={
                      diagnostics.port_listening === null
                        ? t(K.page.providers.diagnosticsValueNA)
                        : diagnostics.port_listening
                        ? t(K.common.yes)
                        : t(K.common.no)
                    }
                  />
                </ListItem>
              </List>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Models Information */}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                {t(K.page.providers.diagnosticsModelsConfigTitle)}
              </Typography>
              <List dense>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsModelsDirectoryLabel)}
                    secondary={diagnostics.models_directory || t(K.page.providers.diagnosticsValueNA)}
                    secondaryTypographyProps={{
                      sx: { fontFamily: 'monospace', fontSize: '0.75rem' },
                    }}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary={t(K.page.providers.diagnosticsModelsCountLabel)}
                    secondary={diagnostics.models_count ?? t(K.page.providers.diagnosticsValueNA)}
                  />
                </ListItem>
              </List>
            </Box>
          </Box>
        )}

        {!loading && !error && !diagnostics && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              {t(K.page.providers.diagnosticsNoData)}
            </Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  )
}
