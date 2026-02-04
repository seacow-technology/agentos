import { IconButton, Menu, MenuItem, Tooltip } from '@mui/material'
import { LanguageIcon } from '@/ui/icons'
import { useState } from 'react'
import { useTranslation } from '../i18n/useTranslation'
import { K, useTextTranslation } from '@/ui/text'
import type { Language } from '../i18n'

/**
 * LanguageSwitcher - Component for switching application language
 *
 * Features:
 * - Dropdown menu with language options
 * - Persists selection to localStorage
 * - Updates all components using i18n
 *
 * Usage:
 *   <LanguageSwitcher />
 */
export function LanguageSwitcher() {
  const { i18n } = useTranslation()
  const { t } = useTextTranslation()
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const open = Boolean(anchorEl)

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  const handleLanguageChange = (lang: Language) => {
    i18n.changeLanguage(lang)
    handleClose()
  }

  const languages = [
    { code: 'en' as Language, name: t(K.common.languageEnglish), nativeName: t(K.common.languageEnglish) },
    { code: 'zh' as Language, name: t(K.common.languageChinese), nativeName: t(K.common.languageChinese) },
  ]

  const currentLanguage = languages.find(lang => lang.code === i18n.language) || languages[0]

  return (
    <>
      <Tooltip title={t(K.common.languageLabel, { language: currentLanguage.nativeName })}>
        <IconButton
          onClick={handleClick}
          size="small"
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
      >
        {languages.map((lang) => (
          <MenuItem
            key={lang.code}
            onClick={() => handleLanguageChange(lang.code)}
            selected={lang.code === i18n.language}
          >
            {lang.nativeName} ({lang.name})
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}

export default LanguageSwitcher
