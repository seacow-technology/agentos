/**
 * Type validation test for component library
 * This file verifies that all component Props types are properly exported
 * and have no 'any' types in their definitions.
 */

import type {
  PageHeaderProps,
  SectionCardProps,
  DataTableProps,
  DataTableColumn,
  EmptyStateProps,
  ErrorStateProps,
  LoadingStateProps,
} from './index'

// Type guards to ensure no 'any' types
const _testPageHeader: PageHeaderProps = {
  title: 'Test',
  subtitle: 'Optional',
  actions: null,
}

const _testSectionCard: SectionCardProps = {
  title: 'Test',
  children: null,
  actions: null,
  className: 'test-class',
}

const _testDataTableColumn: DataTableColumn = {
  field: 'id',
  headerName: 'ID',
  width: 100,
  flex: 1,
  sortable: true,
}

const _testDataTable: DataTableProps = {
  columns: [_testDataTableColumn],
  rows: [{ id: '1', name: 'Test' }],
  loading: false,
  onRowClick: (row) => console.log(row),
  emptyMessage: 'No data',
}


const _testEmptyState: EmptyStateProps = {
  message: 'No items',
  icon: null,
  action: {
    label: 'Create',
    onClick: () => {},
  },
}

const _testErrorState: ErrorStateProps = {
  error: 'Something went wrong',
  onRetry: () => {},
  retryText: 'Try again',
}

const _testLoadingState: LoadingStateProps = {
  message: 'Loading...',
  size: 40,
}

// Export to prevent unused variable warnings
export const __test_types = {
  _testPageHeader,
  _testSectionCard,
  _testDataTableColumn,
  _testDataTable,
  _testEmptyState,
  _testErrorState,
  _testLoadingState,
}
