import { Box, Typography } from '@mui/material'
import { ReactNode } from 'react'

export interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
}

/**
 * PageHeader - 页面顶部标题区组件
 * 用于统一页面的标题展示 + 右侧操作按钮组
 */
export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <Box className="flex items-center justify-between mb-6">
      <Box>
        <Typography variant="h4" component="h1" className="font-semibold">
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" className="mt-1">
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && (
        <Box className="flex items-center gap-2">
          {actions}
        </Box>
      )}
    </Box>
  )
}
