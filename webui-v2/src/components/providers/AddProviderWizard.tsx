/**
 * AddProviderWizard - Multi-step provider setup wizard
 *
 * P0-18: Implements provider creation flow
 *
 * Steps:
 * 1. Select provider type
 * 2. Configure connection details
 * 3. Confirm and create
 */

import { useState } from 'react'
import {
  Box,
  TextField,
  Typography,
  FormControlLabel,
  Switch,
  Grid,
  RadioGroup,
  Radio,
  FormControl,
  FormLabel,
} from '@mui/material'
import { DialogForm } from '@/ui/interaction/DialogForm'
import { K, useTextTranslation } from '@/ui/text'
import { providersApi, type InstanceConfigRequest, type ProviderInfo } from '@/api/providers'

interface AddProviderWizardProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  availableProviders: ProviderInfo[]
}

interface ProviderFormData {
  providerId: string
  instanceId: string
  baseUrl: string
  enabled: boolean
}

/**
 * AddProviderWizard Component
 *
 * P0-18: Multi-step wizard for provider setup
 * Uses DialogForm for consistent styling
 */
export function AddProviderWizard({
  open,
  onClose,
  onSuccess,
  availableProviders,
}: AddProviderWizardProps) {
  const { t } = useTextTranslation()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState<ProviderFormData>({
    providerId: '',
    instanceId: '',
    baseUrl: '',
    enabled: true,
  })

  // Reset form on close
  const handleClose = () => {
    setFormData({
      providerId: '',
      instanceId: '',
      baseUrl: '',
      enabled: true,
    })
    setError(null)
    onClose()
  }

  // Handle form submission
  const handleSubmit = async () => {
    try {
      setLoading(true)
      setError(null)

      // Validate required fields
      if (!formData.providerId) {
        setError(t(K.page.providers.validationSelectType))
        return
      }
      if (!formData.instanceId) {
        setError(t(K.page.providers.validationInstanceId))
        return
      }
      if (!formData.baseUrl) {
        setError(t(K.page.providers.validationBaseUrl))
        return
      }

      // Create instance config
      const config: InstanceConfigRequest = {
        instance_id: formData.instanceId,
        base_url: formData.baseUrl,
        enabled: formData.enabled,
      }

      // Call API
      await providersApi.createInstance(formData.providerId, config)

      // Success
      onSuccess()
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : t(K.page.providers.createFailed))
    } finally {
      setLoading(false)
    }
  }

  // Get local providers for selection
  const localProviders = availableProviders.filter((p) => p.type === 'local')

  return (
    <DialogForm
      open={open}
      onClose={handleClose}
      title={t(K.page.providers.addProvider)}
      submitText={t(K.common.create)}
      cancelText={t(K.common.cancel)}
      onSubmit={handleSubmit}
      loading={loading}
      submitDisabled={!formData.providerId || !formData.instanceId || !formData.baseUrl}
      maxWidth="sm"
    >
      <Grid container spacing={3}>
        {/* Error display */}
        {error && (
          <Grid item xs={12}>
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
          </Grid>
        )}

        {/* Step 1: Select Provider Type */}
        <Grid item xs={12}>
          <FormControl component="fieldset" fullWidth>
            <FormLabel component="legend">
              <Typography variant="subtitle2" gutterBottom>
                {t(K.page.providers.columnType)}
              </Typography>
            </FormLabel>
            <RadioGroup
              value={formData.providerId}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, providerId: e.target.value }))
              }
            >
              {localProviders.map((provider) => (
                <FormControlLabel
                  key={provider.id}
                  value={provider.id}
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body1">{provider.label}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {provider.id}
                      </Typography>
                    </Box>
                  }
                />
              ))}
            </RadioGroup>
          </FormControl>
        </Grid>

        {/* Step 2: Configure Instance */}
        {formData.providerId && (
          <>
            <Grid item xs={12}>
              <TextField
                label={t(K.page.providers.columnId)}
                fullWidth
                required
                value={formData.instanceId}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, instanceId: e.target.value }))
                }
                placeholder={t(K.page.providers.instanceIdPlaceholder)}
                helperText={t(K.page.providers.instanceIdHelper)}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                label={t(K.page.providers.columnApiEndpoint)}
                fullWidth
                required
                value={formData.baseUrl}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, baseUrl: e.target.value }))
                }
                placeholder={t(K.page.providers.baseUrlPlaceholder)}
                helperText={t(K.page.providers.baseUrlHelper)}
              />
            </Grid>

            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.enabled}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, enabled: e.target.checked }))
                    }
                  />
                }
                label={t(K.form.field.enabled)}
              />
            </Grid>
          </>
        )}
      </Grid>
    </DialogForm>
  )
}
