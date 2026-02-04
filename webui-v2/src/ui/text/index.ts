/**
 * Text System - 统一文案导出
 *
 * 🔒 硬契约：
 * 1. T 对象是纯静态结构，从 keys.ts 生成，无任何动态 getter
 * 2. 所有 key 必须在 keys.ts 中声明，TypeScript 编译期检查
 * 3. 禁止绕过 @/ui/text 直接 import i18n
 *
 * 使用方式：
 *
 * 方式 1：聚合对象 API (推荐用于 JSX)
 * ```tsx
 * import { T } from '@/ui/text'
 *
 * <Button>{T.common.save}</Button>
 * <Typography>{T.page.tasks.title}</Typography>
 * ```
 *
 * 方式 2：函数 API (推荐用于动态 key 或参数)
 * ```tsx
 * import { t, K } from '@/ui/text'
 *
 * t(K.common.save)
 * t(K.validation.minLength, { min: 5 })
 * ```
 */

import { K } from './keys'
import type { TranslateParams, TranslateOptions, Language, FallbackDict, TypedTranslateParams } from './types'

// Re-export from t.ts
export { t, tr, tm, hasTranslation, getCurrentLanguage, changeLanguage } from './t'

// Re-export from useTextTranslation.ts
export { useTextTranslation } from './useTextTranslation'
export { useTextTranslation as useText } from './useTextTranslation'
export type { UseTextTranslationReturn } from './useTextTranslation'

// Re-export K
export { K }

// Re-export types
export type { TranslateParams, TypedTranslateParams, TranslateOptions, Language, FallbackDict }
export type { TextKey, AllTextKeys } from './keys'

// ============================================
// T Object - 静态文案对象（无 Proxy）
// ============================================

/**
 * 🔒 硬契约：T 对象是纯静态结构
 *
 * 从 keys.ts 的 K 对象递归生成，编译期类型安全。
 * 任何不存在的 key 会在 TypeScript 层直接报错。
 *
 * 实现原理：
 * - 使用 createStaticTextObject 递归遍历 K
 * - 对于每个 leaf key（string 值），调用 t(key) 获取翻译
 * - 对于每个 node key（object 值），递归生成子对象
 * - 结果是一个纯静态对象，无任何 Proxy/Getter
 *
 * 好处：
 * - TypeScript 可以精确推导类型
 * - IDE 自动补全完美支持
 * - 性能最优（无 Proxy 开销）
 * - 调试友好（可以直接 inspect）
 */

// Import t function for generating static text
import { t as translateFn } from './t'

/**
 * 递归生成静态文案对象
 *
 * @param obj - K 对象或其子对象
 * @returns 静态文案对象，所有 leaf 值都是翻译后的字符串
 */
function createStaticTextObject(obj: any): any {
  if (typeof obj === 'string') {
    // Leaf node: 直接返回翻译
    return translateFn(obj)
  }

  if (typeof obj === 'object' && obj !== null) {
    // Branch node: 递归处理子节点
    const result: any = {}
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        result[key] = createStaticTextObject(obj[key])
      }
    }
    return result
  }

  // Fallback
  return obj
}

/**
 * T - 静态文案对象
 *
 * 🔒 这是一个纯静态对象，不使用 Proxy
 * 🔒 所有 key 必须在 keys.ts 中声明
 * 🔒 TypeScript 编译期类型检查
 *
 * 使用示例：
 *   T.common.save           // → 'Save' (en) or '保存' (zh)
 *   T.page.tasks.title      // → 'Tasks' (en) or '任务' (zh)
 *   T.validation.required   // → 'Required' (en) or '必填' (zh)
 */
export const T = createStaticTextObject(K)

/**
 * txt - T 的别名
 *
 * 某些场景下 T 可能与其他变量冲突，可以使用 txt
 */
export const txt = T

/**
 * 🔒 类型推导：确保 T 对象的类型和 K 对象一致
 *
 * 这样 TypeScript 可以：
 * 1. 检查 T.common.save 是否存在
 * 2. 推导出 T.common.save 是 string 类型
 * 3. 提供精确的 IDE 自动补全
 */
export type TObject = {
  [P1 in keyof typeof K]: {
    [P2 in keyof typeof K[P1]]: typeof K[P1][P2] extends string
      ? string
      : typeof K[P1][P2] extends object
      ? {
          [P3 in keyof typeof K[P1][P2]]: string
        }
      : never
  }
}

// 验证 T 对象类型（编译期检查）
// @ts-expect-error - 用于类型检查，不需要实际使用
const _typeCheck: TObject = T

/**
 * 🔒 导出说明
 *
 * ✅ 允许导出：
 * - T: 静态文案对象
 * - t: 翻译函数（支持参数）
 * - K: Key 白名单
 * - tr, txt, tm: 辅助函数
 * - hasTranslation, getCurrentLanguage, changeLanguage: 工具函数
 *
 * ❌ 禁止导出：
 * - i18n 实例（只能在 t.ts 内部使用）
 * - Proxy 相关（已移除）
 * - 动态 key 生成（不存在）
 *
 * 🔒 红线规则（在 UI_GATES.md 中定义）：
 * - 所有 UI 文案必须从 @/ui/text 导入
 * - 禁止从 react-i18next / i18next 导入（除 src/i18n/** 和 src/ui/text/t.ts）
 * - 禁止在页面/组件中硬编码文案（ESLint Rule G7 强制）
 */

// ============================================
// 使用示例（文档）
// ============================================

/**
 * @example
 * // 方式 1：聚合对象 API
 * import { T } from '@/ui/text'
 *
 * function MyComponent() {
 *   return (
 *     <>
 *       <Button>{T.common.save}</Button>
 *       <Typography>{T.page.tasks.title}</Typography>
 *     </>
 *   )
 * }
 *
 * @example
 * // 方式 2：函数 API + Key 常量
 * import { t, K } from '@/ui/text'
 *
 * function MyComponent() {
 *   const buttonText = t(K.common.save)
 *   const titleText = t(K.page.tasks.title)
 *
 *   return (
 *     <>
 *       <Button>{buttonText}</Button>
 *       <Typography>{titleText}</Typography>
 *     </>
 *   )
 * }
 *
 * @example
 * // 方式 3：带参数的翻译
 * import { t, K } from '@/ui/text'
 *
 * function MyComponent() {
 *   const errorMsg = t(K.validation.minLength, { min: 5 })
 *   // "Minimum 5 characters required"
 *
 *   return <FormHelperText error>{errorMsg}</FormHelperText>
 * }
 *
 * @example
 * // 方式 4：批量翻译
 * import { tm } from '@/ui/text'
 *
 * function MyComponent() {
 *   const texts = tm([
 *     'common.save',
 *     'common.cancel',
 *     'common.delete'
 *   ])
 *
 *   return (
 *     <>
 *       <Button>{texts['common.save']}</Button>
 *       <Button>{texts['common.cancel']}</Button>
 *       <Button>{texts['common.delete']}</Button>
 *     </>
 *   )
 * }
 *
 * @example
 * // 方式 5：检查翻译是否存在
 * import { hasTranslation } from '@/ui/text'
 *
 * if (hasTranslation('custom.key')) {
 *   // 使用翻译
 * } else {
 *   // 使用默认值
 * }
 */
