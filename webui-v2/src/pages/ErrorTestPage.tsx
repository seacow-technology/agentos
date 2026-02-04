import { useState } from 'react'
import { Box, Button, Typography, Card } from '@mui/material'
import BugReportIcon from '@mui/icons-material/BugReport'

/**
 * ErrorTestPage - 用于测试 ErrorBoundary 的页面
 *
 * 这个页面仅用于开发测试,不应该在生产环境中使用
 */
function ErrorTestPage() {
  const [shouldThrow, setShouldThrow] = useState(false)

  if (shouldThrow) {
    // 故意抛出错误来测试 ErrorBoundary
    throw new Error('这是一个测试错误!用于验证 ErrorBoundary 是否正常工作。')
  }

  const handleTriggerError = () => {
    setShouldThrow(true)
  }

  return (
    <Box sx={{ p: 3 }}>
      <Card sx={{ p: 3, maxWidth: 600, mx: 'auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <BugReportIcon color="warning" sx={{ fontSize: 40 }} />
          <Typography variant="h5">
            ErrorBoundary 测试页面
          </Typography>
        </Box>

        <Typography variant="body1" paragraph>
          这个页面用于测试全局错误边界(ErrorBoundary)是否正常工作。
        </Typography>

        <Typography variant="body2" color="text.secondary" paragraph>
          点击下面的按钮将触发一个 React 错误,ErrorBoundary 会捕获这个错误并显示友好的错误弹窗,防止整个应用白屏。
        </Typography>

        <Button
          variant="contained"
          color="error"
          onClick={handleTriggerError}
          startIcon={<BugReportIcon />}
          fullWidth
        >
          触发测试错误
        </Button>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
          注意:触发错误后,您将看到一个错误弹窗,可以选择重新加载页面或尝试恢复。
        </Typography>
      </Card>
    </Box>
  )
}

export default ErrorTestPage
