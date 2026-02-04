/**
 * ChatInputBar - Message Input Component
 *
 * Provides:
 * - Multi-line text input
 * - Attach button (disabled in No-Interaction mode)
 * - Send button
 * - Enter to send (Shift+Enter for new line)
 *
 * 🎯 支持受控和非受控两种模式：
 * - 非受控模式：组件内部管理状态（默认）
 * - 受控模式：通过 value/onChange 外部控制（用于 Draft 保护）
 */

import { useState } from 'react'
import { Box, TextField, IconButton } from '@mui/material'
import { Send as SendIcon, AttachFile as AttachFileIcon } from '@mui/icons-material'

interface ChatInputBarProps {
  onSend?: (text: string) => void
  placeholder?: string
  disabled?: boolean
  // 🎯 受控模式支持（用于 Draft 保护）
  value?: string
  onChange?: (value: string) => void
}

export function ChatInputBar({
  onSend,
  placeholder = 'Type a message...',
  disabled = false,
  value: controlledValue,
  onChange: controlledOnChange,
}: ChatInputBarProps) {
  // 非受控模式的内部状态
  const [internalText, setInternalText] = useState('')

  // 判断是否为受控模式
  const isControlled = controlledValue !== undefined
  const text = isControlled ? controlledValue : internalText
  const setText = isControlled ? controlledOnChange! : setInternalText

  const handleSend = () => {
    if (text.trim() && onSend) {
      onSend(text.trim())
      setText('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
      {/* Attach Button */}
      <IconButton disabled={disabled} size="large" color="default">
        <AttachFileIcon />
      </IconButton>

      {/* Text Input */}
      <TextField
        fullWidth
        multiline
        maxRows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        variant="outlined"
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: 1,
          },
        }}
      />

      {/* Send Button */}
      <IconButton
        color="primary"
        disabled={disabled || !text.trim()}
        onClick={handleSend}
        size="large"
      >
        <SendIcon />
      </IconButton>
    </Box>
  )
}
