/**
 * Text System Types
 *
 * 文案系统类型定义
 */

/**
 * 🔒 翻译参数类型约束
 *
 * 基础类型：Record<string, string | number>
 * 不允许 any 类型，防止滥用
 *
 * 未来可以升级为 per-key 类型映射：
 * - minLength 需要 { min: number }
 * - maxLength 需要 { max: number }
 * - range 需要 { min: number; max: number }
 */
export interface TranslateParams {
  [key: string]: string | number
}

/**
 * 🔒 高频 key 的类型映射（渐进式类型化）
 *
 * 为最常用的 20% key 提供强类型约束
 */
export interface TypedTranslateParams {
  // Validation
  'validation.minLength': { min: number }
  'validation.maxLength': { max: number }
  'validation.range': { min: number; max: number }

  // Form helper
  'form.helper.minLength': { min: number }
  'form.helper.maxLength': { max: number }

  // Table
  'component.table.rowsPerPage': { count: number }
  'component.table.page': { page: number }
  'component.table.of': { total: number }
  'component.table.selected': { count: number }
}

/**
 * 翻译选项
 */
export interface TranslateOptions {
  /**
   * 默认值，当翻译缺失时返回
   */
  defaultValue?: string

  /**
   * 是否在开发环境下显示警告
   * 🔒 只在 dev 或 VITE_I18N_WARN_MISSING=true 时生效
   * @default true
   */
  warn?: boolean
}

/**
 * 语言代码
 */
export type Language = 'en' | 'zh'

/**
 * Fallback 字典结构
 */
export type FallbackDict = Record<string, string>
