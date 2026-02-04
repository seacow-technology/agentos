import { Card, CardHeader, CardContent, CardActions } from '@mui/material'
import { ReactNode } from 'react'

export interface SectionCardProps {
  title?: string
  children: ReactNode
  actions?: ReactNode
  className?: string
}

/**
 * SectionCard - 统一的卡片容器组件
 * 用于包裹表单、信息块等内容区域
 */
export function SectionCard({ title, children, actions, className }: SectionCardProps) {
  return (
    <Card className={className} elevation={1}>
      {title && <CardHeader title={title} />}
      <CardContent>
        {children}
      </CardContent>
      {actions && (
        <CardActions className="px-4 pb-4">
          {actions}
        </CardActions>
      )}
    </Card>
  )
}
