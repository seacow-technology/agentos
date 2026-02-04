import { useTranslation as useI18nextTranslation } from 'react-i18next'
import type { Language } from './index'

/**
 * React hook for using i18n in components
 *
 * This is a re-export of react-i18next's useTranslation hook
 * with proper typing for our application.
 *
 * @returns Translation utilities
 *
 * @example
 * function MyComponent() {
 *   const { t, i18n } = useTranslation()
 *
 *   return (
 *     <div>
 *       <h1>{t('pages.lab.form.title')}</h1>
 *       <button onClick={() => i18n.changeLanguage('en')}>
 *         Switch to English
 *       </button>
 *     </div>
 *   )
 * }
 */
export function useTranslation() {
  const { t, i18n } = useI18nextTranslation()

  return {
    t,
    i18n: {
      ...i18n,
      language: i18n.language as Language,
      changeLanguage: (lang: Language) => i18n.changeLanguage(lang)
    }
  }
}

export default useTranslation
