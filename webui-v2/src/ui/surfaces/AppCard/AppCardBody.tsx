import { CardContent } from '@mui/material'
import { ReactNode } from 'react'

export interface AppCardBodyProps {
  children: ReactNode
  noPadding?: boolean
}

/**
 * AppCardBody - 卡片内容区
 *
 * Material Design 3 风格的卡片内容组件，对 CardContent 的封装。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - padding 使用 theme.spacing
 *
 * 特点：
 * - 统一的内边距
 * - 支持 noPadding 选项（用于表格等场景）
 * - 自动处理最后一个元素的 margin
 *
 * @example
 * <AppCardBody>
 *   <Typography variant="body1">
 *     Card content goes here
 *   </Typography>
 * </AppCardBody>
 *
 * @example
 * <AppCardBody noPadding>
 *   <AppTable data={data} columns={columns} />
 * </AppCardBody>
 */
export function AppCardBody({ children, noPadding = false }: AppCardBodyProps) {
  return (
    <CardContent
      sx={{
        padding: noPadding ? 0 : undefined,
        '&:last-child': {
          paddingBottom: noPadding ? 0 : undefined,
        },
      }}
    >
      {children}
    </CardContent>
  )
}
