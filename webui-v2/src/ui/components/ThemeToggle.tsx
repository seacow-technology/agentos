/**
 * ThemeToggle - Theme Mode Selector
 *
 * 🎨 Design Principles:
 * - Dropdown menu for theme selection
 * - Visual feedback for current theme
 * - i18n support
 * - Support multiple themes (Light/Dark/GitHub)
 */

import { useState } from 'react'
import { IconButton, Tooltip, Menu, MenuItem, ListItemIcon, ListItemText, Divider } from '@mui/material'
import {
  Brightness4 as DarkIcon,
  Brightness7 as LightIcon,
  Code as CodeIcon,
  Palette as PaletteIcon,
  Check as CheckIcon,
  Apple as AppleIcon,
  Google as GoogleIcon,
  Nightlight as NightIcon,
  AcUnit as AcUnitIcon,
} from '@mui/icons-material'
import { K, useTextTranslation } from '@/ui/text'

type ThemeMode = 'light' | 'dark' | 'github' | 'google' | 'macos' | 'dracula' | 'nord' | 'monokai'

export interface ThemeToggleProps {
  /**
   * Current theme mode
   */
  mode: ThemeMode
  /**
   * Callback when theme changes
   */
  onToggle: () => void
  /**
   * Callback to set specific theme
   */
  onSetTheme: (mode: ThemeMode) => void
}

/**
 * ThemeToggle Component
 *
 * Displays a dropdown menu to select theme
 */
export function ThemeToggle({ mode, onSetTheme }: ThemeToggleProps) {
  const { t } = useTextTranslation()
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleSelectTheme = (selectedMode: ThemeMode) => {
    onSetTheme(selectedMode)
    handleClose()
  }

  // 主题配置
  const themeConfig: Record<ThemeMode, { icon: JSX.Element; label: string; isDark: boolean }> = {
    light: { icon: <LightIcon fontSize="small" />, label: t(K.appBar.themeLight), isDark: false },
    dark: { icon: <DarkIcon fontSize="small" />, label: t(K.appBar.themeDark), isDark: true },
    github: { icon: <CodeIcon fontSize="small" />, label: t(K.appBar.themeGithub), isDark: false },
    google: { icon: <GoogleIcon fontSize="small" />, label: t(K.appBar.themeGoogle), isDark: false },
    macos: { icon: <AppleIcon fontSize="small" />, label: t(K.appBar.themeMacos), isDark: false },
    dracula: { icon: <NightIcon fontSize="small" />, label: t(K.appBar.themeDracula), isDark: true },
    nord: { icon: <AcUnitIcon fontSize="small" />, label: t(K.appBar.themeNord), isDark: true },
    monokai: { icon: <PaletteIcon fontSize="small" />, label: t(K.appBar.themeMonokai), isDark: true },
  }

  // 根据当前主题显示对应图标
  const getCurrentIcon = () => {
    return themeConfig[mode]?.icon || <PaletteIcon />
  }

  return (
    <>
      <Tooltip title={t(K.appBar.toggleTheme)}>
        <IconButton
          onClick={handleClick}
          color="inherit"
          aria-label={t(K.appBar.toggleTheme)}
          aria-controls={open ? 'theme-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          {getCurrentIcon()}
        </IconButton>
      </Tooltip>

      <Menu
        id="theme-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'theme-button',
        }}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        sx={{
          zIndex: (theme) => theme.zIndex.modal + 1, // 确保显示在 PageHeader 和其他元素之上
        }}
      >
        {/* 浅色主题组 */}
        {(['light', 'github', 'google', 'macos'] as ThemeMode[]).map((themeMode) => (
          <MenuItem key={themeMode} onClick={() => handleSelectTheme(themeMode)}>
            <ListItemIcon>
              {themeConfig[themeMode].icon}
            </ListItemIcon>
            <ListItemText>{themeConfig[themeMode].label}</ListItemText>
            {mode === themeMode && (
              <CheckIcon fontSize="small" sx={{ ml: 2, color: 'primary.main' }} />
            )}
          </MenuItem>
        ))}

        <Divider sx={{ my: 0.5 }} />

        {/* 暗色主题组 */}
        {(['dark', 'dracula', 'nord', 'monokai'] as ThemeMode[]).map((themeMode) => (
          <MenuItem key={themeMode} onClick={() => handleSelectTheme(themeMode)}>
            <ListItemIcon>
              {themeConfig[themeMode].icon}
            </ListItemIcon>
            <ListItemText>{themeConfig[themeMode].label}</ListItemText>
            {mode === themeMode && (
              <CheckIcon fontSize="small" sx={{ ml: 2, color: 'primary.main' }} />
            )}
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}
