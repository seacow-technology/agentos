import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import zh from './locales/zh.json'

/**
 * i18n Configuration
 *
 * Provides internationalization support for the application
 * - English (en) as fallback language
 * - Simplified Chinese (zh) as default language
 *
 * Usage:
 *   import { t } from '@/i18n'
 *   const text = t('common.save')
 *   const textWithParams = t('validation.minLength', { min: 5 })
 */

// Define supported languages
export type Language = 'en' | 'zh'

// Store language preference in localStorage
const STORAGE_KEY = 'agentos-webui-language'

// Get saved language or default to Chinese
const getSavedLanguage = (): Language => {
  const saved = localStorage.getItem(STORAGE_KEY)
  return (saved === 'en' || saved === 'zh') ? saved : 'zh'
}

// Initialize i18next
i18next
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh }
    },
    lng: getSavedLanguage(),
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false // React already escapes values
    },
    // Enable debugging in development
    debug: import.meta.env.DEV,
    // Disable i18next promotional messages
    saveMissing: false,
    missingKeyHandler: false,
  })

/**
 * Translation function
 *
 * @param key - Translation key following the convention: domain.module.component.key
 * @param params - Optional parameters for interpolation
 * @returns Translated string
 *
 * @example
 * t('common.save') // "保存" (zh) or "Save" (en)
 * t('validation.minLength', { min: 5 }) // "最小长度为 5 个字符"
 * t('pages.lab.form.title') // "创建新任务"
 */
export const t = i18next.t.bind(i18next)

/**
 * Change the current language
 *
 * @param lang - Target language ('en' | 'zh')
 * @returns Promise that resolves when language is changed
 *
 * @example
 * await changeLanguage('en')
 */
export const changeLanguage = async (lang: Language): Promise<void> => {
  await i18next.changeLanguage(lang)
  localStorage.setItem(STORAGE_KEY, lang)
}

/**
 * Get the current active language
 *
 * @returns Current language code
 *
 * @example
 * const currentLang = getCurrentLanguage() // 'zh'
 */
export const getCurrentLanguage = (): Language => {
  return i18next.language as Language
}

/**
 * Check if a translation key exists
 *
 * @param key - Translation key to check
 * @returns true if key exists in current language or fallback
 */
export const hasTranslation = (key: string): boolean => {
  return i18next.exists(key)
}

/**
 * Listen to language change events
 *
 * @param callback - Function to call when language changes
 * @returns Cleanup function to remove listener
 *
 * @example
 * const cleanup = onLanguageChange((lang) => {
 *   console.log('Language changed to:', lang)
 * })
 * // Later: cleanup()
 */
export const onLanguageChange = (callback: (lang: Language) => void) => {
  const handler = (lng: string) => callback(lng as Language)
  i18next.on('languageChanged', handler)
  return () => i18next.off('languageChanged', handler)
}

export default i18next
