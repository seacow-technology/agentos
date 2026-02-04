import { CardHeader } from '@mui/material'
import { ReactNode } from 'react'

export interface AppCardHeaderProps {
  title: string
  subtitle?: string
  action?: ReactNode
  avatar?: ReactNode
}

/**
 * AppCardHeader - 卡片头部
 *
 * Material Design 3 风格的卡片头部组件，对 CardHeader 的封装。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 *
 * 特点：
 * - 统一的标题和副标题样式
 * - 支持头像和操作按钮
 * - 自动处理对齐和间距
 *
 * @example
 * <AppCardHeader
 *   title="User Profile"
 *   subtitle="Last updated 2 hours ago"
 * />
 *
 * @example
 * <AppCardHeader
 *   title="Settings"
 *   action={
 *     <IconOnlyButton tooltip="Edit">
 *       <EditIcon />
 *     </IconOnlyButton>
 *   }
 * />
 */
export function AppCardHeader({
  title,
  subtitle,
  action,
  avatar,
}: AppCardHeaderProps) {
  return (
    <CardHeader
      title={title}
      subheader={subtitle}
      action={action}
      avatar={avatar}
    />
  )
}
