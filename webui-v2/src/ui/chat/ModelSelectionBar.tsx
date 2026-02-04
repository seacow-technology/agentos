/**
 * ModelSelectionBar - Model Selection and Control Bar
 *
 * 位于消息区域和输入框之间的控制栏
 *
 * Features:
 * - Left: Local/Cloud toggle + Provider + Model selection
 * - Right: Empty button
 */

import { Box, ToggleButtonGroup, ToggleButton, Select, MenuItem, Button, FormControl, InputLabel } from '@mui/material'
import {
  Computer as ComputerIcon,
  Cloud as CloudIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material'
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

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        py: 2,
        my: 2,
        gap: 2,
      }}
    >
      {/* Left: Model Selection */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
        {/* Local/Cloud Toggle */}
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
        >
          <ToggleButton value="local" sx={{ px: 2 }}>
            <ComputerIcon sx={{ mr: 0.5, fontSize: 18 }} />
            {t('page.chat.modeLocal')}
          </ToggleButton>
          <ToggleButton value="cloud" sx={{ px: 2 }}>
            <CloudIcon sx={{ mr: 0.5, fontSize: 18 }} />
            {t('page.chat.modeCloud')}
          </ToggleButton>
        </ToggleButtonGroup>

        {/* Provider Select */}
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>{t('page.chat.provider')}</InputLabel>
          <Select
            value={provider}
            label={t('page.chat.provider')}
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

        {/* Model Select */}
        <FormControl size="small" sx={{ minWidth: 280, flex: 1 }}>
          <InputLabel>{t('page.chat.model')}</InputLabel>
          <Select
            value={model}
            label={t('page.chat.model')}
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
      </Box>

      {/* Right: Action Buttons */}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<DeleteIcon />}
          onClick={onEmpty}
          disabled={disabled}
        >
          {t('page.chat.empty')}
        </Button>
      </Box>
    </Box>
  )
}
