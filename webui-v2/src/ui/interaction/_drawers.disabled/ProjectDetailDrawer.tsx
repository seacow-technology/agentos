/**
 * ProjectDetailDrawer - 项目详情抽屉
 *
 * 基于 DetailDrawer 封装的项目详情展示
 * 遵循 G7-G17 规范，使用 t(K.xxx) 多语言
 */

import { Box, Typography, Chip, Button } from '@mui/material'
import { DetailDrawer } from '../DetailDrawer'
import { K, t } from '@/ui/text'
import type { GetProjectResponse } from '@/modules/agentos/dto'

export interface ProjectDetailDrawerProps {
  /**
   * 抽屉是否打开
   */
  open: boolean

  /**
   * 关闭回调
   */
  onClose: () => void

  /**
   * 项目数据
   */
  project: GetProjectResponse | null

  /**
   * 编辑回调（可选）
   */
  onEdit?: () => void

  /**
   * 删除回调（可选）
   */
  onDelete?: () => void

  /**
   * 是否正在加载
   */
  loading?: boolean
}

/**
 * ProjectDetailDrawer 组件
 *
 * 功能：
 * - 展示项目完整信息
 * - 显示关联的仓库列表
 * - 显示项目标签
 * - 提供编辑和删除操作
 *
 * @example
 * ```tsx
 * <ProjectDetailDrawer
 *   open={open}
 *   onClose={handleClose}
 *   project={projectData}
 *   onEdit={handleEdit}
 *   onDelete={handleDelete}
 * />
 * ```
 */
export function ProjectDetailDrawer({
  open,
  onClose,
  project,
  onEdit,
  onDelete,
  loading = false,
}: ProjectDetailDrawerProps) {
  if (!project) {
    return null
  }

  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      title={project.name}
      subtitle={`#${project.project_id}`}
      actions={
        <>
          {onEdit && (
            <Button onClick={onEdit} variant="outlined">
              {t(K.common.edit)}
            </Button>
          )}
          {onDelete && (
            <Button onClick={onDelete} variant="outlined" color="error">
              {t(K.common.delete)}
            </Button>
          )}
        </>
      }
    >
      {loading ? (
        <Typography>{t(K.common.loading)}</Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* 基本信息 */}
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {t(K.component.drawer.description)}
            </Typography>
            <Typography variant="body1">
              {project.description || t(K.component.drawer.noDescription)}
            </Typography>
          </Box>

          {/* 状态 */}
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {t(K.component.drawer.status)}
            </Typography>
            <Chip
              label={project.status}
              size="small"
              color={project.status === 'active' ? 'success' : 'default'}
            />
          </Box>

          {/* 标签 */}
          {project.tags && project.tags.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.component.drawer.tags)}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                {project.tags.map((tag) => (
                  <Chip key={tag} label={tag} size="small" variant="outlined" />
                ))}
              </Box>
            </Box>
          )}

          {/* 统计信息 */}
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {t(K.component.drawer.repositories)}
            </Typography>
            <Typography variant="body1">{project.repos_count || 0}</Typography>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {t(K.component.drawer.recentTasks)}
            </Typography>
            <Typography variant="body1">{project.recent_tasks_count || 0}</Typography>
          </Box>

          {/* 工作目录 */}
          {project.default_workdir && (
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.component.drawer.defaultWorkdir)}
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  bgcolor: 'action.hover',
                  p: 1,
                  borderRadius: 1,
                }}
              >
                {project.default_workdir}
              </Typography>
            </Box>
          )}

          {/* 时间信息 */}
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              {t(K.component.drawer.createdAt)}
            </Typography>
            <Typography variant="body2">
              {new Date(project.created_at).toLocaleString()}
            </Typography>
          </Box>

          {project.updated_at && (
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.component.drawer.updatedAt)}
              </Typography>
              <Typography variant="body2">
                {new Date(project.updated_at).toLocaleString()}
              </Typography>
            </Box>
          )}

          {/* 仓库列表 */}
          {project.repos && project.repos.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.component.drawer.repositoryList)}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                {project.repos.map((repo) => (
                  <Box
                    key={repo.repo_id}
                    sx={{
                      p: 1.5,
                      border: 1,
                      borderColor: 'divider',
                      borderRadius: 1,
                    }}
                  >
                    <Typography variant="body2" fontWeight="medium">
                      {repo.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {repo.role} • {repo.workspace_relpath}
                    </Typography>
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      )}
    </DetailDrawer>
  )
}
