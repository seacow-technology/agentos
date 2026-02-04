import { TextField } from '@mui/material'
import { forwardRef, ReactNode } from 'react'

export interface TextInputProps {
  label?: string
  value?: string
  onChange?: (value: string) => void
  placeholder?: string
  disabled?: boolean
  error?: boolean
  helperText?: string
  required?: boolean
  multiline?: boolean
  rows?: number
  maxRows?: number
  type?: 'text' | 'password' | 'email' | 'number' | 'tel' | 'url'
  fullWidth?: boolean
  size?: 'small' | 'medium'
  startAdornment?: ReactNode
  endAdornment?: ReactNode
  autoFocus?: boolean
  autoComplete?: string
  maxLength?: number
}

/**
 * TextInput - 文本输入框
 *
 * Material Design 3 风格的文本输入组件，对 TextField 的薄封装。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 支持 react-hook-form 集成（通过 ref 转发）
 *
 * 特点：
 * - 统一的 onChange 接口（直接传值而非事件）
 * - 支持 startAdornment/endAdornment
 * - 支持单行和多行输入
 *
 * @example
 * <TextInput
 *   label="Name"
 *   value={name}
 *   onChange={setName}
 *   required
 * />
 *
 * @example
 * <TextInput
 *   label="Description"
 *   multiline
 *   rows={4}
 *   value={description}
 *   onChange={setDescription}
 * />
 */
export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  (
    {
      label,
      value,
      onChange,
      placeholder,
      disabled = false,
      error = false,
      helperText,
      required = false,
      multiline = false,
      rows,
      maxRows,
      type = 'text',
      fullWidth = false,
      size = 'medium',
      startAdornment,
      endAdornment,
      autoFocus = false,
      autoComplete,
      maxLength,
    },
    ref
  ) => {
    return (
      <TextField
        ref={ref}
        label={label}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        error={error}
        helperText={helperText}
        required={required}
        multiline={multiline}
        rows={rows}
        maxRows={maxRows}
        type={type}
        fullWidth={fullWidth}
        size={size}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        InputProps={{
          startAdornment,
          endAdornment,
        }}
        inputProps={{
          maxLength,
        }}
      />
    )
  }
)

TextInput.displayName = 'TextInput'
