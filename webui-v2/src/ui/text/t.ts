/**
 * Text Translation Function
 *
 * 统一翻译函数，决策链：
 * 1. i18n.t(key, params) 如果存在翻译 → 返回
 * 2. 否则查 fallbackDict[currentLang][key]
 * 3. 再否则查 fallbackDict[defaultLang][key]
 * 4. 最后返回 [key]（或 key 本身），并在 dev 环境 console.warn
 */

import i18n from '../../i18n'
import { dictEn } from './dict.en'
import { dictZh } from './dict.zh'
import type { TranslateParams, TranslateOptions, Language, FallbackDict } from './types'

/**
 * Fallback 字典映射
 */
const fallbackDicts: Record<Language, FallbackDict> = {
  en: dictEn,
  zh: dictZh,
}

/**
 * 默认语言
 */
const DEFAULT_LANG: Language = 'en'

/**
 * 简单的模板替换函数
 * 支持 {key} 格式的插值
 *
 * @example
 * interpolate('Hello {name}', { name: 'World' }) // 'Hello World'
 */
function interpolate(text: string, params: TranslateParams): string {
  return text.replace(/\{(\w+)\}/g, (_, key) => {
    const value = params[key]
    return value !== undefined ? String(value) : `{${key}}`
  })
}

/**
 * 翻译函数
 *
 * @param key - 翻译 key
 * @param params - 插值参数
 * @param options - 翻译选项
 * @returns 翻译后的文本
 *
 * @example
 * // 基础用法
 * t('common.save') // 'Save' or '保存'
 *
 * @example
 * // 带参数
 * t('validation.minLength', { min: 5 }) // 'Minimum 5 characters'
 *
 * @example
 * // 带默认值
 * t('unknown.key', {}, { defaultValue: 'Fallback Text' })
 */
export function t(
  key: string,
  params?: TranslateParams,
  options?: TranslateOptions
): string {
  const { defaultValue, warn = true } = options || {}

  // 1. 尝试从 i18n 获取翻译
  if (i18n.exists(key)) {
    const translated = i18n.t(key, params)
    return String(translated)
  }

  // 2. 尝试从当前语言的 fallback 字典获取
  const currentLang = i18n.language as Language
  const currentDict = fallbackDicts[currentLang]
  if (currentDict && currentDict[key]) {
    const text = currentDict[key]
    return params ? interpolate(text, params) : text
  }

  // 3. 尝试从默认语言的 fallback 字典获取
  if (currentLang !== DEFAULT_LANG) {
    const defaultDict = fallbackDicts[DEFAULT_LANG]
    if (defaultDict && defaultDict[key]) {
      const text = defaultDict[key]
      return params ? interpolate(text, params) : text
    }
  }

  // 4. 使用提供的默认值
  if (defaultValue) {
    return params ? interpolate(defaultValue, params) : defaultValue
  }

  // 5. 最后返回 [key] 并在开发环境警告
  // 🔒 硬契约：warn 只在 dev 或 VITE_I18N_WARN_MISSING=true 时启用
  // 防止在生产环境（桌面端/CI）污染日志
  const shouldWarn = warn && (
    import.meta.env.DEV ||
    import.meta.env.VITE_I18N_WARN_MISSING === 'true'
  )

  if (shouldWarn) {
    console.warn(`[ui/text] Missing translation for key: "${key}"`)
  }

  return `[${key}]`
}

/**
 * 翻译函数（React 组件版本）
 * 返回 JSX-safe 的字符串
 *
 * @param key - 翻译 key
 * @param params - 插值参数
 * @param options - 翻译选项
 * @returns 翻译后的文本
 */
export function tr(
  key: string,
  params?: TranslateParams,
  options?: TranslateOptions
): string {
  return t(key, params, options)
}

/**
 * 批量翻译
 * 用于一次性获取多个 key 的翻译
 *
 * @param keys - 翻译 key 数组
 * @returns key-value 映射对象
 *
 * @example
 * const texts = tm(['common.save', 'common.cancel'])
 * // { 'common.save': 'Save', 'common.cancel': 'Cancel' }
 */
export function tm(keys: string[]): Record<string, string> {
  return keys.reduce((acc, key) => {
    acc[key] = t(key)
    return acc
  }, {} as Record<string, string>)
}

/**
 * 检查翻译是否存在
 *
 * @param key - 翻译 key
 * @returns 是否存在翻译
 */
export function hasTranslation(key: string): boolean {
  if (i18n.exists(key)) {
    return true
  }

  const currentLang = i18n.language as Language
  const currentDict = fallbackDicts[currentLang]
  if (currentDict && currentDict[key]) {
    return true
  }

  if (currentLang !== DEFAULT_LANG) {
    const defaultDict = fallbackDicts[DEFAULT_LANG]
    if (defaultDict && defaultDict[key]) {
      return true
    }
  }

  return false
}

/**
 * 获取当前语言
 *
 * @returns 当前语言代码
 */
export function getCurrentLanguage(): Language {
  return i18n.language as Language
}

/**
 * 切换语言
 *
 * @param lang - 目标语言代码
 */
export async function changeLanguage(lang: Language): Promise<void> {
  await i18n.changeLanguage(lang)
}
