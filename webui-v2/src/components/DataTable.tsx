import { Box, CircularProgress, Typography } from '@mui/material'
import { K, useTextTranslation } from '@/ui/text'

export interface DataTableColumn {
  field: string
  headerName: string
  width?: number
  flex?: number
  sortable?: boolean
}

export interface DataTableProps {
  columns: DataTableColumn[]
  rows: Record<string, unknown>[]
  loading?: boolean
  onRowClick?: (row: Record<string, unknown>) => void
  emptyMessage?: string
}

/**
 * DataTable - 简单数据表格组件
 * 对 MUI Table 的轻量包装，内置 loading 和空状态
 * 注意：这是简化版实现，未来可替换为 MUI DataGrid
 */
export function DataTable({
  columns,
  rows,
  loading = false,
  onRowClick,
  emptyMessage,
}: DataTableProps) {
  const { t } = useTextTranslation()

  if (loading) {
    return (
      <Box className="flex items-center justify-center py-12">
        <CircularProgress />
      </Box>
    )
  }

  if (rows.length === 0) {
    return (
      <Box className="flex items-center justify-center py-12">
        <Typography variant="body2" color="text.secondary">
          {emptyMessage ?? t(K.component.table.noData)}
        </Typography>
      </Box>
    )
  }

  return (
    <Box className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.field}
                className="px-4 py-3 text-left text-sm font-medium text-gray-700 border-b"
                style={{ width: col.width, flex: col.flex }}
              >
                {col.headerName}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={row.id as string || index}
              onClick={() => onRowClick?.(row)}
              className={`border-b hover:bg-gray-50 ${onRowClick ? 'cursor-pointer' : ''}`}
            >
              {columns.map((col) => (
                <td key={col.field} className="px-4 py-3 text-sm text-gray-900">
                  {String(row[col.field] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Box>
  )
}
