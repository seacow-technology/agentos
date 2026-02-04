import { Card } from '@mui/material'
import { ReactNode } from 'react'
import { alpha } from '@mui/material/styles'

export interface AppCardProps {
  children: ReactNode
  /** 场景变体 - 控制卡片的视觉风格 */
  variant?: 'default' | 'outlined' | 'compact' | 'config'
  /** 语气/色调 - 传达卡片的语义状态 */
  tone?: 'neutral' | 'info' | 'warning' | 'critical'
  /** 阴影高度 - 仅 variant='default' 时有效 */
  elevation?: number
}

/**
 * AppCard - 卡片容器
 *
 * Material Design 3 风格的卡片组件，对 Card 的封装。
 *
 * 限制：
 * - 禁止页面自定义 padding/radius/shadow
 * - 样式由主题统一控制
 * - 不允许传入 sx 或 style 属性
 * - 所有样式变化必须通过 variant/tone 枚举
 *
 * 变体说明：
 * - default: 默认卡片，带阴影
 * - outlined: 边框卡片，无阴影
 * - compact: 紧凑卡片，减少内边距
 * - config: 配置卡片，适合表单/设置页
 *
 * 语气说明：
 * - neutral: 中性（默认）
 * - info: 信息提示（蓝色边框/背景）
 * - warning: 警告（橙色边框/背景）
 * - critical: 严重/危险（红色边框/背景）
 *
 * @example
 * <AppCard>
 *   <AppCardHeader title="User Profile" />
 *   <AppCardBody>
 *     <p>Content goes here</p>
 *   </AppCardBody>
 * </AppCard>
 *
 * @example
 * <AppCard variant="outlined" tone="info">
 *   <AppCardBody>
 *     <p>Information card</p>
 *   </AppCardBody>
 * </AppCard>
 */
export function AppCard({
  children,
  variant = 'default',
  tone = 'neutral',
  elevation = 1,
}: AppCardProps) {
  // 获取语气样式
  const getToneStyles = () => {
    switch (tone) {
      case 'info':
        return {
          borderColor: 'info.main',
          borderWidth: 1,
          borderStyle: 'solid',
          backgroundColor: (theme: any) => alpha(theme.palette.info.main, 0.08),
        }
      case 'warning':
        return {
          borderColor: 'warning.main',
          borderWidth: 1,
          borderStyle: 'solid',
          backgroundColor: (theme: any) => alpha(theme.palette.warning.main, 0.08),
        }
      case 'critical':
        return {
          borderColor: 'error.main',
          borderWidth: 1,
          borderStyle: 'solid',
          backgroundColor: (theme: any) => alpha(theme.palette.error.main, 0.08),
        }
      default:
        return {}
    }
  }

  // 获取变体样式
  const getVariantStyles = () => {
    switch (variant) {
      case 'compact':
        return {
          '& .MuiCardContent-root': {
            padding: 1.5,
            '&:last-child': {
              paddingBottom: 1.5,
            },
          },
          '& .MuiCardHeader-root': {
            padding: 1.5,
          },
        }
      case 'config':
        return {
          '& .MuiCardContent-root': {
            padding: 3,
            '&:last-child': {
              paddingBottom: 3,
            },
          },
          '& .MuiCardHeader-root': {
            padding: 3,
          },
        }
      default:
        return {}
    }
  }

  const cardVariant = variant === 'default' ? 'elevation' : 'outlined'
  const cardElevation = variant === 'default' ? elevation : 0

  return (
    <Card
      variant={cardVariant}
      elevation={cardElevation}
      sx={{
        ...getToneStyles(),
        ...getVariantStyles(),
      }}
    >
      {children}
    </Card>
  )
}
