/**
 * Table Components
 *
 * Material Design 3 表格组件封装层。
 *
 * 设计原则：
 * - 禁止页面直接 import @mui/x-data-grid
 * - 所有表格样式由主题统一控制
 * - 内置状态管理（加载、错误、空状态）
 *
 * 组件列表：
 * - AppTable: 数据表格（DataGrid wrapper）
 * - TableToolbar: 表格工具栏（搜索/操作区）
 *
 * 使用方式：
 * ```tsx
 * import { AppTable, TableToolbar } from '@/ui'
 * import { GridColDef } from '@mui/x-data-grid'
 *
 * function UsersPage() {
 *   const [search, setSearch] = useState('')
 *   const { data, isLoading, error, refetch } = useUsers()
 *
 *   const columns: GridColDef[] = [
 *     { field: 'id', headerName: 'ID', width: 90 },
 *     { field: 'name', headerName: 'Name', flex: 1 },
 *     { field: 'email', headerName: 'Email', flex: 1 },
 *   ]
 *
 *   return (
 *     <>
 *       <TableToolbar
 *         searchValue={search}
 *         onSearchChange={setSearch}
 *         searchPlaceholder="Search users..."
 *         actions={
 *           <PrimaryButton onClick={handleCreate}>
 *             Create User
 *           </PrimaryButton>
 *         }
 *       />
 *       <AppTable
 *         rows={data}
 *         columns={columns}
 *         loading={isLoading}
 *         error={error}
 *         onRetry={refetch}
 *         checkboxSelection
 *         onRowClick={handleRowClick}
 *       />
 *     </>
 *   )
 * }
 * ```
 *
 * 紧凑表格示例：
 * ```tsx
 * <AppTable
 *   rows={data}
 *   columns={columns}
 *   density="compact"
 *   pageSize={25}
 *   disableColumnFilter
 * />
 * ```
 */

export { AppTable } from './AppTable'
export { TableToolbar } from './TableToolbar'

export type { AppTableProps } from './AppTable'
export type { TableToolbarProps } from './TableToolbar'

// Re-export commonly used DataGrid types
export type { GridColDef, GridRowsProp, GridPaginationModel } from '@mui/x-data-grid'
