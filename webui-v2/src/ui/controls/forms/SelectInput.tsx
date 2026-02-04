import { TextField, MenuItem } from '@mui/material'
import { forwardRef, ReactNode } from 'react'

export interface SelectOption {
  value: string | number
  label: string
  disabled?: boolean
}

export interface SelectInputProps {
  label?: string
  value?: string | number
  onChange?: (value: string | number) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  error?: boolean
  helperText?: string
  required?: boolean
  fullWidth?: boolean
  size?: 'small' | 'medium'
  multiple?: boolean
  renderValue?: (value: unknown) => ReactNode
}

/**
 * SelectInput - 下拉选择框
 *
 * Material Design 3 风格的选择输入组件，对 Select 的封装。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 * - 支持 react-hook-form 集成（通过 ref 转发）
 *
 * 特点：
 * - 统一的 onChange 接口（直接传值而非事件）
 * - 基于 options 数组渲染
 * - 支持禁用选项
 *
 * @example
 * <SelectInput
 *   label="Status"
 *   value={status}
 *   onChange={setStatus}
 *   options={[
 *     { value: 'active', label: 'Active' },
 *     { value: 'inactive', label: 'Inactive' },
 *   ]}
 * />
 *
 * @example
 * <SelectInput
 *   label="Priority"
 *   value={priority}
 *   onChange={setPriority}
 *   options={priorityOptions}
 *   required
 *   helperText="Select task priority"
 * />
 */
export const SelectInput = forwardRef<HTMLInputElement, SelectInputProps>(
  (
    {
      label,
      value,
      onChange,
      options,
      placeholder,
      disabled = false,
      error = false,
      helperText,
      required = false,
      fullWidth = false,
      size = 'medium',
      multiple = false,
      renderValue,
    },
    ref
  ) => {
    return (
      <TextField
        ref={ref}
        select
        label={label}
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        error={error}
        helperText={helperText}
        required={required}
        fullWidth={fullWidth}
        size={size}
        SelectProps={{
          multiple,
          renderValue,
        }}
      >
        {options.map((option) => (
          <MenuItem
            key={option.value}
            value={option.value}
            disabled={option.disabled}
          >
            {option.label}
          </MenuItem>
        ))}
      </TextField>
    )
  }
)

SelectInput.displayName = 'SelectInput'
