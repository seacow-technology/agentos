/**
 * InstallUrlDialog - Install extension from URL
 *
 * Features:
 * - URL input with validation
 * - Optional SHA256 hash verification
 * - Installation progress tracking
 * - Success/error handling
 */

import { useState } from 'react'
import { DialogForm } from '@/ui/interaction'
import { Box, Typography, TextField, LinearProgress, Alert } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { skillosService } from '@/services/skillos.service'

interface InstallUrlDialogProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export function InstallUrlDialog({ open, onClose, onSuccess }: InstallUrlDialogProps) {
  const { t } = useTextTranslation()

  const [url, setUrl] = useState('')
  const [sha256, setSha256] = useState('')
  const [installing, setInstalling] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState<string>('')
  const [error, setError] = useState<string>('')

  const handleSubmit = async () => {
    if (!url.trim()) {
      toast.error(t('page.extensions.urlRequired'))
      return
    }

    // Basic URL validation
    try {
      new URL(url)
    } catch {
      toast.error('Invalid URL format')
      return
    }

    setInstalling(true)
    setError('')
    setProgress(0)
    setCurrentStep('Starting installation...')

    try {
      // Start installation
      const response = await skillosService.installExtensionUrl(
        url.trim(),
        sha256.trim() || undefined
      )
      const installId = response.install_id

      // Poll installation progress
      const pollInterval = setInterval(async () => {
        try {
          const progressData = await skillosService.getInstallProgress(installId)

          setProgress(progressData.progress)
          if (progressData.current_step) {
            setCurrentStep(progressData.current_step)
          }

          if (progressData.status === 'COMPLETED') {
            clearInterval(pollInterval)
            setInstalling(false)
            toast.success(t('page.extensions.installSuccess'))
            onSuccess()
            handleCloseDialog()
          } else if (progressData.status === 'FAILED') {
            clearInterval(pollInterval)
            setInstalling(false)
            const errorMsg = progressData.error || 'Installation failed'
            setError(errorMsg)
            toast.error(t('page.extensions.installFailed') + ': ' + errorMsg)
          }
        } catch (pollError) {
          console.error('Failed to poll progress:', pollError)
          clearInterval(pollInterval)
          setInstalling(false)
          setError('Failed to check installation progress')
        }
      }, 1000) // Poll every second

      // Timeout after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval)
        if (installing) {
          setInstalling(false)
          setError('Installation timeout')
          toast.error('Installation took too long')
        }
      }, 300000)

    } catch (err: any) {
      console.error('Install failed:', err)
      setInstalling(false)
      const errorMsg = err?.message || 'Installation failed'
      setError(errorMsg)
      toast.error(t('page.extensions.installFailed') + ': ' + errorMsg)
    }
  }

  const handleCloseDialog = () => {
    if (!installing) {
      setUrl('')
      setSha256('')
      setProgress(0)
      setCurrentStep('')
      setError('')
      onClose()
    }
  }

  return (
    <DialogForm
      open={open}
      onClose={handleCloseDialog}
      title={t(K.page.extensions.installUrlDialogTitle)}
      submitText={t(K.common.install)}
      cancelText={t(K.common.cancel)}
      onSubmit={handleSubmit}
      loading={installing}
      submitDisabled={!url.trim() || installing}
      maxWidth="sm"
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Description */}
        <Typography variant="body2" color="text.secondary">
          {t(K.page.extensions.installUrlDialogDesc)}
        </Typography>

        {/* URL Input */}
        <TextField
          label={t(K.page.extensions.extensionUrl)}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t(K.page.extensions.installUrlPlaceholder)}
          required
          fullWidth
          disabled={installing}
          autoFocus
        />

        {/* SHA256 Input (Optional) */}
        <TextField
          label={t(K.page.extensions.sha256Optional)}
          value={sha256}
          onChange={(e) => setSha256(e.target.value)}
          placeholder={t(K.page.extensions.installUrlChecksumPlaceholder)}
          fullWidth
          disabled={installing}
          helperText={t(K.page.extensions.installUrlChecksumHelper)}
        />

        {/* Progress */}
        {installing && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {currentStep || t(K.page.extensions.installing)}
            </Typography>
            <LinearProgress variant="determinate" value={progress} />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
              {progress}%
            </Typography>
          </Box>
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
