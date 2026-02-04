/**
 * ChatMessage - Individual Message Bubble Component
 *
 * Displays a single chat message with:
 * - Role-based styling (user/assistant/system)
 * - Avatar
 * - Timestamp
 * - Optional metadata (model, tokens)
 * - Rich content rendering:
 *   - Markdown support (headings, lists, tables, etc.)
 *   - Code syntax highlighting
 *   - Code block actions (copy, download, format, preview)
 *   - Collapsible long code blocks
 */

import { useState, memo, useMemo } from 'react'
import {
  Box,
  Paper,
  Typography,
  Avatar,
  IconButton,
  Tooltip,
  useTheme,
  alpha,
} from '@mui/material'
import {
  Person as PersonIcon,
  SmartToy as SmartToyIcon,
  ContentCopy as CopyIcon,
  Download as DownloadIcon,
  Code as FormatIcon,
  Visibility as PreviewIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Check as CheckIcon,
} from '@mui/icons-material'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { useTranslation } from 'react-i18next'
import * as prettier from 'prettier'
import parserBabel from 'prettier/parser-babel'
import parserHtml from 'prettier/parser-html'
import parserPostcss from 'prettier/parser-postcss'
import parserTypescript from 'prettier/parser-typescript'
import { CodePreviewDialog } from './CodePreviewDialog'
import type { ChatMessageType } from './ChatShell'

interface ChatMessageProps {
  message: ChatMessageType
}

/**
 * Pure function for HTML entity decoding
 * Replaces DOM-based innerHTML approach with efficient string operations
 */
function decodeHTMLEntities(text: string): string {
  const entities: Record<string, string> = {
    '&lt;': '<',
    '&gt;': '>',
    '&amp;': '&',
    '&quot;': '"',
    '&#39;': "'",
    '&nbsp;': ' '
  }

  let decoded = text
  let prevDecoded = ''

  // Recursive decoding (handles multiple layers of escaping)
  while (decoded !== prevDecoded) {
    prevDecoded = decoded
    for (const [entity, char] of Object.entries(entities)) {
      decoded = decoded.split(entity).join(char)
    }
  }

  return decoded
}

/**
 * CodeBlock - Enhanced code block with syntax highlighting and actions
 */
interface CodeBlockProps {
  language: string
  value: string
  inline?: boolean
}

// 🎯 Syntax Highlighting Degradation Strategy
// Long code blocks (>80 lines) default to plain text mode to prevent UI blocking
const MAX_LINES_AUTO_HIGHLIGHT = 80

const CodeBlock = memo(function CodeBlock({ language, value, inline }: CodeBlockProps) {
  const theme = useTheme()
  const agentos = (theme.palette as any).agentos
  const { t } = useTranslation()

  // 🎯 All hooks must be called at the top, before any conditional returns
  const [copied, setCopied] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [formatted, setFormatted] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)

  // Calculate line count for enableHighlight initialization
  const lines = value.split('\n')
  const lineCount = lines.length

  // 🎯 Syntax Highlighting Degradation Strategy
  // For long code blocks (>80 lines), default to plain text mode
  // User can explicitly enable highlighting on demand
  const [enableHighlight, setEnableHighlight] = useState(lineCount <= MAX_LINES_AUTO_HIGHLIGHT)

  const isDark = theme.palette.mode === 'dark'
  const codeStyle = isDark ? oneDark : oneLight

  // Calculate derived state
  const isLongCode = lineCount > 20
  const displayValue = collapsed ? lines.slice(0, 10).join('\n') + '\n...' : value

  // 🎯 Memoize highlighted content to prevent re-rendering
  // Must be called before any conditional returns (React hooks rule)
  // Only re-calculate when displayValue, language, or codeStyle changes
  const highlightedContent = useMemo(() => (
    <SyntaxHighlighter
      language={language || 'text'}
      style={codeStyle}
      customStyle={{
        margin: 0,
        borderRadius: 0,
        fontSize: '0.9em',
      }}
      showLineNumbers={lineCount > 5}
    >
      {displayValue}
    </SyntaxHighlighter>
  ), [displayValue, language, codeStyle, lineCount])

  // If inline code, render simple (after all hooks)
  if (inline) {
    return (
      <code
        style={{
          backgroundColor: alpha(theme.palette.primary.main, 0.1),
          color: theme.palette.primary.main,
          padding: '2px 6px',
          borderRadius: 4,
          fontSize: '0.9em',
          fontFamily: 'monospace',
        }}
      >
        {value}
      </code>
    )
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob([value], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `code.${language || 'txt'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleFormat = async () => {
    try {
      // Determine parser based on language
      let parser: string | undefined
      let plugins: any[] = []

      switch (language.toLowerCase()) {
        case 'html':
        case 'xml':
          parser = 'html'
          plugins = [parserHtml]
          break
        case 'javascript':
        case 'js':
          parser = 'babel'
          plugins = [parserBabel]
          break
        case 'typescript':
        case 'ts':
          parser = 'typescript'
          plugins = [parserTypescript]
          break
        case 'jsx':
          parser = 'babel'
          plugins = [parserBabel]
          break
        case 'tsx':
          parser = 'typescript'
          plugins = [parserTypescript]
          break
        case 'css':
        case 'scss':
        case 'less':
          parser = 'css'
          plugins = [parserPostcss]
          break
        case 'json':
          parser = 'json'
          plugins = [parserBabel]
          break
        default:
          console.warn(`[ChatMessage] Formatting not supported for language: ${language}`)
          return
      }

      // Format code with prettier
      const formattedCode = await prettier.format(value, {
        parser,
        plugins,
        printWidth: 80,
        tabWidth: 2,
        semi: true,
        singleQuote: true,
        trailingComma: 'es5',
      })

      // Copy formatted code to clipboard
      await navigator.clipboard.writeText(formattedCode)
      setFormatted(true)
      setTimeout(() => setFormatted(false), 2000)

      // console.log('[ChatMessage] ✅ Code formatted and copied to clipboard')
    } catch (err) {
      console.error('[ChatMessage] ❌ Format error:', err)
      alert(`格式化失败: ${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  const handlePreview = () => {
    if (language === 'html' || language === 'xml') {
      // Open preview dialog
      setPreviewOpen(true)
    }
  }

  const handleClosePreview = () => {
    setPreviewOpen(false)
  }

  const isHTML = language === 'html' || language === 'xml'

  // 🎯 Plain Text Mode Rendering (for long code blocks without highlighting)
  // Significantly improves performance by avoiding expensive syntax highlighting
  if (!enableHighlight) {
    return (
      <Box sx={{ my: 2 }}>
        {/* Code Block Header */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 0.5,
            bgcolor: alpha(agentos?.bg?.elevated || theme.palette.background.paper, 0.5),
            borderTopLeftRadius: 8,
            borderTopRightRadius: 8,
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          {/* Language Label */}
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'monospace',
              fontWeight: 600,
              color: 'text.secondary',
              textTransform: 'uppercase',
            }}
          >
            {language || 'text'} ({lineCount} {t('common.lines', { defaultValue: 'lines' })})
          </Typography>

          {/* Action Buttons */}
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {/* Enable Highlight Button */}
            <Tooltip title={t('common.enableHighlight', { defaultValue: 'Enable Syntax Highlighting' })}>
              <IconButton
                size="small"
                onClick={() => setEnableHighlight(true)}
                sx={{
                  color: 'primary.main',
                  '&:hover': {
                    bgcolor: alpha(theme.palette.primary.main, 0.1),
                  },
                }}
              >
                <FormatIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            {/* Copy Button */}
            <Tooltip title={copied ? t('common.copied') : t('common.copy')}>
              <IconButton size="small" onClick={handleCopy}>
                {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
              </IconButton>
            </Tooltip>

            {/* Download Button */}
            <Tooltip title={t('common.download')}>
              <IconButton size="small" onClick={handleDownload}>
                <DownloadIcon fontSize="small" />
              </IconButton>
            </Tooltip>

            {/* Collapse/Expand Button (long code only) */}
            {isLongCode && (
              <Tooltip title={collapsed ? t('common.expand') : t('common.collapse')}>
                <IconButton size="small" onClick={() => setCollapsed(!collapsed)}>
                  {collapsed ? <ExpandIcon fontSize="small" /> : <CollapseIcon fontSize="small" />}
                </IconButton>
              </Tooltip>
            )}
          </Box>
        </Box>

        {/* Plain Text Content (No Highlighting) */}
        <Box
          sx={{
            position: 'relative',
            borderBottomLeftRadius: 8,
            borderBottomRightRadius: 8,
            overflow: 'auto',
            bgcolor: isDark ? '#1e1e1e' : '#f5f5f5',
          }}
        >
          <pre
            style={{
              margin: 0,
              padding: '16px',
              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
              fontSize: '0.9em',
              lineHeight: 1.5,
              color: isDark ? '#d4d4d4' : '#333333',
              whiteSpace: 'pre',
              overflowX: 'auto',
            }}
          >
            {displayValue}
          </pre>
        </Box>
      </Box>
    )
  }

  // 🎯 Highlighted mode rendering (syntax highlighting enabled)
  return (
    <Box sx={{ my: 2 }}>
      {/* Code Block Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 0.5,
          bgcolor: alpha(agentos?.bg?.elevated || theme.palette.background.paper, 0.5),
          borderTopLeftRadius: 8,
          borderTopRightRadius: 8,
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        {/* Language Label */}
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'monospace',
            fontWeight: 600,
            color: 'text.secondary',
            textTransform: 'uppercase',
          }}
        >
          {language || 'text'}
        </Typography>

        {/* Action Buttons */}
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {/* Copy Button */}
          <Tooltip title={copied ? t('common.copied') : t('common.copy')}>
            <IconButton size="small" onClick={handleCopy}>
              {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
            </IconButton>
          </Tooltip>

          {/* Download Button */}
          <Tooltip title={t('common.download')}>
            <IconButton size="small" onClick={handleDownload}>
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Tooltip>

          {/* Format Button (HTML/JS/TS/CSS/JSON) */}
          {['html', 'xml', 'javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx', 'css', 'scss', 'less', 'json'].includes(language.toLowerCase()) && (
            <Tooltip title={formatted ? t('common.formatted') : t('common.format')}>
              <IconButton size="small" onClick={handleFormat}>
                {formatted ? <CheckIcon fontSize="small" /> : <FormatIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          )}

          {/* Preview Button (HTML only) */}
          {isHTML && (
            <Tooltip title={t('common.preview')}>
              <IconButton size="small" onClick={handlePreview}>
                <PreviewIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}

          {/* Collapse/Expand Button (long code only) */}
          {isLongCode && (
            <Tooltip title={collapsed ? t('common.expand') : t('common.collapse')}>
              <IconButton size="small" onClick={() => setCollapsed(!collapsed)}>
                {collapsed ? <ExpandIcon fontSize="small" /> : <CollapseIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {/* Code Content (With Highlighting) */}
      <Box
        sx={{
          position: 'relative',
          borderBottomLeftRadius: 8,
          borderBottomRightRadius: 8,
          overflow: 'hidden',
        }}
      >
        {highlightedContent}
      </Box>

      {/* Preview Dialog */}
      <CodePreviewDialog
        open={previewOpen}
        onClose={handleClosePreview}
        code={value}
        language={language}
      />
    </Box>
  )
})

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const theme = useTheme()
  const agentos = (theme.palette as any).agentos
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  // 🎯 Memoize ReactMarkdown rendering to prevent unnecessary re-renders
  const renderedContent = useMemo(() => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={{
        // Custom code block renderer
        code(props: any) {
          const { inline, className, children } = props

          // Extract language from className
          const match = /language-(\w+)/.exec(className || '')
          let language = match ? match[1] : ''
          let value = String(children).replace(/\n$/, '')

          // ✅ Pure function HTML entity decoding (no DOM manipulation)
          // Handles both ReactMarkdown escaping and backend double-escaping
          if (!inline && (value.includes('&lt;') || value.includes('&gt;') || value.includes('&amp;'))) {
            value = decodeHTMLEntities(value)
          }

          // 🔧 Smart Detection: If no language specified, try to detect
          if (!language && !inline) {

            // Auto-detect language based on content
            if (value.match(/^<!DOCTYPE\s+html/i) || value.match(/<html[\s>]/i)) {
              language = 'html'
              // console.log('[ChatMessage] 🎯 Auto-detected language: HTML')
            } else if (value.match(/^import\s+\w+/m) || value.match(/^from\s+\w+\s+import/m) || value.match(/def\s+\w+\(/)) {
              language = 'python'
              // console.log('[ChatMessage] 🎯 Auto-detected language: Python')
            } else if (value.match(/function\s+\w+\(/) || value.match(/const\s+\w+\s*=/) || value.match(/=>\s*{/)) {
              language = 'javascript'
              // console.log('[ChatMessage] 🎯 Auto-detected language: JavaScript')
            } else if (value.match(/SELECT\s+.*\s+FROM/i) || value.match(/CREATE\s+TABLE/i)) {
              language = 'sql'
              // console.log('[ChatMessage] 🎯 Auto-detected language: SQL')
            } else if (value.match(/^{[\s\n]*"/) || value.match(/":\s*[{["]/)) {
              language = 'json'
              // console.log('[ChatMessage] 🎯 Auto-detected language: JSON')
            }
          }

          return (
            <CodeBlock language={language} value={value} inline={inline} />
          )
        },
        // Custom paragraph renderer (remove extra wrapping)
        p({ children }) {
          return <Typography variant="body1" component="span" sx={{ display: 'block' }}>{children}</Typography>
        },
      }}
    >
      {message.content}
    </ReactMarkdown>
  ), [message.content])

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
        ...(isSystem && { justifyContent: 'center' }),
      }}
    >
      {/* Avatar - Assistant/System only (on left) */}
      {!isUser && !isSystem && (
        <Avatar sx={{ mr: 1, bgcolor: 'primary.main', width: 36, height: 36 }}>
          <SmartToyIcon fontSize="small" />
        </Avatar>
      )}

      {/* Message Bubble */}
      <Paper
        elevation={1}
        sx={{
          // 🎯 统一宽度：所有消息 80%
          maxWidth: '80%',
          p: 2,
          // ✅ 使用 AgentOS tokens 适配暗色主题
          bgcolor: isUser
            ? 'primary.main' // 用户消息：保持紫色
            : isSystem
            ? agentos?.bg?.elevated || 'background.paper' // 系统消息：elevated
            : agentos?.bg?.paper || 'background.paper', // 助手消息：paper
          color: isUser ? 'white' : 'text.primary',
          borderRadius: 1,
        }}
      >
        {/* Message Content - Rich Markdown Rendering */}
        <Box
          sx={{
            '& > *:first-of-type': { mt: 0 },
            '& > *:last-child': { mb: 0 },
            // Markdown typography styles
            '& h1, & h2, & h3, & h4, & h5, & h6': {
              mt: 2,
              mb: 1,
              fontWeight: 600,
            },
            '& h1': { fontSize: '1.8em' },
            '& h2': { fontSize: '1.5em' },
            '& h3': { fontSize: '1.3em' },
            '& p': {
              my: 1,
              lineHeight: 1.6,
            },
            '& ul, & ol': {
              my: 1,
              pl: 3,
            },
            '& li': {
              my: 0.5,
            },
            '& blockquote': {
              borderLeft: `4px solid ${theme.palette.primary.main}`,
              pl: 2,
              py: 0.5,
              my: 2,
              color: 'text.secondary',
              fontStyle: 'italic',
            },
            '& table': {
              width: '100%',
              borderCollapse: 'collapse',
              my: 2,
            },
            '& th, & td': {
              border: `1px solid ${theme.palette.divider}`,
              px: 1.5,
              py: 1,
              textAlign: 'left',
            },
            '& th': {
              bgcolor: alpha(theme.palette.primary.main, 0.1),
              fontWeight: 600,
            },
            '& a': {
              color: theme.palette.primary.main,
              textDecoration: 'none',
              '&:hover': {
                textDecoration: 'underline',
              },
            },
            '& hr': {
              border: 'none',
              borderTop: `1px solid ${theme.palette.divider}`,
              my: 2,
            },
            // User message: simpler styling (white text on purple)
            ...(isUser && {
              '& *': { color: 'inherit' },
              '& a': { color: 'inherit', textDecoration: 'underline' },
              '& code': { bgcolor: alpha('#fff', 0.2) },
            }),
          }}
        >
          {renderedContent}
        </Box>

        {/* Timestamp */}
        <Typography
          variant="caption"
          sx={{
            display: 'block',
            mt: 0.5,
            opacity: 0.7,
          }}
        >
          {new Date(message.timestamp).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </Typography>

        {/* Metadata - Model & Tokens */}
        {message.metadata && (
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              opacity: 0.6,
              fontSize: '0.7rem',
              mt: 0.25,
              wordBreak: 'break-word', // ✅ 强制长单词换行
              overflowWrap: 'anywhere', // ✅ 允许在任意位置断行
            }}
          >
            {message.metadata.model}
            {message.metadata.tokens && ` • ${message.metadata.tokens} tokens`}
          </Typography>
        )}
      </Paper>

      {/* Avatar - User only (on right) */}
      {isUser && (
        <Avatar sx={{ ml: 1, bgcolor: 'secondary.main', width: 36, height: 36 }}>
          <PersonIcon fontSize="small" />
        </Avatar>
      )}
    </Box>
  )
}, (prevProps, nextProps) => {
  // Custom comparison: only re-render if message id or content changes
  return prevProps.message.id === nextProps.message.id &&
         prevProps.message.content === nextProps.message.content
})
