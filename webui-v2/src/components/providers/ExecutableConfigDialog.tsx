/**
 * ExecutableConfigDialog - Configure provider executable path
 *
 * Features:
 * - Auto-detect executable path
 * - Validate custom executable path
 * - Save configuration
 * - Show detection details
 */

import { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  TextField,
  Button,
  CircularProgress,
  Alert,
  List,
  ListItem,
  ListItemText,
} from '@/ui'
import { IconButton } from '@mui/material'
import { CloseIcon, SearchIcon, CheckCircleIcon, WarningIcon } from '@/ui/icons'
import { providersApi, type DetectExecutableResponse, type ValidateExecutableResponse } from '@/api/providers'
import { toast } from '@/ui/feedback'
import { K, useTextTranslation } from '@/ui/text'

interface ExecutableConfigDialogProps {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
  providerId: string
  providerLabel: string
}

export function ExecutableConfigDialog({
  open,
  onClose,
  onSuccess,
  providerId,
  providerLabel,
}: ExecutableConfigDialogProps) {
  const { t } = useTextTranslation()
  const [customPath, setCustomPath] = useState('')
  const [detecting, setDetecting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [detectResult, setDetectResult] = useState<DetectExecutableResponse | null>(null)
  const [validateResult, setValidateResult] = useState<ValidateExecutableResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleDetect = async () => {
    setDetecting(true)
    setError(null)
    setValidateResult(null)
    try {
      const result = await providersApi.detectExecutable(providerId)
      setDetectResult(result)

      if (result.detected && result.resolved_path) {
        toast.success(t(K.page.providers.executableDetectedToast, {
          provider: providerLabel,
          path: result.resolved_path,
        }))
        // Auto-fill the custom path with detected path
        setCustomPath(result.resolved_path)
      } else {
        toast.warning(t(K.page.providers.executableNotFoundToast, { provider: providerLabel }))
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t(K.page.providers.executableDetectFailed)
      setError(message)
      toast.error(message)
    } finally {
      setDetecting(false)
    }
  }

  const handleValidate = async () => {
    if (!customPath.trim()) {
      toast.warning(t(K.page.providers.executableValidateMissingPath))
      return
    }

    setValidating(true)
    setError(null)
    try {
      const result = await providersApi.validateExecutable(providerId, customPath.trim())
      setValidateResult(result)

      if (result.is_valid) {
        toast.success(t(K.page.providers.executableValidateSuccess))
      } else {
        toast.error(result.error || t(K.page.providers.executableInvalid))
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t(K.page.providers.executableValidateFailed)
      setError(message)
      toast.error(message)
    } finally {
      setValidating(false)
    }
  }

  const handleSave = async () => {
    // Validate before saving
    if (customPath.trim()) {
      if (!validateResult || !validateResult.is_valid) {
        toast.error(t(K.page.providers.executableValidateBeforeSave))
        return
      }
    }

    setSaving(true)
    setError(null)
    try {
      const pathToSave = customPath.trim() || null
      await providersApi.setExecutablePath(providerId, pathToSave, !pathToSave)

      toast.success(t(K.page.providers.executableSaveSuccess))
      onSuccess?.()
      handleClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : t(K.page.providers.executableSaveFailed)
      setError(message)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  const handleClose = () => {
    setCustomPath('')
    setDetectResult(null)
    setValidateResult(null)
    setError(null)
    onClose()
  }

  const getSourceLabel = (source: string | null) => {
    if (!source) return t(K.page.providers.executableSourceUnknown)
    const labels: Record<string, string> = {
      config: t(K.page.providers.executableSourceUserConfig),
      standard: t(K.page.providers.executableSourceStandard),
      path: t(K.page.providers.executableSourcePath),
    }
    return labels[source] || source
  }

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">
            {t(K.page.providers.executableDialogTitle, { provider: providerLabel })}
          </Typography>
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Auto-detect Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            {t(K.page.providers.executableAutoDetectTitle)}
          </Typography>
          <Button
            variant="outlined"
            startIcon={detecting ? <CircularProgress size={16} /> : <SearchIcon />}
            onClick={handleDetect}
            disabled={detecting}
            fullWidth
          >
            {detecting ? t(K.page.providers.executableDetecting) : t(K.page.providers.executableDetectButton)}
          </Button>

          {detectResult && (
            <Box sx={{ mt: 2 }}>
              {detectResult.detected ? (
                <Alert severity="success" icon={<CheckCircleIcon />}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {t(K.page.providers.executableFoundTitle)}
                  </Typography>
                  <List dense>
                    <ListItem disablePadding>
                      <ListItemText
                        primary={t(K.page.providers.executablePathLabel)}
                        secondary={detectResult.resolved_path}
                        secondaryTypographyProps={{
                          sx: { fontFamily: 'monospace', fontSize: '0.75rem' },
                        }}
                      />
                    </ListItem>
                    <ListItem disablePadding>
                      <ListItemText
                        primary={t(K.page.providers.executableSourceLabel)}
                        secondary={getSourceLabel(detectResult.detection_source)}
                      />
                    </ListItem>
                    {detectResult.version && (
                      <ListItem disablePadding>
                        <ListItemText
                          primary={t(K.page.providers.executableVersionLabel)}
                          secondary={detectResult.version}
                        />
                      </ListItem>
                    )}
                  </List>
                </Alert>
              ) : (
                <Alert severity="warning" icon={<WarningIcon />}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {t(K.page.providers.executableNotFoundTitle)}
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                    {t(K.page.providers.executableSearchedPathsLabel)}
                  </Typography>
                  <List dense>
                    {detectResult.search_paths.map((path, index) => (
                      <ListItem key={index} disablePadding>
                        <Typography
                          variant="caption"
                          sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}
                        >
                          • {path}
                        </Typography>
                      </ListItem>
                    ))}
                  </List>
                </Alert>
              )}
            </Box>
          )}
        </Box>

        {/* Custom Path Section */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            {t(K.page.providers.executableCustomPathTitle)}
          </Typography>
          <TextField
            fullWidth
            placeholder={t(K.page.providers.executableCustomPathPlaceholder)}
            value={customPath}
            onChange={(e) => {
              setCustomPath(e.target.value)
              setValidateResult(null) // Reset validation when path changes
            }}
            disabled={validating || saving}
            sx={{ mb: 1 }}
          />
          <Button
            variant="outlined"
            startIcon={validating ? <CircularProgress size={16} /> : <CheckCircleIcon />}
            onClick={handleValidate}
            disabled={!customPath.trim() || validating || saving}
            fullWidth
          >
            {validating ? t(K.page.providers.executableValidating) : t(K.page.providers.executableValidateButton)}
          </Button>

          {validateResult && (
            <Box sx={{ mt: 2 }}>
              {validateResult.is_valid ? (
                <Alert severity="success">
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {t(K.page.providers.executableValidTitle)}
                  </Typography>
                  {validateResult.version && (
                    <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                      {t(K.page.providers.executableVersionLabel)}: {validateResult.version}
                    </Typography>
                  )}
                </Alert>
              ) : (
                <Alert severity="error">
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {t(K.page.providers.executableInvalidTitle)}
                  </Typography>
                  <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                    {validateResult.error || t(K.page.providers.executableUnknownError)}
                  </Typography>
                  <List dense sx={{ mt: 1 }}>
                    <ListItem disablePadding>
                      <Typography variant="caption">
                        • {t(K.page.providers.executableFileExistsLabel)}: {validateResult.exists ? t(K.common.yes) : t(K.common.no)}
                      </Typography>
                    </ListItem>
                    <ListItem disablePadding>
                      <Typography variant="caption">
                        • {t(K.page.providers.executableIsExecutableLabel)}: {validateResult.is_executable ? t(K.common.yes) : t(K.common.no)}
                      </Typography>
                    </ListItem>
                  </List>
                </Alert>
              )}
            </Box>
          )}
        </Box>

        {/* Information */}
        <Alert severity="info">
          <Typography variant="caption">
            <strong>{t(K.page.providers.executableTipTitle)}:</strong>{' '}
            {t(K.page.providers.executableTipMessage)}
          </Typography>
        </Alert>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={saving}>
          {t(K.common.cancel)}
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || (customPath.trim() !== '' && !validateResult?.is_valid)}
        >
          {saving ? t(K.page.providers.executableSaving) : t(K.page.providers.executableSaveConfig)}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
