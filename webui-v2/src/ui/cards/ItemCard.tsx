/**
 * ItemCard - 通用项卡片
 *
 * 🔒 Contract 强制规则：
 * - 统一卡片外观（border/radius/padding/shadow）
 * - 页面禁止自定义卡片样式
 *
 * 使用示例：
 * ```tsx
 * <ItemCard
 *   title={skill.name}
 *   description={skill.description}
 *   meta={[
 *     { key: 'version', label: T.common.version, value: skill.version },
 *     { key: 'author', label: T.common.author, value: skill.author },
 *   ]}
 *   actions={[
 *     { key: 'view', label: T.common.view, onClick: handleView },
 *     { key: 'install', label: T.common.install, variant: 'contained', onClick: handleInstall },
 *   ]}
 * />
 * ```
 */

import React from 'react'
import { Box, Card, CardContent, Typography, Button, Chip, IconButton, Tooltip } from '@mui/material'
import { CARD_PADDING } from '@/ui/layout/tokens'

// ===================================
// Types
// ===================================

export interface ItemCardMeta {
  key: string
  label: string
  value: string | React.ReactNode
}

export interface ItemCardAction {
  key: string
  label: React.ReactNode
  onClick: () => void
  variant?: 'text' | 'outlined' | 'contained'
  disabled?: boolean
  /**
   * 图标（可选）- 提供时将渲染为 IconButton
   */
  icon?: React.ReactNode
  /**
   * Tooltip 文本（可选）
   */
  tooltip?: string
}

export interface ItemCardProps {
  /**
   * 卡片标题
   */
  title: string

  /**
   * 卡片描述（可选）
   */
  description?: string

  /**
   * Meta 信息列表（key-value 对）
   */
  meta?: ItemCardMeta[]

  /**
   * Tags 标签（可选）
   */
  tags?: string[]

  /**
   * 操作按钮
   */
  actions?: ItemCardAction[]

  /**
   * 点击卡片回调（可选）
   */
  onClick?: () => void

  /**
   * 图标/Logo（可选）
   */
  icon?: React.ReactNode

  /**
   * 自定义页脚内容（可选）
   */
  footer?: React.ReactNode
}

// ===================================
// Component
// ===================================

/**
 * ItemCard 组件
 *
 * 🎨 结构（强制）：
 * - Header: icon + title
 * - Body: description
 * - Meta: key-value 列表
 * - Tags: Chip 列表
 * - Actions: 按钮组
 *
 * 🔒 页面禁止自定义卡片结构
 */
export function ItemCard({
  title,
  description,
  meta,
  tags,
  actions,
  onClick,
  icon,
  footer,
}: ItemCardProps) {
  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s',
        '&:hover': onClick ? {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        } : {},
      }}
      onClick={onClick}
    >
      <CardContent
        sx={{
          p: CARD_PADDING / 8,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header: Icon + Title */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
          {icon && (
            <Box sx={{ flexShrink: 0, color: 'primary.main' }}>
              {icon}
            </Box>
          )}
          <Typography variant="h6" sx={{ fontWeight: 600, flex: 1 }}>
            {title}
          </Typography>
        </Box>

        {/* Description */}
        {description && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mb: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {description}
          </Typography>
        )}

        {/* Meta */}
        {meta && meta.length > 0 && (
          <Box sx={{ mb: 2 }}>
            {meta.map((item) => (
              <Box
                key={item.key}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  mb: 0.5,
                }}
              >
                <Typography variant="caption" color="text.secondary">
                  {item.label}:
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 500 }}>
                  {item.value}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Tags */}
        {tags && tags.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
            {tags.map((tag, index) => (
              <Chip key={index} label={tag} size="small" />
            ))}
          </Box>
        )}

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Actions */}
        {actions && actions.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1, mt: 2, justifyContent: 'flex-end' }}>
            {actions.map((action) => {
              // 如果提供了 icon，渲染 IconButton with Tooltip
              if (action.icon) {
                const iconButton = (
                  <IconButton
                    key={action.key}
                    onClick={(e) => {
                      e.stopPropagation()
                      action.onClick()
                    }}
                    disabled={action.disabled}
                    size="small"
                    color={action.variant === 'contained' ? 'primary' : 'default'}
                  >
                    {action.icon}
                  </IconButton>
                )

                // 如果提供了 tooltip，包装在 Tooltip 中
                return action.tooltip ? (
                  <Tooltip key={action.key} title={action.tooltip}>
                    <span>{iconButton}</span>
                  </Tooltip>
                ) : (
                  iconButton
                )
              }

              // 否则，渲染标准 Button
              return (
                <Button
                  key={action.key}
                  variant={action.variant ?? 'text'}
                  onClick={(e) => {
                    e.stopPropagation()
                    action.onClick()
                  }}
                  disabled={action.disabled}
                  size="small"
                  sx={{ flex: 1 }}
                >
                  {action.label}
                </Button>
              )
            })}
          </Box>
        )}

        {/* Footer */}
        {footer && (
          <Box sx={{ mt: 2 }}>
            {footer}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}
