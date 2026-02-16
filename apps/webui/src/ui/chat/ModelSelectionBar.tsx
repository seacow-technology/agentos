/**
 * ModelSelectionBar - Model Selection and Control Bar
 *
 * 位于消息区域和输入框之间的控制栏
 *
 * Features:
 * - Left: Local/Cloud toggle + Provider + Model selection
 * - Right: Empty button
 */

import { Box, Grid, ToggleButtonGroup, ToggleButton, Select, MenuItem, Button, FormControl, InputLabel } from '@mui/material'
import {
  Computer as ComputerIcon,
  Cloud as CloudIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material'
import { useId } from 'react'
import { useTextTranslation } from '@/ui/text'

export interface ModelSelectionBarProps {
  // Model Selection
  mode?: 'local' | 'cloud'
  provider?: string
  model?: string
  providers?: string[]
  models?: string[]

  // Callbacks
  onModeChange?: (mode: 'local' | 'cloud') => void
  onProviderChange?: (provider: string) => void
  onModelChange?: (model: string) => void

  // Actions
  onEmpty?: () => void

  // States
  disabled?: boolean
}

export function ModelSelectionBar({
  mode = 'local',
  provider = '',
  model = '',
  providers = [],
  models = [],
  onModeChange,
  onProviderChange,
  onModelChange,
  onEmpty,
  disabled = false,
}: ModelSelectionBarProps) {
  const { t } = useTextTranslation()
  const selectIdBase = useId()

  return (
    <Box
      sx={{
        px: 2,
        py: 2,
        my: 2,
      }}
    >
      {/* 4-column Grid contract at desktop widths: toggle / provider / model / actions */}
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={12} md="auto">
          <ToggleButtonGroup
            value={mode}
            exclusive
            onChange={(_, newMode) => {
              if (newMode && onModeChange) {
                onModeChange(newMode)
              }
            }}
            size="small"
            disabled={disabled}
            sx={{ flexWrap: 'nowrap' }}
          >
            <ToggleButton value="local" sx={{ px: 2, minWidth: 120, whiteSpace: 'nowrap' }}>
              <ComputerIcon sx={{ mr: 0.5, fontSize: 18 }} />
              {t('page.chat.modeLocal')}
            </ToggleButton>
            <ToggleButton value="cloud" sx={{ px: 2, minWidth: 120, whiteSpace: 'nowrap' }}>
              <CloudIcon sx={{ mr: 0.5, fontSize: 18 }} />
              {t('page.chat.modeCloud')}
            </ToggleButton>
          </ToggleButtonGroup>
        </Grid>

        <Grid item xs={12} md={3}>
          <FormControl size="small" fullWidth>
            <InputLabel id={`${selectIdBase}-chat-provider-label`}>{t('page.chat.provider')}</InputLabel>
            <Select
              value={provider}
              label={t('page.chat.provider')}
              labelId={`${selectIdBase}-chat-provider-label`}
              id={`${selectIdBase}-chat-provider`}
              onChange={(e) => onProviderChange?.(e.target.value)}
              disabled={disabled}
            >
              {providers.length === 0 ? (
                <MenuItem value="">
                  <em>{t('page.chat.noProviders')}</em>
                </MenuItem>
              ) : (
                providers.map((p) => (
                  <MenuItem key={p} value={p}>
                    {p}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} md>
          <FormControl size="small" fullWidth>
            <InputLabel id={`${selectIdBase}-chat-model-label`}>{t('page.chat.model')}</InputLabel>
            <Select
              value={model}
              label={t('page.chat.model')}
              labelId={`${selectIdBase}-chat-model-label`}
              id={`${selectIdBase}-chat-model`}
              onChange={(e) => onModelChange?.(e.target.value)}
              disabled={disabled || !provider}
            >
              {models.length === 0 ? (
                <MenuItem value="">
                  <em>{t('page.chat.noModels')}</em>
                </MenuItem>
              ) : (
                models.map((m) => (
                  <MenuItem key={m} value={m}>
                    {m}
                  </MenuItem>
                ))
              )}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} md="auto">
          <Box sx={{ display: 'flex', justifyContent: { xs: 'flex-start', md: 'flex-end' } }}>
            <Button
              size="small"
              variant="outlined"
              startIcon={<DeleteIcon />}
              onClick={onEmpty}
              disabled={disabled}
              sx={{ minWidth: 120, whiteSpace: 'nowrap' }}
            >
              {t('page.chat.empty')}
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  )
}
