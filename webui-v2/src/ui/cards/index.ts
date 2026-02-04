/**
 * Card System - 统一卡片出口
 *
 * 🔒 Contract 强制规则：
 * - 页面禁止自定义卡片布局
 * - 必须使用 CardCollectionWrap 容器
 * - 卡片样式统一（ItemCard/StatusCard）
 */

export { CardCollectionWrap } from './CardCollectionWrap'
export type { CardCollectionWrapProps } from './CardCollectionWrap'

export { ItemCard } from './ItemCard'
export type {
  ItemCardProps,
  ItemCardMeta,
  ItemCardAction,
} from './ItemCard'

export { StatusCard } from './StatusCard'
export type {
  StatusCardProps,
  StatusCardMeta,
  StatusCardAction,
  StatusColor,
} from './StatusCard'
