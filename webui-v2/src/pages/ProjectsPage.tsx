/**
 * ProjectsPage - 项目管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Real API Integration: agentosService (Phase 6)
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
// eslint-disable-next-line no-restricted-imports -- G3 Exception: Grid is explicitly allowed
import { Grid } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem } from '@/ui'
import { DialogForm } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import type { GridColDef } from '@/ui'
import { agentosService, type Project } from '@/services/agentos.service'
import { useSnackbar } from 'notistack'

// Constants for prop values
const SIZE_SMALL = 'small' as const
const VALUE_ALL = 'all' as const
const VALUE_ACTIVE = 'active' as const
const VALUE_MAINTENANCE = 'maintenance' as const
const VALUE_ARCHIVED = 'archived' as const
const VALUE_CODE = 'code' as const
const VALUE_DOCS = 'docs' as const
const VALUE_INFRA = 'infra' as const
const VALUE_MONO_SUBDIR = 'mono-subdir' as const
const LABEL_PROJECT = 'Project' as const
const LABEL_ACTIVE = 'Active' as const
const LABEL_MAINTENANCE = 'Maintenance' as const
const LABEL_ARCHIVED = 'Archived' as const

/**
 * Display Project for Table
 */
interface DisplayProject {
  id: string
  name: string
  description: string
  repoCount: number
  status: string
  owner: string
  lastActivity: string
}

/**
 * ProjectsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function ProjectsPage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()
  const { enqueueSnackbar } = useSnackbar()

  // ===================================
  // State (Data Management)
  // ===================================
  const [loading, setLoading] = useState(true)
  const [projects, setProjects] = useState<DisplayProject[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)

  // ===================================
  // State (Filter)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>(VALUE_ALL)

  // ===================================
  // State (Add Repo Dialog)
  // ===================================
  const [addRepoDialogOpen, setAddRepoDialogOpen] = useState(false)
  const [repoUrl, setRepoUrl] = useState('')
  const [repoBranch, setRepoBranch] = useState('main')
  const [repoType, setRepoType] = useState<string>(VALUE_CODE)
  const [repoSubmitting, setRepoSubmitting] = useState(false)

  // ===================================
  // State (Selected Project for Repo)
  // ===================================
  const [selectedProjectId, setSelectedProjectId] = useState<string>('')

  // ===================================
  // State (Create Project Dialog)
  // ===================================
  const [createProjectDialogOpen, setCreateProjectDialogOpen] = useState(false)
  const [projectName, setProjectName] = useState('')
  const [projectDescription, setProjectDescription] = useState('')
  const [projectWorkdir, setProjectWorkdir] = useState('')
  const [projectTags, setProjectTags] = useState('')
  const [projectSubmitting, setProjectSubmitting] = useState(false)

  // ===================================
  // Data Fetching
  // ===================================
  const fetchProjects = async () => {
    try {
      setLoading(true)

      // Fetch projects with pagination
      const params: { page?: number; limit?: number; status?: string } = {
        page: page + 1, // API uses 1-based indexing
        limit: pageSize,
      }

      // Add status filter if not 'all'
      if (statusFilter !== VALUE_ALL) {
        params.status = statusFilter
      }

      const response = await agentosService.listProjects(params)

      // Fetch repo count for each project in parallel
      const projectsWithRepos = await Promise.all(
        response.projects.map(async (project: Project, index: number) => {
          // Ensure valid id - use fallback if API returns invalid data
          const validId = project.id || `project-${index}-${Date.now()}`

          try {
            const reposRes = await agentosService.getProjectRepos(validId)
            return {
              id: validId,
              name: project.name || 'Unnamed Project',
              description: project.description || '-',
              repoCount: reposRes.total,
              status: project.status || 'unknown',
              owner: '-', // API doesn't provide owner field yet
              lastActivity: project.updated_at
                ? new Date(project.updated_at).toLocaleDateString('en-CA')
                : new Date(project.created_at).toLocaleDateString('en-CA'),
            }
          } catch (error) {
            console.error(`Failed to fetch repos for project ${validId}:`, error)
            return {
              id: validId,
              name: project.name || 'Unnamed Project',
              description: project.description || '-',
              repoCount: 0,
              status: project.status || 'unknown',
              owner: '-',
              lastActivity: project.updated_at
                ? new Date(project.updated_at).toLocaleDateString('en-CA')
                : new Date(project.created_at).toLocaleDateString('en-CA'),
            }
          }
        })
      )

      setProjects(projectsWithRepos)
      setTotal(response.total)
    } catch (error) {
      console.error('Failed to fetch projects:', error)
      enqueueSnackbar(t('common.error') + ': Failed to load projects', { variant: 'error' })
      setProjects([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, statusFilter])

  // ===================================
  // Handlers
  // ===================================
  const handleRefresh = async () => {
    enqueueSnackbar(t('common.loading') + '...', { variant: 'info' })
    await fetchProjects()
    enqueueSnackbar(t('common.success'), { variant: 'success' })
  }

  const handleSearch = () => {
    // Trigger search by resetting page
    setPage(0)
    fetchProjects()
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setStatusFilter(VALUE_ALL)
    setPage(0)
  }

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.projects.title'),
    subtitle: t('page.projects.subtitle'),
  })

  usePageActions([
    {
      key: 'createProject',
      label: t(K.page.projects.createProject),
      variant: 'contained',
      onClick: () => {
        setCreateProjectDialogOpen(true)
      },
    },
    {
      key: 'addRepo',
      label: t(K.page.projects.addRepo),
      variant: 'outlined',
      onClick: () => {
        // Select first project if available
        if (projects.length > 0) {
          setSelectedProjectId(projects[0].id)
        }
        setAddRepoDialogOpen(true)
      },
    },
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: handleRefresh,
    },
  ])

  // ===================================
  // Create Project Handler
  // ===================================
  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      enqueueSnackbar(t('common.error') + ': Project name is required', { variant: 'error' })
      return
    }

    try {
      setProjectSubmitting(true)

      // Prepare request data
      const createData: {
        name: string
        description?: string
        tags?: string[]
        default_workdir?: string
      } = {
        name: projectName.trim(),
      }

      if (projectDescription.trim()) {
        createData.description = projectDescription.trim()
      }

      if (projectWorkdir.trim()) {
        createData.default_workdir = projectWorkdir.trim()
      }

      if (projectTags.trim()) {
        createData.tags = projectTags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean)
      }

      const response = await agentosService.createProject(createData)

      enqueueSnackbar(t('common.success') + ': Project created successfully', { variant: 'success' })
      setCreateProjectDialogOpen(false)

      // Reset form
      setProjectName('')
      setProjectDescription('')
      setProjectWorkdir('')
      setProjectTags('')

      // Refresh projects list
      await fetchProjects()

      // Auto-select the newly created project
      if (response.project?.id) {
        setSelectedProjectId(response.project.id)
      }
    } catch (error) {
      console.error('Failed to create project:', error)
      enqueueSnackbar(t('common.error') + ': Failed to create project', { variant: 'error' })
    } finally {
      setProjectSubmitting(false)
    }
  }

  // ===================================
  // Add Repo Handler
  // ===================================
  const handleAddRepo = async () => {
    if (!selectedProjectId) {
      enqueueSnackbar(t('common.error') + ': No project selected', { variant: 'error' })
      return
    }

    if (!repoUrl.trim()) {
      enqueueSnackbar(t('common.error') + ': Repository URL is required', { variant: 'error' })
      return
    }

    try {
      setRepoSubmitting(true)

      // Extract repo name from URL (simplified logic)
      const repoName = repoUrl.split('/').pop()?.replace('.git', '') || 'unknown-repo'

      await agentosService.createProjectRepo(selectedProjectId, {
        project_id: selectedProjectId,
        name: repoName,
        path: repoUrl,
        url: repoUrl,
      })

      enqueueSnackbar(t(K.page.projects.repoAddedSuccess), { variant: 'success' })
      setAddRepoDialogOpen(false)

      // Reset form
      setRepoUrl('')
      setRepoBranch('main')
      setRepoType(VALUE_CODE)

      // Refresh projects to update repo count
      await fetchProjects()
    } catch (error) {
      console.error('Failed to add repository:', error)
      enqueueSnackbar(t('common.error') + ': Failed to add repository', { variant: 'error' })
    } finally {
      setRepoSubmitting(false)
    }
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.projects.columnId),
      width: 80,
    },
    {
      field: 'name',
      headerName: t(K.page.projects.columnName),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'description',
      headerName: t(K.page.projects.columnDescription),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'repoCount',
      headerName: t(K.page.projects.columnRepoCount),
      width: 120,
    },
    {
      field: 'status',
      headerName: t('form.field.status'),
      width: 120,
    },
    {
      field: 'owner',
      headerName: t(K.page.projects.columnOwner),
      width: 150,
    },
    {
      field: 'lastActivity',
      headerName: t(K.page.projects.columnLastActivity),
      width: 130,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
      loading={loading}
      rows={projects}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t('form.placeholder.search')}
                  fullWidth
                  size={SIZE_SMALL}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleSearch()
                    }
                  }}
                />
              ),
            },
            {
              width: 6,
              component: (
                <Select
                  label={t('form.field.status')}
                  fullWidth
                  size={SIZE_SMALL}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value={VALUE_ALL}>{t('common.all')}</MenuItem>
                  <MenuItem value={VALUE_ACTIVE}>{LABEL_ACTIVE}</MenuItem>
                  <MenuItem value={VALUE_MAINTENANCE}>{LABEL_MAINTENANCE}</MenuItem>
                  <MenuItem value={VALUE_ARCHIVED}>{LABEL_ARCHIVED}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'search',
              label: t('common.search'),
              onClick: handleSearch,
            },
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: handleResetFilters,
            },
          ]}
        />
      }
      emptyState={{
        title: t('page.projects.noProjects'),
        description: 'Create your first project to get started',
        actions: [
          {
            label: t('page.projects.createProject'),
            onClick: () => {
              setCreateProjectDialogOpen(true)
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page,
        pageSize,
        total,
        onPageChange: (newPage) => setPage(newPage),
      }}
      onRowClick={(row) => {
        console.log('Project row clicked:', row)
        enqueueSnackbar(`Viewing project: ${row.name}`, { variant: 'info' })
      }}
    />

      {/* Create Project Dialog */}
      <DialogForm
        open={createProjectDialogOpen}
        onClose={() => {
          if (!projectSubmitting) {
            setCreateProjectDialogOpen(false)
            setProjectName('')
            setProjectDescription('')
            setProjectWorkdir('')
            setProjectTags('')
          }
        }}
        title={t(K.page.projects.createProject)}
        submitText={t('common.create')}
        cancelText={t('common.cancel')}
        onSubmit={handleCreateProject}
        submitDisabled={!projectName.trim() || projectSubmitting}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.component.dialog.projectName)}
              placeholder={t(K.component.dialog.projectNamePlaceholder)}
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              fullWidth
              required
              autoFocus
              disabled={projectSubmitting}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              label={t(K.component.dialog.projectDescription)}
              placeholder={t(K.component.dialog.projectDescriptionPlaceholder)}
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              fullWidth
              multiline
              rows={3}
              disabled={projectSubmitting}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              label={t(K.component.dialog.defaultWorkdir)}
              placeholder={t(K.component.dialog.defaultWorkdirPlaceholder)}
              value={projectWorkdir}
              onChange={(e) => setProjectWorkdir(e.target.value)}
              fullWidth
              disabled={projectSubmitting}
              helperText={t(K.component.dialog.defaultWorkdirHelper)}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              label={t(K.component.dialog.tags)}
              placeholder={t(K.component.dialog.tagsPlaceholder)}
              value={projectTags}
              onChange={(e) => setProjectTags(e.target.value)}
              fullWidth
              disabled={projectSubmitting}
              helperText={t(K.component.dialog.tagsHelper)}
            />
          </Grid>
        </Grid>
      </DialogForm>

      {/* Add Repo Dialog */}
      <DialogForm
        open={addRepoDialogOpen}
        onClose={() => {
          if (!repoSubmitting) {
            setAddRepoDialogOpen(false)
            setRepoUrl('')
            setRepoBranch('main')
            setRepoType(VALUE_CODE)
          }
        }}
        title={t(K.page.projects.dialogTitle)}
        submitText={t('common.add')}
        cancelText={t('common.cancel')}
        onSubmit={handleAddRepo}
        submitDisabled={!repoUrl.trim() || !selectedProjectId || repoSubmitting}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Select
              label={LABEL_PROJECT}
              fullWidth
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              disabled={repoSubmitting}
              required
            >
              {projects.map((project, index) => (
                <MenuItem key={project.id || `project-item-${index}`} value={project.id}>
                  {project.name}
                </MenuItem>
              ))}
            </Select>
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.projects.fieldUrl)}
              placeholder={t(K.page.projects.fieldUrlPlaceholder)}
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              fullWidth
              required
              autoFocus
              disabled={repoSubmitting}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField
              label={t(K.page.projects.fieldBranch)}
              placeholder={t(K.page.projects.fieldBranchPlaceholder)}
              value={repoBranch}
              onChange={(e) => setRepoBranch(e.target.value)}
              fullWidth
              disabled={repoSubmitting}
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <Select
              label={t(K.page.projects.fieldType)}
              fullWidth
              value={repoType}
              onChange={(e) => setRepoType(e.target.value)}
              disabled={repoSubmitting}
            >
              <MenuItem value={VALUE_CODE}>{t(K.page.projects.typeCode)}</MenuItem>
              <MenuItem value={VALUE_DOCS}>{t(K.page.projects.typeDocs)}</MenuItem>
              <MenuItem value={VALUE_INFRA}>{t(K.page.projects.typeInfra)}</MenuItem>
              <MenuItem value={VALUE_MONO_SUBDIR}>{t(K.page.projects.typeMonoSubdir)}</MenuItem>
            </Select>
          </Grid>
        </Grid>
      </DialogForm>
    </>
  )
}
