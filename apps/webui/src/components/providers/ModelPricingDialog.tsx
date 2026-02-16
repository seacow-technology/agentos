import { useEffect, useMemo, useState } from 'react'
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, TextField, Typography } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { providersApi, type ModelPricingRow } from '@/api/providers'

interface ModelPricingDialogProps {
  open: boolean
  onClose: () => void
  providerId: string
  providerLabel?: string
  modelId: string
  modelLabel?: string
  current?: ModelPricingRow | null
  onSaved: (row: ModelPricingRow | null) => void
}

export function ModelPricingDialog({
  open,
  onClose,
  providerId,
  providerLabel,
  modelId,
  modelLabel,
  current,
  onSaved,
}: ModelPricingDialogProps) {
  const { t } = useTextTranslation()
  const [saving, setSaving] = useState(false)

  const title = useMemo(() => t(K.page.providers.modelPricingTitle), [t])

  const [inputPer1m, setInputPer1m] = useState<string>('')
  const [outputPer1m, setOutputPer1m] = useState<string>('')
  const [source, setSource] = useState<string>('')

  useEffect(() => {
    if (!open) return
    setInputPer1m(current ? String(current.input_per_1m) : '')
    setOutputPer1m(current ? String(current.output_per_1m) : '')
    setSource(current?.source ? String(current.source) : '')
  }, [open, current])

  const parseNum = (v: string): number | null => {
    const n = Number(v)
    if (!Number.isFinite(n) || n < 0) return null
    return n
  }

  const handleSave = async () => {
    const inN = parseNum(inputPer1m.trim())
    const outN = parseNum(outputPer1m.trim())
    if (inN === null || outN === null) {
      toast.error(t(K.page.providers.modelPricingInvalid))
      return
    }
    try {
      setSaving(true)
      const res = await providersApi.upsertProviderModelPricing(providerId, modelId, {
        input_per_1m: inN,
        output_per_1m: outN,
        currency: 'USD',
        source: source.trim() ? source.trim() : null,
        enabled: true,
      })
      toast.success(t(K.page.providers.modelPricingSaved))
      onSaved(res.pricing)
      onClose()
    } catch (err) {
      toast.error(t(K.page.providers.modelPricingSaveFailed))
      throw err
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async () => {
    try {
      setSaving(true)
      await providersApi.deleteProviderModelPricing(providerId, modelId)
      toast.success(t(K.page.providers.modelPricingCleared))
      onSaved(null)
      onClose()
    } catch (err) {
      toast.error(t(K.page.providers.modelPricingClearFailed))
      throw err
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      sx={{
        // DetailDrawer uses theme.zIndex.modal + 2; keep pricing dialog above it.
        zIndex: (theme) => theme.zIndex.modal + 6,
      }}
    >
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {t(K.page.providers.modelPricingSubtitle, {
              provider: providerLabel || providerId,
              model: modelLabel || modelId,
            })}
          </Typography>
          <Divider />
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <TextField
              label={t(K.page.providers.modelPricingInput)}
              value={inputPer1m}
              onChange={(e) => setInputPer1m(e.target.value)}
              disabled={saving}
              helperText={t(K.page.providers.modelPricingPer1m)}
            />
            <TextField
              label={t(K.page.providers.modelPricingOutput)}
              value={outputPer1m}
              onChange={(e) => setOutputPer1m(e.target.value)}
              disabled={saving}
              helperText={t(K.page.providers.modelPricingPer1m)}
            />
          </Box>
          <TextField
            label={t(K.page.providers.modelPricingSource)}
            value={source}
            onChange={(e) => setSource(e.target.value)}
            disabled={saving}
            placeholder="manual"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        {current ? (
          <Button onClick={handleClear} disabled={saving} color="error">
            {t(K.page.providers.modelPricingClear)}
          </Button>
        ) : (
          <Box />
        )}
        <Button onClick={onClose} disabled={saving}>
          {t(K.common.cancel)}
        </Button>
        <Button variant="contained" onClick={handleSave} disabled={saving}>
          {t(K.common.save)}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
