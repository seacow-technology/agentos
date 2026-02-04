/**
 * Button Components
 *
 * Material Design 3 按钮封装层，提供一致的按钮变体。
 *
 * 设计原则：
 * - 禁止页面直接 import @mui/material/Button
 * - 所有按钮样式由主题统一控制
 * - 只暴露必要的功能性 props
 * - 不允许传入 sx 或 style 属性
 *
 * 按钮层级：
 * - PrimaryButton: 主要操作（contained, primary）
 * - SecondaryButton: 次要操作（outlined, primary）
 * - DangerButton: 危险操作（contained, error）
 * - IconOnlyButton: 纯图标按钮
 * - ButtonWithIcon: 图标文字按钮（统一间距）
 *
 * 使用方式：
 * ```tsx
 * import { PrimaryButton, SecondaryButton } from '@/ui'
 *
 * function MyPage() {
 *   return (
 *     <>
 *       <PrimaryButton onClick={handleSave}>Save</PrimaryButton>
 *       <SecondaryButton onClick={handleCancel}>Cancel</SecondaryButton>
 *     </>
 *   )
 * }
 * ```
 */

export { PrimaryButton } from './PrimaryButton'
export { SecondaryButton } from './SecondaryButton'
export { DangerButton } from './DangerButton'
export { IconOnlyButton } from './IconOnlyButton'
export { ButtonWithIcon } from './ButtonWithIcon'

export type { PrimaryButtonProps } from './PrimaryButton'
export type { SecondaryButtonProps } from './SecondaryButton'
export type { DangerButtonProps } from './DangerButton'
export type { IconOnlyButtonProps } from './IconOnlyButton'
export type { ButtonWithIconProps } from './ButtonWithIcon'
