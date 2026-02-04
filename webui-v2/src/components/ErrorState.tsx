import { Box, Typography, Button, Alert } from '@mui/material'
import { K, useTextTranslation } from '@/ui/text'

export interface ErrorStateProps {
  error: string | Error
  onRetry?: () => void
  retryText?: string
}

/**
 * ErrorState - 错误状态展示组件
 * 用于 API 失败、加载错误等场景
 */
export function ErrorState({
  error,
  onRetry,
  retryText,
}: ErrorStateProps) {
  const { t } = useTextTranslation()
  const errorMessage = typeof error === 'string' ? error : error.message

  return (
    <Box className="flex flex-col items-center justify-center py-12 px-4">
      <Alert severity="error" className="mb-4 max-w-md">
        <Typography variant="body2">
          {errorMessage}
        </Typography>
      </Alert>
      {onRetry && (
        <Button variant="contained" color="primary" onClick={onRetry}>
          {retryText ?? t(K.component.errorState.retry)}
        </Button>
      )}
    </Box>
  )
}
