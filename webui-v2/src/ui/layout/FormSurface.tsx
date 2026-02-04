/**
 * FormSurface - 表单表面组件
 *
 * 🔒 硬契约：表单必须在统一的 surface 中
 *
 * 目标：
 * - 统一表单表面样式（Card/Paper）
 * - 统一表单宽度（720px-860px，居中）
 * - 统一表单内边距
 */

import { Paper } from '@mui/material'
import { FORM_SURFACE_MAX_WIDTH, CARD_PADDING } from './tokens'

export interface FormSurfaceProps {
  /**
   * 表单内容
   */
  children: React.ReactNode

  /**
   * 最大宽度（默认 860px）
   */
  maxWidth?: number

  /**
   * 是否提升阴影（默认 1）
   */
  elevation?: number
}

/**
 * FormSurface 组件
 *
 * 🔒 Form 页面必须使用此组件包裹表单
 *
 * 特性：
 * - 表单表面宽度：720px-860px（居中）
 * - 统一内边距：24px
 * - 统一阴影和圆角
 *
 * @example
 * ```tsx
 * <FormSurface>
 *   <Grid container spacing={2}>
 *     <Grid item xs={12} md={6}>
 *       <TextField label="Name" fullWidth />
 *     </Grid>
 *     <Grid item xs={12} md={6}>
 *       <TextField label="Email" fullWidth />
 *     </Grid>
 *   </Grid>
 * </FormSurface>
 * ```
 */
export function FormSurface({
  children,
  maxWidth = FORM_SURFACE_MAX_WIDTH,
  elevation = 1,
}: FormSurfaceProps) {
  return (
    <Paper
      elevation={elevation}
      sx={{
        // 🔒 表单宽度：720px-860px，居中
        maxWidth,
        mx: 'auto',
        width: '100%',

        // 🔒 统一内边距：24px
        p: CARD_PADDING / 8, // MUI 使用 8px base

        // 圆角
        borderRadius: 1,
      }}
    >
      {children}
    </Paper>
  )
}
