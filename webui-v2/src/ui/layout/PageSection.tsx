/**
 * PageSection - 页面内容块
 *
 * 🔒 硬契约：页面 section 间距必须统一
 *
 * 目标：
 * - 统一 section 间距（默认 32px）
 * - 支持 dense 模式（24px）
 * - 支持二级标题（section 内部标题，不是 page header）
 */

import { Box, Typography } from '@mui/material'
import { SECTION_GAP, spacing } from './tokens'

export interface PageSectionProps {
  /**
   * Section 标题（可选）
   */
  title?: React.ReactNode

  /**
   * Section 副标题（可选）
   */
  subtitle?: React.ReactNode

  /**
   * Section 操作按钮（可选）
   */
  actions?: React.ReactNode

  /**
   * 紧凑模式（间距 24px 而不是 32px）
   */
  dense?: boolean

  /**
   * Section 内容
   */
  children: React.ReactNode

  /**
   * 自定义样式（仅允许 marginBottom）
   */
  sx?: { mb?: number }
}

/**
 * PageSection 组件
 *
 * 🔒 强制建议：页面需要"二级标题块"时，只能用 PageSection
 *
 * @example
 * ```tsx
 * <PageSection title="Basic Information">
 *   <FormField label="Name" />
 *   <FormField label="Email" />
 * </PageSection>
 *
 * <PageSection title="Settings" actions={<Button>Edit</Button>}>
 *   <SettingsContent />
 * </PageSection>
 * ```
 */
export function PageSection({
  title,
  subtitle,
  actions,
  dense = false,
  children,
  sx,
}: PageSectionProps) {
  const mb = sx?.mb ?? (dense ? spacing.s5 : SECTION_GAP) / 8 // MUI uses 8px base

  return (
    <Box sx={{ mb }}>
      {/* Section Header（可选） */}
      {(title || subtitle || actions) && (
        <Box
          sx={{
            mb: 2,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: 2,
          }}
        >
          {/* 标题区 */}
          {(title || subtitle) && (
            <Box sx={{ minWidth: 0, flex: 1 }}>
              {title && (
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 600,
                    lineHeight: 1.3,
                    color: 'text.primary',
                  }}
                >
                  {title}
                </Typography>
              )}
              {subtitle && (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 0.5 }}
                >
                  {subtitle}
                </Typography>
              )}
            </Box>
          )}

          {/* 操作区 */}
          {actions && (
            <Box
              sx={{
                flexShrink: 0,
                display: 'flex',
                gap: 1,
                alignItems: 'center',
              }}
            >
              {actions}
            </Box>
          )}
        </Box>
      )}

      {/* Section Content */}
      {children}
    </Box>
  )
}
