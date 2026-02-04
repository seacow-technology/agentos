import { Box, InputAdornment } from '@mui/material'
import { SearchIcon } from '../../icons'
import { ReactNode } from 'react'
import { TextInput } from '../../controls/forms/TextInput'

export interface TableToolbarProps {
  searchValue?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  actions?: ReactNode
}

/**
 * TableToolbar - 表格工具栏
 *
 * 提供统一的表格顶部工具栏，包含搜索框和操作按钮区域。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题统一控制
 *
 * 特点：
 * - 搜索框和操作按钮统一布局
 * - 响应式设计
 * - 预留筛选功能扩展点
 *
 * @example
 * <TableToolbar
 *   searchValue={search}
 *   onSearchChange={setSearch}
 *   searchPlaceholder="Search users..."
 *   actions={
 *     <PrimaryButton onClick={handleCreate}>
 *       Create User
 *     </PrimaryButton>
 *   }
 * />
 *
 * @example
 * <TableToolbar
 *   searchValue={search}
 *   onSearchChange={setSearch}
 *   actions={
 *     <>
 *       <SecondaryButton>Export</SecondaryButton>
 *       <PrimaryButton>Add New</PrimaryButton>
 *     </>
 *   }
 * />
 */
export function TableToolbar({
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search...',
  actions,
}: TableToolbarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        gap: 2,
        alignItems: 'center',
        justifyContent: 'space-between',
        mb: 2,
        flexWrap: 'wrap',
      }}
    >
      {/* 搜索框 */}
      {onSearchChange && (
        <Box sx={{ flex: '1 1 300px', maxWidth: 400 }}>
          <TextInput
            value={searchValue}
            onChange={onSearchChange}
            placeholder={searchPlaceholder}
            fullWidth
            size="small"
            startAdornment={
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            }
          />
        </Box>
      )}

      {/* 操作按钮区 */}
      {actions && (
        <Box
          sx={{
            display: 'flex',
            gap: 1,
            alignItems: 'center',
          }}
        >
          {actions}
        </Box>
      )}
    </Box>
  )
}
