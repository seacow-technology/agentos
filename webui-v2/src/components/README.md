# AgentOS WebUI v2 - Component Library

无业务逻辑的原子组件库，用于构建统一的 UI 界面。

## 快速使用

### 导入组件
```typescript
import {
  PageHeader,
  SectionCard,
  DataTable,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components'

// 导入类型
import type { PageHeaderProps, DataTableColumn } from '../components'
```

### 路径别名（Vite 运行时）
```typescript
import { PageHeader } from '@components'
```

---

## 组件列表

### 1. PageHeader - 页面头部
统一的页面标题区域 + 右侧操作按钮。

```typescript
<PageHeader
  title="Page Title"
  subtitle="Optional description"
  actions={
    <>
      <Button variant="outlined">Cancel</Button>
      <Button variant="contained">Save</Button>
    </>
  }
/>
```

**Props**:
- `title: string` - 页面标题（必填）
- `subtitle?: string` - 副标题
- `actions?: ReactNode` - 右侧操作按钮组

---

### 2. SectionCard - 卡片容器
用于包裹表单、信息块等内容区域。

```typescript
<SectionCard
  title="User Information"
  actions={<Button size="small">Edit</Button>}
>
  <TextField label="Name" />
  <TextField label="Email" />
</SectionCard>
```

**Props**:
- `title?: string` - 卡片标题
- `children: ReactNode` - 卡片内容（必填）
- `actions?: ReactNode` - 底部操作按钮
- `className?: string` - 自定义样式类

---

### 3. DataTable - 数据表格
简单的数据表格组件，内置 loading 和空状态。

```typescript
const columns: DataTableColumn[] = [
  { field: 'id', headerName: 'ID', width: 100 },
  { field: 'name', headerName: 'Name', flex: 1 },
  { field: 'status', headerName: 'Status', width: 150 },
]

<DataTable
  columns={columns}
  rows={data}
  loading={isLoading}
  onRowClick={(row) => console.log(row)}
  emptyMessage="No data available"
/>
```

**Props**:
- `columns: DataTableColumn[]` - 列定义（必填）
- `rows: Record<string, unknown>[]` - 数据行（必填）
- `loading?: boolean` - 加载状态
- `onRowClick?: (row: Record<string, unknown>) => void` - 行点击事件
- `emptyMessage?: string` - 空数据提示文本

**DataTableColumn**:
- `field: string` - 字段名
- `headerName: string` - 列标题
- `width?: number` - 固定宽度
- `flex?: number` - 弹性宽度
- `sortable?: boolean` - 是否可排序（未实现）

---

### 4. ConfirmDialog - 确认对话框
用于删除、危险操作前的二次确认。

```typescript
const [open, setOpen] = useState(false)

<ConfirmDialog
  open={open}
  title="Confirm Deletion"
  message="Are you sure you want to delete this item?"
  confirmText="Delete"
  cancelText="Cancel"
  confirmColor="error"
  onConfirm={() => {
    // 执行删除
    setOpen(false)
  }}
  onCancel={() => setOpen(false)}
/>
```

**Props**:
- `open: boolean` - 是否显示（必填）
- `title: string` - 对话框标题（必填）
- `message: string` - 确认消息（必填）
- `onConfirm: () => void` - 确认回调（必填）
- `onCancel: () => void` - 取消回调（必填）
- `confirmText?: string` - 确认按钮文本（默认 "Confirm"）
- `cancelText?: string` - 取消按钮文本（默认 "Cancel"）
- `confirmColor?: 'error' | 'primary' | ...` - 确认按钮颜色

---

### 5. EmptyState - 空状态
用于列表为空、搜索无结果等场景。

```typescript
import InboxIcon from '@mui/icons-material/Inbox'

<EmptyState
  icon={<InboxIcon sx={{ fontSize: 64 }} />}
  message="No items found. Create your first item to get started."
  action={{
    label: 'Create Item',
    onClick: () => navigate('/create'),
  }}
/>
```

**Props**:
- `message: string` - 提示文本（必填）
- `icon?: ReactNode` - 图标
- `action?: { label: string; onClick: () => void }` - 操作按钮

---

### 6. ErrorState - 错误状态
用于 API 失败、加载错误等场景。

```typescript
<ErrorState
  error="Failed to load data from server."
  onRetry={() => refetch()}
  retryText="Retry"
/>

// 也支持 Error 对象
<ErrorState
  error={new Error('Network timeout')}
  onRetry={() => refetch()}
/>
```

**Props**:
- `error: string | Error` - 错误信息（必填）
- `onRetry?: () => void` - 重试回调
- `retryText?: string` - 重试按钮文本（默认 "Retry"）

---

### 7. LoadingState - 加载状态
用于全页或区块加载中的状态展示。

```typescript
<LoadingState
  message="Loading components..."
  size={40}
/>
```

**Props**:
- `message?: string` - 提示文本（默认 "Loading..."）
- `size?: number` - 加载动画尺寸（默认 40）

---

## 设计原则

### ✅ 无业务逻辑
- 不调用 API
- 不访问全局状态
- 不包含领域模型

### ✅ 纯 UI 组件
- 只负责展示和基础交互
- 通过 props 接收数据和回调
- 可独立使用

### ✅ 完整 TypeScript 类型
- 每个组件有完整的 Props interface
- 所有类型均已导出
- 无 `any` 类型

### ✅ MUI + Tailwind 协作
- MUI 提供核心组件（Button, Card, Dialog 等）
- Tailwind 用于布局和间距（flex, gap, py-12 等）

---

## 组件展示页

访问 `http://localhost:5174/components` 查看所有组件的实际效果。

---

## 文件结构

```
components/
├── PageHeader.tsx          # 页面头部
├── SectionCard.tsx         # 卡片容器
├── DataTable.tsx           # 数据表格
├── ConfirmDialog.tsx       # 确认对话框
├── EmptyState.tsx          # 空状态
├── ErrorState.tsx          # 错误状态
├── LoadingState.tsx        # 加载状态
├── index.ts                # 统一导出
├── __test-types.ts         # 类型验证
└── README.md               # 本文档
```

---

## 扩展建议

如需添加新组件，请遵循以下规范：

1. **文件名**: 使用 PascalCase（如 `MyComponent.tsx`）
2. **导出方式**: 命名导出 + Props 类型导出
3. **Props 定义**: 使用 `interface`，命名为 `${ComponentName}Props`
4. **文档注释**: 添加组件功能说明
5. **无业务逻辑**: 保持组件纯净
6. **更新导出**: 在 `index.ts` 中添加导出

### 示例
```typescript
export interface MyComponentProps {
  title: string
  onClick: () => void
}

/**
 * MyComponent - 组件功能说明
 */
export function MyComponent({ title, onClick }: MyComponentProps) {
  return (
    <Button onClick={onClick}>
      {title}
    </Button>
  )
}
```

然后在 `index.ts` 中添加：
```typescript
export { MyComponent } from './MyComponent'
export type { MyComponentProps } from './MyComponent'
```
