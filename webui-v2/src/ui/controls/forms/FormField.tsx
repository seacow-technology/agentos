import { Box, FormLabel, FormHelperText } from '@mui/material'
import { ReactNode } from 'react'

export interface FormFieldProps {
  label?: string
  children: ReactNode
  error?: string
  helperText?: string
  required?: boolean
  optional?: boolean
  fullWidth?: boolean
}

/**
 * FormField - 表单字段容器
 *
 * 提供统一的表单字段布局和错误提示展示。
 * 用于包裹任何表单输入组件，提供标签和帮助文本容器。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 *
 * 特点：
 * - 自动处理 required 标记
 * - 统一的错误提示样式
 * - 预留 react-hook-form 集成点
 *
 * @example
 * <FormField label="Email" required error={errors.email}>
 *   <TextInput
 *     value={email}
 *     onChange={setEmail}
 *     type="email"
 *   />
 * </FormField>
 *
 * @example
 * <FormField
 *   label="Status"
 *   helperText="Choose the current status"
 * >
 *   <SelectInput
 *     value={status}
 *     onChange={setStatus}
 *     options={statusOptions}
 *   />
 * </FormField>
 */
export function FormField({
  label,
  children,
  error,
  helperText,
  required = false,
  fullWidth = false,
}: FormFieldProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 0.5,
        width: fullWidth ? '100%' : 'auto',
      }}
    >
      {label && (
        <FormLabel required={required} error={!!error}>
          {label}
        </FormLabel>
      )}
      {children}
      {(error || helperText) && (
        <FormHelperText error={!!error}>
          {error || helperText}
        </FormHelperText>
      )}
    </Box>
  )
}
