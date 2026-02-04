/**
 * Table System - 统一表格出口
 *
 * 🔒 Contract 强制规则：
 * - 页面禁止自定义 Table 布局
 * - 必须使用 TableShell 三行结构
 * - FilterBar 必须使用 Grid + 宽度枚举
 */

export { TableShell } from './TableShell'
export type { TableShellProps } from './TableShell'

export { FilterBar } from './FilterBar'
export type { FilterBarProps, FilterItem, FilterAction } from './FilterBar'
