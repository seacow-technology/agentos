/**
 * ListToolbar - 列表工具栏组件
 *
 * 🔒 硬契约：列表页必须使用统一的工具栏
 *
 * 目标：
 * - 统一搜索/过滤/操作区布局
 * - 统一工具栏与表格之间的间距
 * - 防止页面自定义工具栏样式
 */

import { Box, TextField, InputAdornment } from '@mui/material'
import { SearchIcon } from '@/ui/icons'
import { TOOLBAR_GAP } from './tokens'

export interface ListToolbarProps {
  /**
   * 搜索占位符
   */
  searchPlaceholder?: string

  /**
   * 搜索值
   */
  searchValue?: string

  /**
   * 搜索变化回调
   */
  onSearchChange?: (value: string) => void

  /**
   * 过滤器区域（可选）
   */
  filters?: React.ReactNode

  /**
   * 操作按钮区域（可选）
   */
  actions?: React.ReactNode
}

/**
 * ListToolbar 组件
 *
 * 🔒 Table 页必须使用此组件
 *
 * 布局：
 * - 左侧：搜索框
 * - 中间：过滤器
 * - 右侧：操作按钮
 * - 工具栏与表格之间：16px 间距
 *
 * @example
 * ```tsx
 * <ListToolbar
 *   searchPlaceholder="Search tasks..."
 *   searchValue={search}
 *   onSearchChange={setSearch}
 *   filters={
 *     <>
 *       <Select value={status} onChange={handleStatus}>
 *         <MenuItem value="all">All</MenuItem>
 *         <MenuItem value="active">Active</MenuItem>
 *       </Select>
 *     </>
 *   }
 *   actions={
 *     <Button variant="contained">New Task</Button>
 *   }
 * />
 * ```
 */
export function ListToolbar({
  searchPlaceholder = 'Search...',
  searchValue = '',
  onSearchChange,
  filters,
  actions,
}: ListToolbarProps) {
  return (
    <Box
      sx={{
        // 🔒 工具栏与表格之间：16px 间距
        mb: TOOLBAR_GAP / 8, // MUI 使用 8px base

        display: 'flex',
        alignItems: 'center',
        gap: 2,
        flexWrap: 'wrap',
      }}
    >
      {/* 搜索框 */}
      {onSearchChange && (
        <TextField
          size="small"
          placeholder={searchPlaceholder}
          value={searchValue}
          onChange={(e) => onSearchChange(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{
            minWidth: 240,
            flex: { xs: '1 1 100%', sm: '0 1 auto' },
          }}
        />
      )}

      {/* 过滤器区域 */}
      {filters && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            flex: { xs: '1 1 100%', sm: '1 1 auto' },
          }}
        >
          {filters}
        </Box>
      )}

      {/* 操作按钮区域 */}
      {actions && (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            ml: 'auto',
          }}
        >
          {actions}
        </Box>
      )}
    </Box>
  )
}
