/**
 * ConfigureExtensionDialog - Configure extension settings
 *
 * Features:
 * - Load current configuration
 * - JSON editor with validation
 * - Save configuration
 * - Error handling
 */

import { useState, useEffect } from 'react'
import { DialogForm } from '@/ui/interaction'
import { Box, Typography, TextField, Alert, CircularProgress } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { skillosService } from '@/services/skillos.service'

interface ConfigureExtensionDialogProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
  extensionId: string
  extensionName: string
}

export function ConfigureExtensionDialog({
  open,
  onClose,
  onSuccess,
  extensionId,
  extensionName
}: ConfigureExtensionDialogProps) {
  const { t } = useTextTranslation()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [configText, setConfigText] = useState('')
  const [error, setError] = useState<string>('')
  const [jsonError, setJsonError] = useState<string>('')

  // Load configuration when dialog opens
  useEffect(() => {
    if (open && extensionId) {
      loadConfig()
    }
  }, [open, extensionId])

  const loadConfig = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await skillosService.getExtensionConfig(extensionId)
      const config = response.config || {}
      setConfigText(JSON.stringify(config, null, 2))
    } catch (err: any) {
      console.error('Failed to load config:', err)
      const errorMsg = err?.message || 'Failed to load configuration'
      setError(errorMsg)
      setConfigText('{}')
    } finally {
      setLoading(false)
    }
  }

  const handleConfigChange = (value: string) => {
    setConfigText(value)
    setJsonError('')

    // Validate JSON
    if (value.trim()) {
      try {
        JSON.parse(value)
      } catch (e: any) {
        setJsonError(e.message)
      }
    }
  }

  const handleSubmit = async () => {
    // Validate JSON
    let parsedConfig: Record<string, unknown>
    try {
      parsedConfig = JSON.parse(configText)
    } catch (e: any) {
      toast.error(t('page.extensions.invalidJson') + ': ' + e.message)
      return
    }

    setSaving(true)
    setError('')

    try {
      await skillosService.updateExtensionConfig(extensionId, parsedConfig)
      toast.success(t('page.extensions.configureSuccess'))
      onSuccess()
      handleCloseDialog()
    } catch (err: any) {
      console.error('Failed to save config:', err)
      const errorMsg = err?.message || 'Failed to save configuration'
      setError(errorMsg)
      toast.error(t('page.extensions.configureFailed') + ': ' + errorMsg)
    } finally {
      setSaving(false)
    }
  }

  const handleCloseDialog = () => {
    if (!loading && !saving) {
      setConfigText('')
      setError('')
      setJsonError('')
      onClose()
    }
  }

  return (
    <DialogForm
      open={open}
      onClose={handleCloseDialog}
      title={`${t(K.page.extensions.configureDialogTitle)} - ${extensionName}`}
      submitText={t(K.common.save)}
      cancelText={t(K.common.cancel)}
      onSubmit={handleSubmit}
      loading={saving}
      submitDisabled={loading || saving || !!jsonError}
      maxWidth="md"
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Description */}
        <Typography variant="body2" color="text.secondary">
          {t(K.page.extensions.configureDialogDesc)}
        </Typography>

        {/* Loading State */}
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {/* JSON Editor */}
        {!loading && (
          <>
            <TextField
              label={t(K.page.extensions.configuration)}
              value={configText}
              onChange={(e) => handleConfigChange(e.target.value)}
              multiline
              rows={12}
              fullWidth
              disabled={saving}
              error={!!jsonError}
              helperText={jsonError || 'Enter configuration as JSON'}
              sx={{
                '& .MuiInputBase-input': {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                }
              }}
            />

            {/* Info */}
            <Alert severity="info">
              Note: Sensitive values (keys, secrets, passwords) are masked with "***" when loaded.
              You can update them by entering new values.
            </Alert>
          </>
        )}

        {/* Error */}
        {error && (
          <Alert
            severity="error"
            sx={{
              '& .MuiAlert-message': {
                width: '100%',
                wordBreak: 'break-word',
                cursor: 'pointer'
              }
            }}
            onClick={() => {
              navigator.clipboard.writeText(error)
              toast.success('Error copied to clipboard')
            }}
          >
            {error}
          </Alert>
        )}
      </Box>
    </DialogForm>
  )
}
