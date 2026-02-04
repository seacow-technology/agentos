import { DataGrid, GridColDef, GridRowsProp, GridPaginationModel, GridRowSelectionModel, GridCallbackDetails } from '@mui/x-data-grid'
import { Box } from '@mui/material'
import { EmptyState } from '../../../components/EmptyState'
import { ErrorState } from '../../../components/ErrorState'
import { LoadingState } from '../../../components/LoadingState'
import { dataGridStyles } from '../../theme'

export type AppTableDensity = 'compact' | 'standard' | 'comfortable'
export type AppTableVariant = 'default' | 'striped' | 'bordered'

export interface AppTableProps {
  /**
   * 表格行数据
   */
  rows: GridRowsProp

  /**
   * 表格列定义
   */
  columns: GridColDef[]

  /**
   * 密度变体
   * @default 'standard'
   */
  density?: AppTableDensity

  /**
   * 视觉变体
   * @default 'default'
   */
  variant?: AppTableVariant

  /**
   * 加载状态
   */
  loading?: boolean

  /**
   * 错误消息
   */
  error?: string | null

  /**
   * 错误重试回调
   */
  onRetry?: () => void

  /**
   * 空状态消息
   */
  emptyMessage?: string

  /**
   * 空状态操作
   */
  emptyAction?: {
    label: string
    onClick: () => void
  }

  /**
   * 是否启用复选框选择
   */
  checkboxSelection?: boolean

  /**
   * 行选择模型
   */
  rowSelectionModel?: GridRowSelectionModel

  /**
   * 行选择变化回调
   */
  onRowSelectionModelChange?: (rowSelectionModel: GridRowSelectionModel, details: GridCallbackDetails) => void

  /**
   * 行点击回调
   */
  onRowClick?: (params: any) => void

  /**
   * 分页模型
   */
  paginationModel?: GridPaginationModel

  /**
   * 分页模型变化回调
   */
  onPaginationModelChange?: (model: GridPaginationModel) => void

  /**
   * 每页显示行数（便捷属性）
   * @deprecated 请使用 paginationModel={{ pageSize: number, page: 0 }}
   */
  pageSize?: number

  /**
   * 是否禁用列过滤
   */
  disableColumnFilter?: boolean

  /**
   * 是否禁用列菜单
   */
  disableColumnMenu?: boolean

  /**
   * 是否禁用列选择器
   */
  disableColumnSelector?: boolean

  /**
   * 是否禁用密度选择器
   */
  disableDensitySelector?: boolean

  /**
   * 是否自动高度
   */
  autoHeight?: boolean

  /**
   * 每页显示行数选项
   */
  pageSizeOptions?: number[]

  /**
   * 是否隐藏页脚
   */
  hideFooter?: boolean

  /**
   * 是否隐藏页脚分页
   */
  hideFooterPagination?: boolean

  /**
   * 是否隐藏页脚选中行数
   */
  hideFooterSelectedRowCount?: boolean
}

/**
 * AppTable - 数据表格组件
 *
 * 基于 MUI DataGrid 的封装，提供统一的表格体验。
 *
 * 限制：
 * - 不允许传入 sx 或 style 属性
 * - 样式由主题和变体统一控制
 * - 密度和变体通过 props 控制
 *
 * 变体系统：
 * - density: 控制行高（compact: 32px | standard: 52px | comfortable: 72px）
 * - variant: 控制视觉风格（default | striped | bordered）
 *
 * 内置状态：
 * - Loading: 显示加载骨架屏
 * - Error: 显示错误信息和重试按钮
 * - Empty: 显示空状态提示
 *
 * @example
 * // 基础用法
 * <AppTable
 *   rows={users}
 *   columns={columns}
 *   loading={isLoading}
 * />
 *
 * @example
 * // 紧凑斑马纹表格
 * <AppTable
 *   rows={data}
 *   columns={columns}
 *   density="compact"
 *   variant="striped"
 * />
 *
 * @example
 * // 带复选框和错误处理
 * <AppTable
 *   rows={data}
 *   columns={columns}
 *   checkboxSelection
 *   error={error}
 *   onRetry={refetch}
 * />
 */
export function AppTable({
  rows,
  columns,
  density = 'standard',
  variant = 'default',
  loading = false,
  error = null,
  onRetry,
  emptyMessage,
  emptyAction,
  checkboxSelection = false,
  rowSelectionModel,
  onRowSelectionModelChange,
  onRowClick,
  paginationModel,
  onPaginationModelChange,
  pageSize,
  disableColumnFilter = false,
  disableColumnMenu = false,
  disableColumnSelector = false,
  disableDensitySelector = false,
  autoHeight = false,
  pageSizeOptions = [10, 25, 50, 100],
  hideFooter = false,
  hideFooterPagination = false,
  hideFooterSelectedRowCount = false,
}: AppTableProps) {
  // 处理 pageSize 便捷属性（向后兼容）
  const finalPaginationModel = paginationModel || (pageSize ? { pageSize, page: 0 } : undefined)
  // 显示加载状态
  if (loading) {
    return (
      <Box sx={{ height: 400 }}>
        <LoadingState />
      </Box>
    )
  }

  // 显示错误状态
  if (error) {
    return (
      <Box sx={{ height: 400 }}>
        <ErrorState error={error} onRetry={onRetry} />
      </Box>
    )
  }

  // 显示空状态
  if (!rows || rows.length === 0) {
    return (
      <Box sx={{ height: 400 }}>
        <EmptyState
          message={emptyMessage || 'No data found.'}
          action={emptyAction}
        />
      </Box>
    )
  }

  // 计算行高
  const rowHeight = (() => {
    switch (density) {
      case 'compact':
        return 32
      case 'comfortable':
        return 72
      case 'standard':
      default:
        return 52
    }
  })()

  // 计算变体样式
  const variantSx = (() => {
    switch (variant) {
      case 'striped':
        return {
          '& .MuiDataGrid-row:nth-of-type(even)': {
            backgroundColor: 'action.hover',
          },
        }
      case 'bordered':
        return {
          '& .MuiDataGrid-cell': {
            borderRight: '1px solid',
            borderColor: 'divider',
          },
        }
      case 'default':
      default:
        return {}
    }
  })()

  return (
    <Box
      sx={{
        width: '100%',
        ...dataGridStyles,
        ...variantSx,
      }}
    >
      <DataGrid
        rows={rows}
        columns={columns}
        rowHeight={rowHeight}
        checkboxSelection={checkboxSelection}
        rowSelectionModel={rowSelectionModel}
        onRowSelectionModelChange={onRowSelectionModelChange}
        onRowClick={onRowClick}
        paginationModel={finalPaginationModel}
        onPaginationModelChange={onPaginationModelChange}
        pageSizeOptions={pageSizeOptions}
        disableColumnFilter={disableColumnFilter}
        disableColumnMenu={disableColumnMenu}
        disableColumnSelector={disableColumnSelector}
        disableDensitySelector={disableDensitySelector}
        autoHeight={autoHeight}
        hideFooter={hideFooter}
        hideFooterPagination={hideFooterPagination}
        hideFooterSelectedRowCount={hideFooterSelectedRowCount}
        disableRowSelectionOnClick
        sx={{
          border: 'none',
        }}
      />
    </Box>
  )
}

// Re-export types for convenience
export type { GridColDef, GridRowsProp, GridPaginationModel }
