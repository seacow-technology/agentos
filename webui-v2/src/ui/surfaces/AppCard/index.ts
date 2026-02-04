/**
 * Card Components
 *
 * Material Design 3 卡片组件封装层。
 *
 * 设计原则：
 * - 禁止页面自定义 padding/radius/shadow
 * - 所有卡片样式由主题统一控制
 * - 不允许传入 sx 或 style 属性
 *
 * 组件列表：
 * - AppCard: 卡片容器
 * - AppCardHeader: 卡片头部
 * - AppCardBody: 卡片内容区
 *
 * 使用方式：
 * ```tsx
 * import { AppCard, AppCardHeader, AppCardBody } from '@/ui'
 *
 * function MyPage() {
 *   return (
 *     <AppCard>
 *       <AppCardHeader
 *         title="User Profile"
 *         subtitle="Manage your account"
 *       />
 *       <AppCardBody>
 *         <p>Content goes here</p>
 *       </AppCardBody>
 *     </AppCard>
 *   )
 * }
 * ```
 *
 * 变体示例：
 * ```tsx
 * // Outlined card
 * <AppCard variant="outlined">
 *   <AppCardBody>Content</AppCardBody>
 * </AppCard>
 *
 * // Card with action button
 * <AppCard>
 *   <AppCardHeader
 *     title="Settings"
 *     action={<IconButton><MoreIcon /></IconButton>}
 *   />
 *   <AppCardBody>Content</AppCardBody>
 * </AppCard>
 *
 * // Card with no padding (for tables)
 * <AppCard>
 *   <AppCardHeader title="Users" />
 *   <AppCardBody noPadding>
 *     <AppTable data={users} />
 *   </AppCardBody>
 * </AppCard>
 * ```
 */

export { AppCard } from './AppCard'
export { AppCardHeader } from './AppCardHeader'
export { AppCardBody } from './AppCardBody'

export type { AppCardProps } from './AppCard'
export type { AppCardHeaderProps } from './AppCardHeader'
export type { AppCardBodyProps } from './AppCardBody'
