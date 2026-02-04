/**
 * useTextTranslation - React Hook for Text System
 *
 * 🎯 解决问题：
 * - react-i18next 的 useTranslation() 只查 i18n 资源（zh.json/en.json）
 * - 但我们的翻译主要在 fallback 字典（dictZh.ts/dictEn.ts）
 * - 需要一个 hook 既能订阅语言变化，又能使用 fallback 逻辑
 *
 * 🔒 设计原则：
 * - 复用 @/ui/text/t 的完整 fallback 逻辑
 * - 订阅 i18n 的 languageChanged 事件
 * - 语言切换时触发组件重新渲染
 *
 * 使用方式：
 * ```tsx
 * import { useTextTranslation } from '@/ui/text'
 * import { K } from '@/ui/text'
 *
 * function MyPage() {
 *   const { t } = useTextTranslation()
 *
 *   return <h1>{t(K.page.home.title)}</h1>  // ✓ 会自动更新
 * }
 * ```
 */

import { useState, useEffect } from 'react'
import { t as translateFn } from './t'
import i18n from '../../i18n'
import type { Language, TranslateParams, TranslateOptions } from './types'

export interface UseTextTranslationReturn {
  /**
   * 翻译函数（带 fallback 逻辑）
   */
  t: (key: string, params?: TranslateParams, options?: TranslateOptions) => string

  /**
   * 当前语言
   */
  language: Language

  /**
   * i18n 实例（用于高级操作）
   */
  i18n: typeof i18n
}

/**
 * useTextTranslation Hook
 *
 * 订阅语言变化并提供翻译函数
 *
 * @returns { t, language, i18n }
 *
 * @example
 * const { t } = useTextTranslation()
 * const title = t(K.page.home.title)  // ← 会自动响应语言变化
 */
export function useTextTranslation(): UseTextTranslationReturn {
  // 订阅当前语言（语言变化时触发重新渲染）
  const [language, setLanguage] = useState<Language>(i18n.language as Language)

  useEffect(() => {
    // 监听语言变化事件
    const handleLanguageChanged = (lng: string) => {
      setLanguage(lng as Language)
    }

    i18n.on('languageChanged', handleLanguageChanged)

    // Cleanup
    return () => {
      i18n.off('languageChanged', handleLanguageChanged)
    }
  }, [])

  return {
    t: translateFn,  // ← 使用原来的 t 函数（带 fallback 逻辑）
    language,
    i18n,
  }
}
