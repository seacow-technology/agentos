/**
 * LanguageSwitch - Language Selector
 *
 * 🎨 Design Principles:
 * - IconButton with Menu
 * - Show current language
 * - i18n support
 * - Support zh/en
 */

import { useState } from 'react'
import { IconButton, Tooltip, Menu, MenuItem, ListItemText, ListItemIcon } from '@mui/material'
import { Language as LanguageIcon, Check as CheckIcon } from '@mui/icons-material'
import { K, useTextTranslation } from '@/ui/text'

export interface LanguageSwitchProps {
  /**
   * Current language code
   */
  currentLanguage: string
  /**
   * Callback when language changes
   */
  onLanguageChange: (lang: string) => void
}

/**
 * LanguageSwitch Component
 *
 * Displays a language selector with menu
 */
export function LanguageSwitch({ currentLanguage, onLanguageChange }: LanguageSwitchProps) {
  const { t } = useTextTranslation()
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)
  const languages = [
    { code: 'zh', label: t(K.common.languageChinese) },
    { code: 'en', label: t(K.common.languageEnglish) },
  ]

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    // 延迟关闭，让焦点先转移
    setTimeout(() => {
      setAnchorEl(null)
    }, 0)
  }

  const handleLanguageSelect = (lang: string) => {
    onLanguageChange(lang)
    handleClose()
  }

  return (
    <>
      <Tooltip title={t(K.appBar.switchLanguage)}>
        <IconButton
          onClick={handleClick}
          color="inherit"
          aria-label={t(K.appBar.switchLanguage)}
          aria-controls={open ? 'language-menu' : undefined}
          aria-haspopup="true"
          aria-expanded={open ? 'true' : undefined}
        >
          <LanguageIcon />
        </IconButton>
      </Tooltip>
      <Menu
        id="language-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          'aria-labelledby': 'language-button',
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        sx={{
          zIndex: (theme) => theme.zIndex.modal + 1, // Ensure Menu is above PageHeader and other elements
        }}
      >
        {languages.map((lang) => (
          <MenuItem
            key={lang.code}
            onClick={() => handleLanguageSelect(lang.code)}
            selected={currentLanguage === lang.code}
          >
            <ListItemIcon>
              {currentLanguage === lang.code ? <CheckIcon fontSize="small" /> : <span style={{ width: 20 }} />}
            </ListItemIcon>
            <ListItemText>{lang.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}
