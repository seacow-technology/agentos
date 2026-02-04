/**
 * DataGrid 多语言配置
 *
 * 为 MUI DataGrid 组件提供中英文翻译
 */

import type { GridLocaleText } from '@mui/x-data-grid'

/**
 * 中文 localeText
 */
export const zhCN: Partial<GridLocaleText> = {
  // Root
  noRowsLabel: '暂无数据',
  noResultsOverlayLabel: '未找到数据',

  // Density selector toolbar button text
  toolbarDensity: '表格密度',
  toolbarDensityLabel: '表格密度',
  toolbarDensityCompact: '紧凑',
  toolbarDensityStandard: '标准',
  toolbarDensityComfortable: '舒适',

  // Columns selector toolbar button text
  toolbarColumns: '列',
  toolbarColumnsLabel: '选择列',

  // Filters toolbar button text
  toolbarFilters: '筛选',
  toolbarFiltersLabel: '显示筛选',
  toolbarFiltersTooltipHide: '隐藏筛选',
  toolbarFiltersTooltipShow: '显示筛选',
  toolbarFiltersTooltipActive: (count) => `${count} 个筛选`,

  // Quick filter toolbar field
  toolbarQuickFilterPlaceholder: '搜索…',
  toolbarQuickFilterLabel: '搜索',
  toolbarQuickFilterDeleteIconLabel: '清除',

  // Export selector toolbar button text
  toolbarExport: '导出',
  toolbarExportLabel: '导出',
  toolbarExportCSV: '导出为 CSV',
  toolbarExportPrint: '打印',
  toolbarExportExcel: '导出为 Excel',

  // Columns panel text
  // columnsPanelTextFieldLabel: '查找列',
  // columnsPanelTextFieldPlaceholder: '列标题',
  // columnsPanelDragIconLabel: '重新排序列',
  // columnsPanelShowAllButton: '显示全部',
  // columnsPanelHideAllButton: '隐藏全部',

  // Filter panel text
  filterPanelAddFilter: '添加筛选',
  filterPanelRemoveAll: '移除全部',
  filterPanelDeleteIconLabel: '删除',
  filterPanelLogicOperator: '逻辑运算符',
  filterPanelOperator: '运算符',
  filterPanelOperatorAnd: '与',
  filterPanelOperatorOr: '或',
  filterPanelColumns: '列',
  filterPanelInputLabel: '值',
  filterPanelInputPlaceholder: '筛选值',

  // Filter operators text
  filterOperatorContains: '包含',
  filterOperatorEquals: '等于',
  filterOperatorStartsWith: '开始于',
  filterOperatorEndsWith: '结束于',
  filterOperatorIs: '是',
  filterOperatorNot: '不是',
  filterOperatorAfter: '在后面',
  filterOperatorOnOrAfter: '在当天或之后',
  filterOperatorBefore: '在前面',
  filterOperatorOnOrBefore: '在当天或之前',
  filterOperatorIsEmpty: '为空',
  filterOperatorIsNotEmpty: '不为空',
  filterOperatorIsAnyOf: '是其中之一',

  // Header filter operators text
  headerFilterOperatorContains: '包含',
  headerFilterOperatorEquals: '等于',
  headerFilterOperatorStartsWith: '开始于',
  headerFilterOperatorEndsWith: '结束于',
  headerFilterOperatorIs: '是',
  headerFilterOperatorNot: '不是',
  headerFilterOperatorAfter: '在后面',
  headerFilterOperatorOnOrAfter: '在当天或之后',
  headerFilterOperatorBefore: '在前面',
  headerFilterOperatorOnOrBefore: '在当天或之前',
  headerFilterOperatorIsEmpty: '为空',
  headerFilterOperatorIsNotEmpty: '不为空',
  headerFilterOperatorIsAnyOf: '是其中之一',
  'headerFilterOperator=': '等于',
  'headerFilterOperator!=': '不等于',
  'headerFilterOperator>': '大于',
  'headerFilterOperator>=': '大于等于',
  'headerFilterOperator<': '小于',
  'headerFilterOperator<=': '小于等于',

  // Filter values text
  filterValueAny: '任意',
  filterValueTrue: '真',
  filterValueFalse: '假',

  // Column menu text
  columnMenuLabel: '菜单',
  columnMenuShowColumns: '显示列',
  columnMenuManageColumns: '管理列',
  columnMenuFilter: '筛选',
  columnMenuHideColumn: '隐藏',
  columnMenuUnsort: '取消排序',
  columnMenuSortAsc: '升序排序',
  columnMenuSortDesc: '降序排序',

  // Column header text
  columnHeaderFiltersTooltipActive: (count) => `${count} 个筛选`,
  columnHeaderFiltersLabel: '显示筛选',
  columnHeaderSortIconLabel: '排序',

  // Rows selected footer text
  footerRowSelected: (count) => `已选择 ${count.toLocaleString()} 行`,

  // Total row amount footer text
  footerTotalRows: '总行数：',

  // Total visible row amount footer text
  footerTotalVisibleRows: (visibleCount, totalCount) =>
    `${visibleCount.toLocaleString()} / ${totalCount.toLocaleString()}`,

  // Checkbox selection text
  checkboxSelectionHeaderName: '多选框',
  checkboxSelectionSelectAllRows: '选择全部行',
  checkboxSelectionUnselectAllRows: '取消选择全部行',
  checkboxSelectionSelectRow: '选择行',
  checkboxSelectionUnselectRow: '取消选择行',

  // Boolean cell text
  booleanCellTrueLabel: '是',
  booleanCellFalseLabel: '否',

  // Actions cell more text
  actionsCellMore: '更多',

  // Column pinning text
  pinToLeft: '固定在左侧',
  pinToRight: '固定在右侧',
  unpin: '取消固定',

  // Tree Data
  treeDataGroupingHeaderName: '分组',
  treeDataExpand: '展开',
  treeDataCollapse: '折叠',

  // Grouping columns
  groupingColumnHeaderName: '分组',
  groupColumn: (name) => `按 ${name} 分组`,
  unGroupColumn: (name) => `取消按 ${name} 分组`,

  // Master/detail
  detailPanelToggle: '详情面板切换',
  expandDetailPanel: '展开',
  collapseDetailPanel: '折叠',

  // Row reordering text
  rowReorderingHeaderName: '行重新排序',

  // Aggregation
  aggregationMenuItemHeader: '聚合',
  aggregationFunctionLabelSum: '求和',
  aggregationFunctionLabelAvg: '平均值',
  aggregationFunctionLabelMin: '最小值',
  aggregationFunctionLabelMax: '最大值',
  aggregationFunctionLabelSize: '大小',
}

/**
 * 英文 localeText (使用 MUI 默认值)
 */
export const enUS: Partial<GridLocaleText> = {
  // Root
  noRowsLabel: 'No rows',
  noResultsOverlayLabel: 'No results found',

  // Density selector toolbar button text
  toolbarDensity: 'Density',
  toolbarDensityLabel: 'Density',
  toolbarDensityCompact: 'Compact',
  toolbarDensityStandard: 'Standard',
  toolbarDensityComfortable: 'Comfortable',

  // Columns selector toolbar button text
  toolbarColumns: 'Columns',
  toolbarColumnsLabel: 'Select columns',

  // Filters toolbar button text
  toolbarFilters: 'Filters',
  toolbarFiltersLabel: 'Show filters',
  toolbarFiltersTooltipHide: 'Hide filters',
  toolbarFiltersTooltipShow: 'Show filters',
  toolbarFiltersTooltipActive: (count) => `${count} active filter${count !== 1 ? 's' : ''}`,

  // Quick filter toolbar field
  toolbarQuickFilterPlaceholder: 'Search…',
  toolbarQuickFilterLabel: 'Search',
  toolbarQuickFilterDeleteIconLabel: 'Clear',

  // Export selector toolbar button text
  toolbarExport: 'Export',
  toolbarExportLabel: 'Export',
  toolbarExportCSV: 'Download as CSV',
  toolbarExportPrint: 'Print',
  toolbarExportExcel: 'Download as Excel',

  // Columns panel text
  // columnsPanelTextFieldLabel: 'Find column',
  // columnsPanelTextFieldPlaceholder: 'Column title',
  // columnsPanelDragIconLabel: 'Reorder column',
  // columnsPanelShowAllButton: 'Show all',
  // columnsPanelHideAllButton: 'Hide all',

  // Filter panel text
  filterPanelAddFilter: 'Add filter',
  filterPanelRemoveAll: 'Remove all',
  filterPanelDeleteIconLabel: 'Delete',
  filterPanelLogicOperator: 'Logic operator',
  filterPanelOperator: 'Operator',
  filterPanelOperatorAnd: 'And',
  filterPanelOperatorOr: 'Or',
  filterPanelColumns: 'Columns',
  filterPanelInputLabel: 'Value',
  filterPanelInputPlaceholder: 'Filter value',

  // Filter operators text
  filterOperatorContains: 'contains',
  filterOperatorEquals: 'equals',
  filterOperatorStartsWith: 'starts with',
  filterOperatorEndsWith: 'ends with',
  filterOperatorIs: 'is',
  filterOperatorNot: 'is not',
  filterOperatorAfter: 'is after',
  filterOperatorOnOrAfter: 'is on or after',
  filterOperatorBefore: 'is before',
  filterOperatorOnOrBefore: 'is on or before',
  filterOperatorIsEmpty: 'is empty',
  filterOperatorIsNotEmpty: 'is not empty',
  filterOperatorIsAnyOf: 'is any of',

  // Filter values text
  filterValueAny: 'any',
  filterValueTrue: 'true',
  filterValueFalse: 'false',

  // Column menu text
  columnMenuLabel: 'Menu',
  columnMenuShowColumns: 'Show columns',
  columnMenuManageColumns: 'Manage columns',
  columnMenuFilter: 'Filter',
  columnMenuHideColumn: 'Hide',
  columnMenuUnsort: 'Unsort',
  columnMenuSortAsc: 'Sort by ASC',
  columnMenuSortDesc: 'Sort by DESC',

  // Column header text
  columnHeaderFiltersTooltipActive: (count) =>
    `${count} active filter${count !== 1 ? 's' : ''}`,
  columnHeaderFiltersLabel: 'Show filters',
  columnHeaderSortIconLabel: 'Sort',

  // Rows selected footer text
  footerRowSelected: (count) =>
    `${count.toLocaleString()} row${count !== 1 ? 's' : ''} selected`,

  // Total row amount footer text
  footerTotalRows: 'Total Rows:',

  // Total visible row amount footer text
  footerTotalVisibleRows: (visibleCount, totalCount) =>
    `${visibleCount.toLocaleString()} of ${totalCount.toLocaleString()}`,

  // Checkbox selection text
  checkboxSelectionHeaderName: 'Checkbox selection',
  checkboxSelectionSelectAllRows: 'Select all rows',
  checkboxSelectionUnselectAllRows: 'Unselect all rows',
  checkboxSelectionSelectRow: 'Select row',
  checkboxSelectionUnselectRow: 'Unselect row',

  // Boolean cell text
  booleanCellTrueLabel: 'yes',
  booleanCellFalseLabel: 'no',

  // Actions cell more text
  actionsCellMore: 'more',

  // Column pinning text
  pinToLeft: 'Pin to left',
  pinToRight: 'Pin to right',
  unpin: 'Unpin',

  // Tree Data
  treeDataGroupingHeaderName: 'Group',
  treeDataExpand: 'see children',
  treeDataCollapse: 'hide children',

  // Grouping columns
  groupingColumnHeaderName: 'Group',
  groupColumn: (name) => `Group by ${name}`,
  unGroupColumn: (name) => `Stop grouping by ${name}`,

  // Master/detail
  detailPanelToggle: 'Detail panel toggle',
  expandDetailPanel: 'Expand',
  collapseDetailPanel: 'Collapse',

  // Row reordering text
  rowReorderingHeaderName: 'Row reordering',

  // Aggregation
  aggregationMenuItemHeader: 'Aggregation',
  aggregationFunctionLabelSum: 'sum',
  aggregationFunctionLabelAvg: 'avg',
  aggregationFunctionLabelMin: 'min',
  aggregationFunctionLabelMax: 'max',
  aggregationFunctionLabelSize: 'size',
}
