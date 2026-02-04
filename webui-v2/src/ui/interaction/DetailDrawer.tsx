/**
 * DetailDrawer - 详情统一抽屉
 *
 * 🔒 硬契约：所有详情查看必须使用此组件
 *
 * 目标：
 * - 统一抽屉宽度（600px）
 * - 统一 header 样式（标题 + 关闭按钮）
 * - 统一内边距
 * - 统一 footer 操作区（可选）
 */

import { useRef, useEffect } from 'react'
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Divider,
} from '@mui/material'
import { K, useTextTranslation } from '@/ui/text'
import { CloseIcon } from '@/ui/icons'

export interface DetailDrawerProps {
  /**
   * 抽屉是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 抽屉标题
   */
  title: string

  /**
   * 副标题（可选）
   */
  subtitle?: string

  /**
   * 抽屉宽度（默认 600px）
   */
  width?: number

  /**
   * Footer 操作区（可选）
   */
  actions?: React.ReactNode

  /**
   * 详情内容
   */
  children: React.ReactNode
}

/**
 * DetailDrawer 组件
 *
 * 🔒 详情查看必须使用此组件
 *
 * 特性：
 * - 默认 600px 宽度（适合详情展示）
 * - 右侧滑出
 * - Header: 标题 + 副标题 + 关闭按钮
 * - Content: 自动滚动
 * - Footer: 可选操作区（编辑/删除等）
 *
 * @example
 * ```tsx
 * <DetailDrawer
 *   open={open}
 *   onClose={handleClose}
 *   title="Task Detail"
 *   subtitle="#12345"
 *   actions={
 *     <>
 *       <Button onClick={handleEdit}>Edit</Button>
 *       <Button onClick={handleDelete} color="error">Delete</Button>
 *     </>
 *   }
 * >
 *   <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
 *     <Box>
 *       <Typography variant="caption" color="text.secondary">Name</Typography>
 *       <Typography variant="body1">Sample Task</Typography>
 *     </Box>
 *     <Box>
 *       <Typography variant="caption" color="text.secondary">Status</Typography>
 *       <Typography variant="body1">Active</Typography>
 *     </Box>
 *   </Box>
 * </DetailDrawer>
 * ```
 */
export function DetailDrawer({
  open,
  onClose,
  title,
  subtitle,
  width = 600,
  actions,
  children,
}: DetailDrawerProps) {
  const { t } = useTextTranslation()
  // ===================================
  // 🔒 修复策略4A：显式焦点保存和恢复
  // ===================================
  // 保存打开前的焦点元素
  const lastActiveElementRef = useRef<HTMLElement | null>(null)

  // Drawer打开时保存当前焦点
  useEffect(() => {
    if (open) {
      // 保存打开前的焦点元素
      lastActiveElementRef.current = document.activeElement as HTMLElement
    }
  }, [open])

  // 处理Drawer关闭，显式恢复焦点
  const handleClose = () => {
    // ===================================
    // 🔒 关键修复：在 onClose 前立即恢复焦点
    // ===================================
    // 避免在关闭动画期间焦点留在被 aria-hidden 的 Drawer 内

    // 首先，强制blur当前焦点元素（如果在Drawer内）
    const currentFocus = document.activeElement as HTMLElement
    if (currentFocus && typeof currentFocus.blur === 'function') {
      try {
        currentFocus.blur()
      } catch (e) {
        // ignore
      }
    }

    // 然后，尝试恢复到原始触发元素
    if (lastActiveElementRef.current && typeof lastActiveElementRef.current.focus === 'function') {
      try {
        lastActiveElementRef.current.focus()
      } catch (e) {
        // 恢复失败，尝试fallback到body（避免焦点留在Drawer内）
        console.warn('Failed to restore focus to last active element:', e)
        try {
          document.body.focus()
        } catch (e2) {
          // 最后的fallback：让焦点自然丢失
        }
      }
    } else {
      // 没有保存的焦点元素，强制blur到body
      try {
        document.body.focus()
      } catch (e) {
        // ignore
      }
    }

    // 然后关闭 Drawer
    onClose()
  }

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={handleClose}
      // ===================================
      // 🔒 焦点管理 - 修复 ARIA 警告
      // ===================================
      // 注意：虽然设置了disableRestoreFocus={false}，但MUI的自动restore
      // 在嵌套overlay场景可能失效，所以我们实现了显式restore（上面）
      disableRestoreFocus={false}  // 保留MUI的自动restore作为fallback
      disableEnforceFocus={false}  // 强制焦点保持在 Drawer 内
      disableAutoFocus={true}      // 🔒 阻止Paper容器自动获得焦点，避免aria-hidden警告
      // ===================================
      // 🔒 z-index 修复 - DetailDrawer 层级管理
      // ===================================
      // AppBar z-index = theme.zIndex.appBar = 1020
      // Dialog/Modal z-index = theme.zIndex.modal = 1040
      // DetailDrawer 使用 modal + 2 = 1042，确保在所有层之上
      sx={{
        zIndex: (theme) => theme.zIndex.modal + 2,  // 1042，高于 Dialog(1040) 和 AppBar(1020)
        '& .MuiDrawer-paper': {
          width,
          maxWidth: '100%',
        },
      }}
      // ===================================
      // 🔒 关键修复：让 Paper 容器完全不可聚焦
      // ===================================
      // MUI Drawer 默认给 Paper 设置 tabIndex={-1}，使其可接收 programmatic focus
      // 这导致焦点可能"落到"Paper上，触发 aria-hidden 警告
      // 通过移除 tabIndex，让 Paper 完全不可聚焦
      PaperProps={{
        // @ts-ignore - MUI types可能不允许tabIndex为null，但运行时有效
        tabIndex: null,  // 移除tabIndex，让Paper不可聚焦
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          p: 3,
          pb: 2,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h6" component="div" gutterBottom>
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        <IconButton
          aria-label={t(K.common.close)}
          onClick={handleClose}
          size="small"
          sx={{ ml: 2, mt: -0.5 }}
        >
          <CloseIcon />
        </IconButton>
      </Box>

      <Divider />

      {/* Content */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 3,
        }}
      >
        {children}
      </Box>

      {/* Footer (optional) */}
      {actions && (
        <>
          <Divider />
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              justifyContent: 'flex-end',
              p: 3,
              pt: 2,
            }}
          >
            {actions}
          </Box>
        </>
      )}
    </Drawer>
  )
}
