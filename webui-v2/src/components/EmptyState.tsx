import { Box, Typography, Button } from '@mui/material'
import { ReactNode } from 'react'

export interface EmptyStateProps {
  message: string
  icon?: ReactNode
  action?: {
    label: string
    onClick: () => void
  }
}

/**
 * EmptyState - 空状态展示组件
 * 用于列表为空、搜索无结果等场景
 */
export function EmptyState({ message, icon, action }: EmptyStateProps) {
  return (
    <Box className="flex flex-col items-center justify-center py-12 px-4">
      {icon && (
        <Box className="mb-4 text-gray-400">
          {icon}
        </Box>
      )}
      <Typography variant="body1" color="text.secondary" className="mb-4 text-center">
        {message}
      </Typography>
      {action && (
        <Button variant="outlined" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </Box>
  )
}
