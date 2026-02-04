import { Component, ErrorInfo, ReactNode } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  IconButton,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import RefreshIcon from '@mui/icons-material/Refresh'
import BugReportIcon from '@mui/icons-material/BugReport'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import i18n from '../i18n'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  copied: boolean
}

/**
 * ErrorBoundary - 全局错误边界组件
 *
 * 捕获 React 组件树中的错误,防止白屏,显示友好的错误弹窗
 * 支持多语言显示
 */
class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      copied: false,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // 更新 state 使下一次渲染能够显示降级后的 UI
    return {
      hasError: true,
      error,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // 记录错误到错误报告服务
    console.error('ErrorBoundary caught an error:', error, errorInfo)

    this.setState({
      error,
      errorInfo,
    })
  }

  handleReload = () => {
    // 重新加载页面
    window.location.reload()
  }

  handleClose = () => {
    // 尝试恢复,清除错误状态
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      copied: false,
    })
  }

  handleCopyError = () => {
    const { error, errorInfo } = this.state
    const errorText = `
Error: ${error?.name || 'Unknown Error'}
Message: ${error?.message || 'No message'}
Stack: ${error?.stack || 'No stack trace'}

Component Stack:
${errorInfo?.componentStack || 'No component stack'}
    `.trim()

    navigator.clipboard.writeText(errorText).then(() => {
      this.setState({ copied: true })
      setTimeout(() => {
        this.setState({ copied: false })
      }, 2000)
    })
  }

  render() {
    const { hasError, error, errorInfo, copied } = this.state
    const { children } = this.props

    if (hasError) {
      const t = i18n.t

      return (
        <Dialog
          open={true}
          maxWidth="md"
          fullWidth
          PaperProps={{
            sx: {
              borderRadius: 2,
            },
          }}
        >
          <DialogTitle
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              bgcolor: 'error.main',
              color: 'error.contrastText',
            }}
          >
            <BugReportIcon />
            <Typography variant="h6" component="span">
              {t('errorBoundary.title')}
            </Typography>
          </DialogTitle>

          <DialogContent sx={{ mt: 2 }}>
            <Alert severity="error" sx={{ mb: 2 }}>
              <Typography variant="body1" gutterBottom>
                {t('errorBoundary.message')}
              </Typography>
            </Alert>

            <Typography variant="body2" color="text.secondary" paragraph>
              {t('errorBoundary.suggestion')}
            </Typography>

            {/* 错误详情折叠面板 */}
            <Accordion
              sx={{
                mt: 2,
                bgcolor: 'grey.50',
                '&:before': { display: 'none' },
              }}
            >
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                sx={{ bgcolor: 'grey.100' }}
              >
                <Typography variant="body2" fontWeight="medium">
                  {t('errorBoundary.technicalDetails')}
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ position: 'relative' }}>
                  <IconButton
                    size="small"
                    onClick={this.handleCopyError}
                    sx={{
                      position: 'absolute',
                      right: 0,
                      top: 0,
                    }}
                    title={t('common.copy')}
                  >
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>

                  {copied && (
                    <Typography
                      variant="caption"
                      color="success.main"
                      sx={{
                        position: 'absolute',
                        right: 40,
                        top: 8,
                      }}
                    >
                      {t('common.copied')}
                    </Typography>
                  )}

                  <Typography
                    variant="body2"
                    component="pre"
                    sx={{
                      p: 2,
                      bgcolor: 'grey.900',
                      color: 'grey.100',
                      borderRadius: 1,
                      overflow: 'auto',
                      maxHeight: 300,
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {error?.name || 'Error'}: {error?.message || 'Unknown error'}
                    {'\n\n'}
                    {error?.stack}
                    {errorInfo?.componentStack && (
                      <>
                        {'\n\nComponent Stack:'}
                        {errorInfo.componentStack}
                      </>
                    )}
                  </Typography>
                </Box>
              </AccordionDetails>
            </Accordion>
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button
              onClick={this.handleClose}
              color="inherit"
            >
              {t('errorBoundary.tryRecover')}
            </Button>
            <Button
              onClick={this.handleReload}
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
            >
              {t('errorBoundary.reloadPage')}
            </Button>
          </DialogActions>
        </Dialog>
      )
    }

    return children
  }
}

export default ErrorBoundary
