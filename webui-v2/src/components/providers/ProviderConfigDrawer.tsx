/**
 * ProviderConfigDrawer - Provider configuration editor
 *
 * P0-19: Implements provider configuration editing
 *
 * Features:
 * - View current configuration
 * - Edit endpoint URL
 * - Toggle enabled state
 * - Save changes
 */

import { useState, useEffect } from 'react'
import {
  Box,
  TextField,
  Typography,
  FormControlLabel,
  Switch,
  Button,
  Divider,
} from '@mui/material'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { K, useTextTranslation } from '@/ui/text'
import { providersApi, type InstanceConfigRequest } from '@/api/providers'

interface ProviderConfigDrawerProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  providerId: string
  instanceId: string
  currentEndpoint: string
  currentEnabled: boolean
}

/**
 * ProviderConfigDrawer Component
 *
 * P0-19: Configuration editor using DetailDrawer
 */
export function ProviderConfigDrawer({
  open,
  onClose,
  onSuccess,
  providerId,
  instanceId,
  currentEndpoint,
  currentEnabled,
}: ProviderConfigDrawerProps) {
  const { t } = useTextTranslation()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [baseUrl, setBaseUrl] = useState(currentEndpoint)
  const [enabled, setEnabled] = useState(currentEnabled)

  // Reset form when props change
  useEffect(() => {
    setBaseUrl(currentEndpoint)
    setEnabled(currentEnabled)
    setError(null)
  }, [currentEndpoint, currentEnabled, open])

  // Handle save
  const handleSave = async () => {
    try {
      setLoading(true)
      setError(null)

      if (!baseUrl) {
        setError(t(K.page.providers.configBaseUrlRequired))
        return
      }

      // Create update config
      const config: InstanceConfigRequest = {
        base_url: baseUrl,
        enabled: enabled,
      }

      // Call API
      await providersApi.updateInstance(providerId, instanceId, config)

      // Success
      onSuccess()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : t(K.page.providers.configUpdateFailed))
    } finally {
      setLoading(false)
    }
  }

  // Check if form has changes
  const hasChanges = baseUrl !== currentEndpoint || enabled !== currentEnabled

  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      title={t(K.page.providers.editProvider)}
      subtitle={`${providerId}:${instanceId}`}
      actions={
        <>
          <Button onClick={onClose} disabled={loading}>
            {t(K.common.cancel)}
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={loading || !hasChanges || !baseUrl}
          >
            {t(K.common.save)}
          </Button>
        </>
      }
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {/* Error display */}
        {error && (
          <Box
            sx={{
              p: 2,
              bgcolor: 'error.light',
              borderRadius: 1,
              color: 'error.contrastText',
            }}
          >
            <Typography variant="body2">{error}</Typography>
          </Box>
        )}

        {/* Provider Info */}
        <Box>
          <Typography variant="caption" color="text.secondary">
            {t(K.page.providers.columnType)}
          </Typography>
          <Typography variant="body1">{providerId}</Typography>
        </Box>

        <Divider />

        {/* Configuration Fields */}
        <Box>
          <TextField
            label={t(K.page.providers.columnApiEndpoint)}
            fullWidth
            required
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            disabled={loading}
            helperText={t(K.page.providers.baseUrlHelper)}
          />
        </Box>

        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                disabled={loading}
              />
            }
            label={t(K.form.field.enabled)}
          />
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
            {t(K.page.providers.configDisabledHint)}
          </Typography>
        </Box>

        {/* Change indicator */}
        {hasChanges && (
          <Box
            sx={{
              p: 2,
              bgcolor: 'info.light',
              borderRadius: 1,
              color: 'info.contrastText',
            }}
          >
            <Typography variant="body2">{t(K.page.providers.configUnsavedChanges)}</Typography>
          </Box>
        )}
      </Box>
    </DetailDrawer>
  )
}
