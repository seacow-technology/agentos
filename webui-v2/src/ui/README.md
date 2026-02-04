# UI Component Library - WebUIv2

这是 WebUIv2 的 UI 组件封装层，提供基于 Material Design 3 的统一组件库。

## 📋 设计原则

1. **唯一入口**：所有 UI 组件必须从 `@/ui` 导入
2. **禁止直接使用 MUI**：不允许页面直接 import `@mui/material` 或 `@mui/x-data-grid`
3. **样式统一**：不允许在页面中使用 `sx` 或 `style` 属性自定义组件样式
4. **主题控制**：所有样式由主题统一管理

## 📦 组件分类

### Buttons (控制按钮)
- `PrimaryButton` - 主要操作按钮
- `SecondaryButton` - 次要操作按钮
- `DangerButton` - 危险操作按钮
- `IconOnlyButton` - 纯图标按钮
- `ButtonWithIcon` - 图标文字按钮

### Forms (表单控件)
- `TextInput` - 文本输入框
- `SelectInput` - 下拉选择框
- `FormField` - 表单字段容器

### Surfaces (容器)
- `AppCard` - 卡片容器
- `AppCardHeader` - 卡片头部
- `AppCardBody` - 卡片内容区

### Data (数据展示)
- `AppTable` - 数据表格
- `TableToolbar` - 表格工具栏

### States (状态)
- `EmptyState` - 空状态
- `ErrorState` - 错误状态
- `LoadingState` - 加载状态

## 🚀 快速开始

### 导入组件

```tsx
import {
  PrimaryButton,
  SecondaryButton,
  AppCard,
  AppCardHeader,
  AppCardBody,
  TextInput,
  SelectInput,
  AppTable,
  TableToolbar,
} from '@/ui'
```

### 按钮示例

```tsx
// 主要操作
<PrimaryButton onClick={handleSave}>
  Save Changes
</PrimaryButton>

// 次要操作
<SecondaryButton onClick={handleCancel}>
  Cancel
</SecondaryButton>

// 危险操作
<DangerButton onClick={handleDelete}>
  Delete
</DangerButton>

// 图标按钮
<IconOnlyButton tooltip="Edit" onClick={handleEdit}>
  <EditIcon />
</IconOnlyButton>

// 图标文字按钮
<ButtonWithIcon icon={<AddIcon />} onClick={handleCreate}>
  Create New
</ButtonWithIcon>
```

### 表单示例

```tsx
function MyForm() {
  const [name, setName] = useState('')
  const [status, setStatus] = useState('')

  return (
    <>
      <TextInput
        label="Name"
        value={name}
        onChange={setName}
        required
      />

      <SelectInput
        label="Status"
        value={status}
        onChange={setStatus}
        options={[
          { value: 'active', label: 'Active' },
          { value: 'inactive', label: 'Inactive' },
        ]}
      />
    </>
  )
}
```

### 卡片示例

```tsx
<AppCard>
  <AppCardHeader
    title="User Profile"
    subtitle="Manage your account"
    action={
      <IconOnlyButton tooltip="Edit">
        <EditIcon />
      </IconOnlyButton>
    }
  />
  <AppCardBody>
    <p>Content goes here</p>
  </AppCardBody>
</AppCard>
```

### 表格示例

```tsx
function UsersPage() {
  const [search, setSearch] = useState('')
  const { data, isLoading, error, refetch } = useUsers()

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 90 },
    { field: 'name', headerName: 'Name', flex: 1 },
    { field: 'email', headerName: 'Email', flex: 1 },
  ]

  return (
    <>
      <TableToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search users..."
        actions={
          <PrimaryButton onClick={handleCreate}>
            Create User
          </PrimaryButton>
        }
      />

      <AppTable
        rows={data}
        columns={columns}
        loading={isLoading}
        error={error}
        onRetry={refetch}
        checkboxSelection
      />
    </>
  )
}
```

## 🎨 主题和 Tokens

```tsx
import { theme, tokens } from '@/ui'

// 使用 theme
<ThemeProvider theme={theme}>
  <App />
</ThemeProvider>

// 使用 tokens
const spacing = tokens.spacing.md // 16px
const radius = tokens.radius.md   // 8px
const elevation = tokens.elevation.card // 阴影值
```

## 📋 Props 限制

### 禁止的 Props
- ❌ `sx` - 不允许自定义样式
- ❌ `style` - 不允许内联样式
- ❌ `className` - 应由主题控制

### 允许的 Props
- ✅ 功能性 props (`onClick`, `onChange`, etc.)
- ✅ 状态 props (`disabled`, `loading`, `error`, etc.)
- ✅ 内容 props (`children`, `label`, `placeholder`, etc.)
- ✅ 尺寸/变体 props (`size`, `variant`, etc.)

## 🔍 组件展示页

访问以下路由查看组件展示：

- `/lab` - 组件展示索引
- `/lab/buttons` - 按钮组件展示
- `/lab/cards` - 卡片组件展示
- `/lab/tables` - 表格组件展示

## ⚠️ 常见错误

### ❌ 错误做法

```tsx
// 直接导入 MUI 组件
import { Button } from '@mui/material'

// 使用 sx 自定义样式
<PrimaryButton sx={{ color: 'red' }}>
  Button
</PrimaryButton>

// 使用内联样式
<AppCard style={{ padding: 24 }}>
  Content
</AppCard>
```

### ✅ 正确做法

```tsx
// 从 @/ui 导入
import { PrimaryButton, AppCard } from '@/ui'

// 使用组件默认样式
<PrimaryButton onClick={handleClick}>
  Button
</PrimaryButton>

// 使用预定义的变体
<AppCard variant="outlined">
  Content
</AppCard>
```

## 📚 进阶用法

### react-hook-form 集成

```tsx
import { useForm, Controller } from 'react-hook-form'
import { TextInput, FormField } from '@/ui'

function MyForm() {
  const { control, formState: { errors } } = useForm()

  return (
    <Controller
      name="email"
      control={control}
      rules={{ required: 'Email is required' }}
      render={({ field }) => (
        <FormField
          label="Email"
          error={errors.email?.message}
          required
        >
          <TextInput {...field} type="email" />
        </FormField>
      )}
    />
  )
}
```

### 自定义表格操作列

```tsx
const columns: GridColDef[] = [
  { field: 'name', headerName: 'Name', flex: 1 },
  {
    field: 'actions',
    headerName: 'Actions',
    width: 120,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <IconOnlyButton
          size="small"
          tooltip="Edit"
          onClick={() => handleEdit(params.row.id)}
        >
          <EditIcon fontSize="small" />
        </IconOnlyButton>
        <IconOnlyButton
          size="small"
          color="error"
          tooltip="Delete"
          onClick={() => handleDelete(params.row.id)}
        >
          <DeleteIcon fontSize="small" />
        </IconOnlyButton>
      </Box>
    ),
  },
]
```

## 🛠️ 开发指南

### 添加新组件

1. 在对应目录创建组件文件
2. 导出组件和类型
3. 在 `ui/index.ts` 中统一导出
4. 创建展示页面验证功能
5. 更新本文档

### 组件设计原则

1. **单一职责**：每个组件只做一件事
2. **最小 API**：只暴露必要的 props
3. **类型安全**：完整的 TypeScript 类型定义
4. **无副作用**：组件应是纯展示组件
5. **可测试**：易于单元测试和集成测试

## 📝 文件结构

```
src/ui/
├── theme/              # 主题配置
│   ├── theme.ts        # MUI 主题
│   ├── components.ts   # 组件样式覆盖
│   └── dataGridStyles.ts
├── tokens/             # 设计 tokens
│   └── tokens.ts
├── icons/              # 图标导出
│   └── index.ts
├── controls/           # 控制组件
│   ├── buttons/        # 按钮组件
│   └── forms/          # 表单组件
├── surfaces/           # 容器组件
│   └── AppCard/        # 卡片组件
├── data/               # 数据组件
│   └── AppTable/       # 表格组件
├── index.ts            # 统一导出
└── README.md           # 本文档
```

## 🤝 贡献指南

1. 遵循现有组件的结构和命名规范
2. 确保所有组件有完整的 TypeScript 类型
3. 添加 JSDoc 注释说明组件用途
4. 创建展示页面验证功能
5. 更新相关文档

## 📄 许可证

Internal use only - AgentOS WebUIv2
