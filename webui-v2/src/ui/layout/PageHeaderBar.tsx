/**
 * PageHeaderBar - 页面头部浮层条
 *
 * 🔒 v2.3.3: Bar 深度语义 + 内容轨道对齐修复
 *
 * 设计原则：
 * - Bar = Paper（统一 radius/shadow/bg）- Bar 有 elevation，PageHeader 无 elevation
 * - 与 AppBar 之间保持固定 SHELL_GAP
 * - 内容：PageHeader（title/subtitle/actions）
 * - 布局：Paper 只负责 Surface，内层 Box 负责内容对齐
 * - 内容轨道：PageHeader 与 main content 左对齐（共用 PAGE_GUTTER）
 */

import React from 'react'
import { Box, Paper } from '@mui/material'
import { PageHeader, PageHeaderContext } from './PageHeaderProvider'
import { SHELL_SURFACE, SHELL_SURFACE_SX } from './tokens'

/**
 * PageHeaderBar 组件
 *
 * 🎨 外观：与 AppBar 完全一致的 Surface token
 * 📍 位置：AppBar 下方，固定 SHELL_GAP
 * 📦 内容：PageHeader（无皮肤）
 * 🔒 条件渲染：只在页面上报 header 时才显示
 */
export function PageHeaderBar() {
  // 检查是否有 header 内容
  const context = React.useContext(PageHeaderContext)
  const headerData = context?.headerData ?? {}
  const actions = context?.actions ?? []

  // 没有 header 内容时不渲染
  if (!headerData.title && !headerData.subtitle && actions.length === 0) {
    return null
  }

  return (
    <Paper
      elevation={SHELL_SURFACE.elevation}
      sx={{
        // 🎨 ShellSurface 统一 sx（与 AppBar/FooterBar 完全一致）
        ...SHELL_SURFACE_SX,
        bgcolor: 'background.paper',

        // 🎨 v2.3.3: Paper 只负责垂直 padding，横向由内层 Box 控制
        py: 2,
      }}
    >
      {/* 🔒 v2.3.3: 内容轨道对齐 - 与 main content 共用 PAGE_GUTTER */}
      <Box sx={{ px: 3 }}>
        <PageHeader />
      </Box>
    </Paper>
  )
}
