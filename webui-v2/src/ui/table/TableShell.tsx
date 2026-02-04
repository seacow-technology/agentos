/**
 * TableShell - 三行结构表格容器
 *
 * 🔒 Contract 强制规则：
 * - Row 1: FilterBar（过滤栏）
 * - Row 2: Table Content（表格内容 + loading/empty 三态）
 * - Row 3: Pagination（分页）
 *
 * 页面禁止自定义 Table 布局，必须使用此组件。
 *
 * 使用示例：
 * ```tsx
 * <TableShell
 *   loading={loading}
 *   rows={tasks}
 *   columns={columns}
 *   filterBar={<FilterBar filters={filters} />}
 *   emptyState={{ title: T.empty.noTasks }}
 *   pagination={{ page, total, onPageChange }}
 * />
 * ```
 */

import React from 'react'
import { Box } from '@mui/material'
import { DataGrid, GridColDef, GridRowsProp } from '@mui/x-data-grid'
import { EmptyState, EmptyStateProps } from '@/ui/layout'
import { TOOLBAR_GAP } from '@/ui/layout/tokens'
import { useTextTranslation } from '@/ui/text'
import { zhCN, enUS } from './localeText'

// ===================================
// Types
// ===================================

export interface TableShellProps {
  /**
   * 是否正在加载
   */
  loading?: boolean

  /**
   * 表格行数据
   */
  rows: GridRowsProp

  /**
   * 表格列定义
   */
  columns: GridColDef[]

  /**
   * FilterBar 组件（Row 1）
   */
  filterBar?: React.ReactNode

  /**
   * 空态配置（与 EmptyStateProps 一致）
   */
  emptyState?: EmptyStateProps

  /**
   * 分页配置
   */
  pagination?: {
    page: number
    pageSize?: number
    total: number
    onPageChange: (page: number) => void
    onPageSizeChange?: (pageSize: number) => void
  }

  /**
   * 行点击回调
   */
  onRowClick?: (row: any) => void

  /**
   * 自动高度（默认 true）
   */
  autoHeight?: boolean

  /**
   * 固定高度（与 autoHeight 互斥）
   */
  height?: number
}

// ===================================
// Component
// ===================================

/**
 * TableShell 组件
 *
 * 🎨 三行结构（强制）：
 * 1. FilterBar（可选）
 * 2. Table Content（loading/empty/ready 三态）
 * 3. Pagination（可选）
 *
 * 🔒 页面禁止自定义 Table 布局
 */
export function TableShell({
  loading = false,
  rows,
  columns,
  filterBar,
  emptyState,
  pagination,
  onRowClick,
  autoHeight = true,
  height,
}: TableShellProps) {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { language } = useTextTranslation()
  const localeText = language === 'zh' ? zhCN : enUS
  // ===================================
  // Row 1: FilterBar
  // ===================================
  const renderFilterBar = () => {
    if (!filterBar) return null

    return (
      <Box sx={{ mb: TOOLBAR_GAP / 8 }}>
        {filterBar}
      </Box>
    )
  }

  // ===================================
  // Row 2: Table Content（三态）
  // ===================================
  const renderTableContent = () => {
    // 态 1: Loading → Skeleton
    if (loading) {
      return (
        <Box sx={{ height: height || 400 }}>
          <DataGrid
            rows={[]}
            columns={columns}
            loading={true}
            hideFooter
            localeText={localeText}
          />
        </Box>
      )
    }

    // 态 2: Empty → EmptyState
    if ((!rows || rows.length === 0) && emptyState) {
      return <EmptyState {...emptyState} />
    }

    // 态 3: Ready → Table
    return (
      <Box sx={{ height: autoHeight ? 'auto' : height || 600 }}>
        <DataGrid
          rows={rows || []}
          columns={columns}
          autoHeight={autoHeight}
          disableRowSelectionOnClick
          onRowClick={onRowClick ? (params) => onRowClick(params.row) : undefined}
          localeText={localeText}
          {...(pagination ? {
            paginationMode: 'server' as const,
            paginationModel: {
              page: pagination.page,
              pageSize: pagination.pageSize || 25,
            },
            pageSizeOptions: [5, 10, 25, 50, 100],
            rowCount: pagination.total,
            onPaginationModelChange: (model) => {
              pagination.onPageChange(model.page)
              pagination.onPageSizeChange?.(model.pageSize)
            },
          } : {
            hideFooter: true,
          })}
          sx={{
            border: 'none',
            '& .MuiDataGrid-cell:focus': {
              outline: 'none',
            },
            '& .MuiDataGrid-row': {
              cursor: onRowClick ? 'pointer' : 'default',
            },
          }}
        />
      </Box>
    )
  }

  // ===================================
  // Main Render
  // ===================================
  return (
    <Box>
      {/* Row 1: FilterBar */}
      {renderFilterBar()}

      {/* Row 2: Table Content */}
      {renderTableContent()}

      {/* Row 3: Pagination（DataGrid 内建，无需额外渲染） */}
    </Box>
  )
}
