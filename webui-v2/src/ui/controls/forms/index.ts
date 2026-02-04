/**
 * Form Components
 *
 * Material Design 3 表单组件封装层。
 *
 * 设计原则：
 * - 禁止页面直接 import @mui/material/TextField|Select
 * - 所有表单样式由主题统一控制
 * - 支持 react-hook-form 集成（通过 ref 转发）
 * - 统一的 onChange 接口（直接传值而非事件）
 *
 * 组件列表：
 * - TextInput: 文本输入框（TextField wrapper）
 * - SelectInput: 下拉选择框（Select wrapper）
 * - FormField: 表单字段容器（标签+错误提示）
 *
 * react-hook-form 集成示例：
 * ```tsx
 * import { useForm, Controller } from 'react-hook-form'
 * import { TextInput, FormField } from '@/ui'
 *
 * function MyForm() {
 *   const { control, formState: { errors } } = useForm()
 *
 *   return (
 *     <Controller
 *       name="email"
 *       control={control}
 *       rules={{ required: 'Email is required' }}
 *       render={({ field }) => (
 *         <FormField
 *           label="Email"
 *           error={errors.email?.message}
 *           required
 *         >
 *           <TextInput
 *             {...field}
 *             type="email"
 *           />
 *         </FormField>
 *       )}
 *     />
 *   )
 * }
 * ```
 *
 * 使用方式（简单场景）：
 * ```tsx
 * import { TextInput, SelectInput } from '@/ui'
 *
 * function MyPage() {
 *   const [name, setName] = useState('')
 *   const [status, setStatus] = useState('')
 *
 *   return (
 *     <>
 *       <TextInput
 *         label="Name"
 *         value={name}
 *         onChange={setName}
 *         required
 *       />
 *       <SelectInput
 *         label="Status"
 *         value={status}
 *         onChange={setStatus}
 *         options={statusOptions}
 *       />
 *     </>
 *   )
 * }
 * ```
 */

export { TextInput } from './TextInput'
export { SelectInput } from './SelectInput'
export { FormField } from './FormField'

export type { TextInputProps } from './TextInput'
export type { SelectInputProps, SelectOption } from './SelectInput'
export type { FormFieldProps } from './FormField'
