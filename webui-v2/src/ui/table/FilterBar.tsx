/**
 * FilterBar - 过滤栏组件
 *
 * 🔒 Grid Contract 强制规则：
 * - 必须使用 Grid 容器
 * - FilterItem 宽度枚举：3/12、4/12、6/12、12/12
 * - 一行最多 4 列（最小 3/12）
 * - 布局：filters grid + 右侧 actions（可选）
 *
 * 使用示例：
 * ```tsx
 * <FilterBar
 *   filters={[
 *     { width: 4, component: <TextField label={T.filter.search} /> },
 *     { width: 4, component: <Select label={T.filter.status} /> },
 *     { width: 4, component: <Select label={T.filter.priority} /> },
 *   ]}
 *   actions={[
 *     { key: 'reset', label: T.common.reset, onClick: handleReset },
 *     { key: 'apply', label: T.common.apply, variant: 'contained', onClick: handleApply },
 *   ]}
 * />
 * ```
 */

import React from 'react'
import { Grid, Button } from '@mui/material'
import { Box } from '@mui/material'

// ===================================
// Types
// ===================================

/**
 * FilterItem - 过滤项配置
 *
 * 🔒 宽度只允许枚举值：3/12、4/12、6/12、12/12
 */
export interface FilterItem {
  /**
   * Grid 宽度（枚举值）
   * - 3: 一行 4 列（最小）
   * - 4: 一行 3 列（默认）
   * - 6: 一行 2 列
   * - 12: 整行
   */
  width: 3 | 4 | 6 | 12

  /**
   * 过滤组件（TextField/Select/DatePicker 等）
   */
  component: React.ReactNode
}

/**
 * FilterAction - 过滤操作按钮
 */
export interface FilterAction {
  key: string
  label: React.ReactNode
  onClick: () => void
  variant?: 'text' | 'outlined' | 'contained'
  disabled?: boolean
}

export interface FilterBarProps {
  /**
   * 过滤项列表
   */
  filters: FilterItem[]

  /**
   * 操作按钮（Reset/Apply 等）
   */
  actions?: FilterAction[]
}

// ===================================
// Component
// ===================================

/**
 * FilterBar 组件
 *
 * 🎨 布局结构（强制）：
 * - Grid 容器（多行自动换行）
 * - FilterItem 宽度枚举：3/12、4/12、6/12、12/12
 * - 一行最多 4 列
 *
 * 🔒 页面禁止自定义 FilterBar 布局
 */
export function FilterBar({ filters, actions }: FilterBarProps) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1,
        bgcolor: 'background.paper',
        border: (theme) => `1px solid ${theme.palette.divider}`,
      }}
    >
      <Grid container spacing={2} alignItems="center">
        {/* Filters Grid */}
        {filters.map((filter, index) => (
          <Grid item xs={12} md={filter.width} key={index}>
            {filter.component}
          </Grid>
        ))}

        {/* Actions（右侧对齐） */}
        {actions && actions.length > 0 && (
          <Grid item xs={12} md="auto" sx={{ ml: 'auto' }}>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              {actions.map((action) => (
                <Button
                  key={action.key}
                  variant={action.variant ?? 'text'}
                  onClick={action.onClick}
                  disabled={action.disabled}
                >
                  {action.label}
                </Button>
              ))}
            </Box>
          </Grid>
        )}
      </Grid>
    </Box>
  )
}
