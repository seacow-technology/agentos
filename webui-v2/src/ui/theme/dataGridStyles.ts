import { tokens } from '../tokens/tokens'

/**
 * DataGrid Style Overrides
 *
 * MUI X DataGrid is not part of the core MUI components object,
 * so we provide these sx overrides to be applied directly to DataGrid.
 *
 * Usage:
 *   import { dataGridStyles } from '@/ui/theme/dataGridStyles'
 *   <DataGrid sx={dataGridStyles} ... />
 */

export const dataGridStyles = {
  borderRadius: tokens.radius.sm,
  border: 'none',
  '& .MuiDataGrid-cell:focus': {
    outline: 'none',
  },
  '& .MuiDataGrid-cell:focus-within': {
    outline: 'none',
  },
  '& .MuiDataGrid-columnHeader:focus': {
    outline: 'none',
  },
  '& .MuiDataGrid-columnHeader:focus-within': {
    outline: 'none',
  },
  '& .MuiDataGrid-columnHeaders': {
    backgroundColor: 'rgba(0, 0, 0, 0.02)',
    borderRadius: `${tokens.radius.sm}px ${tokens.radius.sm}px 0 0`,
    minHeight: '56px !important',
    maxHeight: '56px !important',
  },
  '& .MuiDataGrid-columnHeader': {
    fontSize: tokens.typography.label.large.size,
    fontWeight: tokens.typography.label.large.weight,
  },
  '& .MuiDataGrid-row:hover': {
    backgroundColor: 'rgba(0, 0, 0, 0.04)',
  },
  '& .MuiDataGrid-row.Mui-selected': {
    backgroundColor: 'rgba(103, 80, 164, 0.08)',
    '&:hover': {
      backgroundColor: 'rgba(103, 80, 164, 0.12)',
    },
  },
  '& .MuiDataGrid-cell': {
    fontSize: tokens.typography.body.medium.size,
    padding: `${tokens.spacing.md}px`,
  },
  '& .MuiDataGrid-footerContainer': {
    borderTop: '1px solid',
    borderColor: 'divider',
    minHeight: 52,
  },
} as const
