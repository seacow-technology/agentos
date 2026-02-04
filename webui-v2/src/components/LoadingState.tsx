import { Box, CircularProgress, Typography } from '@mui/material'
import { K, useTextTranslation } from '@/ui/text'

export interface LoadingStateProps {
  message?: string
  size?: number
}

/**
 * LoadingState - 加载状态展示组件
 * 用于全页或区块加载中的状态展示
 */
export function LoadingState({
  message,
  size = 40
}: LoadingStateProps) {
  const { t } = useTextTranslation()
  const displayMessage = message ?? t(K.component.loadingState.loading)
  return (
    <Box className="flex flex-col items-center justify-center py-12 px-4">
      <CircularProgress size={size} />
      {displayMessage && (
        <Typography variant="body2" color="text.secondary" className="mt-4">
          {displayMessage}
        </Typography>
      )}
    </Box>
  )
}
