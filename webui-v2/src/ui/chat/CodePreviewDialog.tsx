/**
 * CodePreviewDialog - HTML Code Preview Dialog
 *
 * 🎯 Purpose: Preview HTML code in an iframe dialog (similar to webui v1)
 *
 * Features:
 * - Full-screen dialog with iframe
 * - Console output capture
 * - Responsive design
 * - Theme adaptation
 */

import { useState, useRef, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Paper,
  Typography,
  useTheme,
  Divider,
} from '@mui/material'
import {
  Close as CloseIcon,
  Fullscreen as FullscreenIcon,
  FullscreenExit as FullscreenExitIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material'
import { t, K } from '@/ui/text'
import { get, post } from '@platform/http'
import { config } from '@platform/config/env'

export interface CodePreviewDialogProps {
  open: boolean
  onClose: () => void
  code: string
  language: string
}

interface ConsoleMessage {
  method: 'log' | 'error' | 'warn' | 'info'
  args: string[]
  timestamp: number
}

/**
 * CodePreviewDialog Component
 *
 * Displays HTML code in an iframe with console output
 */
export function CodePreviewDialog({
  open,
  onClose,
  code,
  language,
}: CodePreviewDialogProps) {
  const theme = useTheme()
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [consoleMessages, setConsoleMessages] = useState<ConsoleMessage[]>([])
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // Clear console when dialog opens
  useEffect(() => {
    if (open) {
      setConsoleMessages([])
    }
  }, [open])

  // Listen for console messages from iframe
  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      if (e.data?.type === 'console') {
        const { method, args } = e.data
        setConsoleMessages((prev) => [
          ...prev,
          {
            method,
            args,
            timestamp: Date.now(),
          },
        ])
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  // Prepare HTML with console capture script
  const prepareHtml = (htmlCode: string) => {
    const consoleScript = `
<script>
(function() {
  const original = {
    log: console.log,
    error: console.error,
    warn: console.warn,
    info: console.info
  };

  ['log', 'error', 'warn', 'info'].forEach(method => {
    console[method] = function(...args) {
      original[method].apply(console, args);
      window.parent.postMessage({
        type: 'console',
        method: method,
        args: args.map(arg => {
          try {
            return typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg);
          } catch {
            return '[Object]';
          }
        })
      }, '*');
    };
  });
})();
</script>`

    // Wrap HTML if it's not a complete document
    const wrapped = htmlCode.includes('<html')
      ? htmlCode
      : `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  padding: 20px;
  line-height: 1.6;
  color: #333;
}
* {
  box-sizing: border-box;
}
</style>
</head>
<body>
${htmlCode}
</body>
</html>`

    // Inject console capture script before </body>
    return wrapped.replace('</body>', consoleScript + '</body>')
  }

  // Load HTML into iframe using server preview endpoint (avoids sandbox warning)
  useEffect(() => {
    if (open && code) {
      // console.log('[CodePreviewDialog] 🔍 Raw code received:', code.substring(0, 500))
      const wrappedHtml = prepareHtml(code)
      // console.log('[CodePreviewDialog] 🔍 Wrapped HTML:', wrappedHtml.substring(0, 500))

      // Ensure CSRF token exists before making POST request
      const ensureCSRFToken = async () => {
        // ✅ Always call GET /api/csrf-token to ensure session is initialized
        // This endpoint is exempt from CSRF protection and generates token on GET
        try {
          await get<{ csrf_token: string }>('/api/csrf-token')

          // ⏱️ Wait for browser to process Set-Cookie header
          await new Promise(resolve => setTimeout(resolve, 200))

          // 🔍 Debug: Check if cookie was set
          const hasCookie = document.cookie.includes('csrf_token=')
          // console.log('[CodePreviewDialog] 🔍 Cookie check:', hasCookie ? 'Found' : 'Not found')
          // console.log('[CodePreviewDialog] 🔍 All cookies:', document.cookie)

          if (!hasCookie) {
            console.error('[CodePreviewDialog] ❌ CSRF cookie not set by server! Check:')
            console.error('  1. Session middleware is installed')
            console.error('  2. Response has Set-Cookie header')
            console.error('  3. Cookie domain matches current domain')
          }
        } catch (err) {
          console.warn('[CodePreviewDialog] Failed to get CSRF token:', err)
        }

        // Create preview session
        try {
          const data = await post<{ session_id: string; url: string; preset: string }>('/api/preview', {
            html: wrappedHtml,
            preset: 'html-basic', // Use 'three-webgl-umd' for Three.js auto-detection
          })

          if (data.url) {
            // Construct full URL with backend base URL
            const fullUrl = `${config.apiBaseUrl}${data.url}`
            setPreviewUrl(fullUrl)
          }
        } catch (err: any) {
          console.error('[CodePreviewDialog] ❌ Failed to create preview session:', err)
          console.error('[CodePreviewDialog] 🔍 Error details:', {
            status: err.status,
            code: err.code,
            message: err.message,
            data: err.data,
          })
        }
      }

      ensureCSRFToken()
    }

    return () => {
      setPreviewUrl(null)
    }
  }, [open, code])

  // Handle refresh
  const handleRefresh = async () => {
    setConsoleMessages([])
    if (code) {
      const wrappedHtml = prepareHtml(code)

      try {
        // Create new preview session using httpClient
        const data = await post<{ session_id: string; url: string; preset: string }>('/api/preview', {
          html: wrappedHtml,
          preset: 'html-basic',
        })

        if (data.url) {
          // Construct full URL with backend base URL
          const fullUrl = `${config.apiBaseUrl}${data.url}`
          setPreviewUrl(fullUrl)
        }
      } catch (err) {
        console.error('[CodePreviewDialog] Failed to refresh preview:', err)
      }
    }
  }

  // Toggle fullscreen
  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  // Console message color
  const getConsoleColor = (method: string) => {
    switch (method) {
      case 'error':
        return theme.palette.error.main
      case 'warn':
        return theme.palette.warning.main
      case 'info':
        return theme.palette.info.main
      default:
        return theme.palette.text.primary
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={isFullscreen ? false : 'lg'}
      fullWidth
      fullScreen={isFullscreen}
      sx={{
        // ✅ Ensure dialog is above AppBar (zIndex: drawer + 1 = 1041)
        zIndex: (theme) => theme.zIndex.modal + 100,
      }}
      PaperProps={{
        sx: {
          height: isFullscreen ? '100%' : '80vh',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      {/* Dialog Header */}
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        {/* ✅ Use Box instead of Typography to avoid h6 inside h2 */}
        <Box sx={{ fontSize: '1.25rem', fontWeight: 500 }}>
          {t(K.common.preview)} - {language.toUpperCase()}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <IconButton size="small" onClick={handleRefresh} title={t(K.common.refresh)}>
            <RefreshIcon />
          </IconButton>
          <IconButton
            size="small"
            onClick={handleToggleFullscreen}
            title={isFullscreen ? t(K.common.exitFullscreen) : t(K.common.fullscreen)}
          >
            {isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
          </IconButton>
          <IconButton size="small" onClick={onClose} title={t(K.common.close)}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <Divider />

      {/* Dialog Content */}
      <DialogContent
        sx={{
          flex: 1,
          p: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Preview Frame */}
        <Box
          sx={{
            flex: 1,
            position: 'relative',
            overflow: 'hidden',
            bgcolor: 'background.paper',
          }}
        >
          <iframe
            ref={iframeRef}
            title={t(K.common.htmlPreview)}
            src={previewUrl || ''}
            // ✅ Server endpoint allows loading with proper origin, no sandbox warning
            sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups"
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              backgroundColor: '#fff',
            }}
          />
        </Box>

        {/* Console Output */}
        {consoleMessages.length > 0 && (
          <>
            <Divider />
            <Paper
              elevation={0}
              sx={{
                height: 200,
                overflow: 'auto',
                bgcolor: theme.palette.mode === 'dark' ? '#1e1e1e' : '#f5f5f5',
                p: 1,
                fontFamily: 'monospace',
                fontSize: '0.875rem',
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  display: 'block',
                  color: 'text.secondary',
                  mb: 1,
                  fontWeight: 'bold',
                }}
              >
                Console Output:
              </Typography>
              {consoleMessages.map((msg, idx) => (
                <Box key={idx} sx={{ mb: 0.5 }}>
                  <Typography
                    component="span"
                    sx={{
                      color: getConsoleColor(msg.method),
                      fontWeight: msg.method === 'error' ? 'bold' : 'normal',
                    }}
                  >
                    [{msg.method}]
                  </Typography>{' '}
                  <Typography component="span" sx={{ color: 'text.primary' }}>
                    {msg.args.join(' ')}
                  </Typography>
                </Box>
              ))}
            </Paper>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
