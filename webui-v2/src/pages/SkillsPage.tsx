/**
 * SkillsPage - Skills Management
 *
 * 🔒 Phase 6 - Real API Integration:
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Real API: skillosServiceGen.listSkills()
 * - ✅ State Handling: Loading/Success/Error/Empty
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect, useCallback } from 'react'
// eslint-disable-next-line no-restricted-imports -- Box and Typography are allowed from @mui/material per G3 exceptions
import { Box, Typography, Chip } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem } from '@/ui'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { skillosServiceGen } from '@/services/skillos.service.gen'
import type { GridColDef } from '@/ui'
import type { Skill } from '@modules/skillos'

// ===================================
// Constants
// ===================================
const DEFAULT_PAGE_SIZE = 25
const FILTER_ALL = 'all'
const CHIP_SIZE = 'small'
const PLACEHOLDER_DASH = '-'
const STATUS_ENABLED = 'enabled'
const STATUS_DISABLED = 'disabled'

// ===================================
// UI Row Type (extends Skill with UI-specific fields)
// ===================================
interface SkillRow extends Skill {
  id: string
  category?: string
  description?: string
}

/**
 * SkillsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function SkillsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [loading, setLoading] = useState(false)
  const [skills, setSkills] = useState<SkillRow[]>([])
  const [totalCount, setTotalCount] = useState(0)

  // ===================================
  // State - Pagination
  // ===================================
  const [page, setPage] = useState(0)
  const [pageSize] = useState(DEFAULT_PAGE_SIZE)

  // ===================================
  // State - Filters
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState(FILTER_ALL)

  // ===================================
  // State - Skill Detail
  // ===================================
  const [selectedSkill, setSelectedSkill] = useState<SkillRow | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.skills.title),
    subtitle: t(K.page.skills.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {
        void loadSkills()
      },
    },
    {
      key: 'install',
      label: t(K.page.skills.installSkill),
      variant: 'contained',
      onClick: () => {
        toast.info(t(K.page.skills.installSkillDesc))
      },
    },
  ])

  // ===================================
  // API Call - Load Skills
  // ===================================
  const loadSkills = useCallback(async () => {
    setLoading(true)
    try {
      const response = await skillosServiceGen.listSkills({
        status: statusFilter === FILTER_ALL ? 'all' : (statusFilter as 'enabled' | 'disabled'),
      })

      // Transform Skill to SkillRow
      // Ensure skillsData is always an array (defensive check)
      const skillsData = Array.isArray(response.data) ? response.data : []
      const transformedSkills: SkillRow[] = skillsData.map((skill) => ({
        ...skill,
        id: skill.skill_id,
        category: extractCategory(skill),
        description: extractDescription(skill),
      }))

      setSkills(transformedSkills)
      setTotalCount(transformedSkills.length)
    } catch (error) {
      console.error('[Skills] Failed to load skills:', error)
      toast.error(t(K.error.loadFailed))
      setSkills([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, t])

  // ===================================
  // Helper - Extract Category from Manifest
  // ===================================
  const extractCategory = (skill: Skill): string => {
    if (skill.manifest_json && typeof skill.manifest_json === 'object') {
      const category = skill.manifest_json.category as string | undefined
      if (category) return category
    }
    return 'General'
  }

  // ===================================
  // Helper - Extract Description from Manifest
  // ===================================
  const extractDescription = (skill: Skill): string => {
    if (skill.manifest_json && typeof skill.manifest_json === 'object') {
      const desc = skill.manifest_json.description as string | undefined
      if (desc) return desc
    }
    return PLACEHOLDER_DASH
  }

  // ===================================
  // Effect - Load on mount and filter change
  // ===================================
  useEffect(() => {
    void loadSkills()
  }, [loadSkills])

  // ===================================
  // Handler - Skill Detail
  // ===================================
  const handleRowClick = (row: SkillRow) => {
    setSelectedSkill(row)
    setDetailDrawerOpen(true)
  }

  const handleCloseDetailDrawer = () => {
    setDetailDrawerOpen(false)
    setSelectedSkill(null)
  }

  // ===================================
  // Handler - Apply Filters (Client-side)
  // ===================================
  const filteredSkills = skills.filter((skill) => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const matchesSearch =
        skill.name.toLowerCase().includes(query) ||
        (skill.description && skill.description.toLowerCase().includes(query)) ||
        (skill.category && skill.category.toLowerCase().includes(query))
      if (!matchesSearch) return false
    }

    return true
  })

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'skill_id',
      headerName: t(K.page.skills.columnId),
      width: 200,
    },
    {
      field: 'name',
      headerName: t(K.page.skills.columnName),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'description',
      headerName: t(K.page.skills.columnDescription),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'category',
      headerName: t(K.page.skills.columnCategory),
      width: 130,
    },
    {
      field: 'status',
      headerName: t(K.form.field.status),
      width: 150,
      renderCell: (params) => {
        const statusColors: Record<string, 'success' | 'warning' | 'error'> = {
          [STATUS_ENABLED]: 'success',
          [STATUS_DISABLED]: 'warning',
          imported_disabled: 'error',
        }
        const statusValue = params.value as string
        return (
          <Chip
            label={statusValue}
            color={statusColors[statusValue] || 'default'}
            size={CHIP_SIZE}
          />
        )
      },
    },
    {
      field: 'version',
      headerName: t(K.page.skills.columnVersion),
      width: 120,
    },
    {
      field: 'source_type',
      headerName: t(K.page.skills.columnSource),
      width: 120,
      renderCell: (params) => {
        const value = params.value as string | undefined
        return value || PLACEHOLDER_DASH
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredSkills}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t(K.common.search)}
                    placeholder={t(K.page.skills.searchPlaceholder)}
                    fullWidth
                    size={CHIP_SIZE}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    label={t(K.form.field.status)}
                    fullWidth
                    size={CHIP_SIZE}
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <MenuItem value={FILTER_ALL}>{t(K.page.skills.statusAll)}</MenuItem>
                    <MenuItem value={STATUS_ENABLED}>{t(K.page.skills.statusEnabled)}</MenuItem>
                    <MenuItem value={STATUS_DISABLED}>{t(K.page.skills.statusDisabled)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t(K.common.reset),
                onClick: () => {
                  setSearchQuery('')
                  setStatusFilter(FILTER_ALL)
                },
              },
              {
                key: 'apply',
                label: t(K.common.apply),
                variant: 'contained',
                onClick: () => {
                  toast.info(t(K.common.success))
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.skills.noSkills),
          description: t(K.page.skills.noSkillsDesc),
          actions: [
            {
              label: t(K.page.skills.installSkill),
              onClick: () => {
                toast.info(t(K.page.skills.installSkillDesc))
              },
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page,
          pageSize,
          total: totalCount,
          onPageChange: (newPage: number) => setPage(newPage),
        }}
        onRowClick={handleRowClick}
      />

      {/* Skill Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleCloseDetailDrawer}
        title={t(K.page.skills.skillDetail)}
        subtitle={selectedSkill ? selectedSkill.name : ''}
      >
        {selectedSkill && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Skill ID */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailId)}
              </Typography>
              <Typography variant="body1">{selectedSkill.skill_id || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Name */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailName)}
              </Typography>
              <Typography variant="body1">{selectedSkill.name || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailDescription)}
              </Typography>
              <Typography variant="body1">{selectedSkill.description || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Version */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailVersion)}
              </Typography>
              <Typography variant="body1">{selectedSkill.version || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailStatus)}
              </Typography>
              <Chip
                label={selectedSkill.status}
                color={
                  selectedSkill.status === STATUS_ENABLED
                    ? 'success'
                    : selectedSkill.status === STATUS_DISABLED
                    ? 'warning'
                    : 'error'
                }
                size={CHIP_SIZE}
              />
            </Box>

            {/* Source Type */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailSourceType)}
              </Typography>
              <Typography variant="body1">{selectedSkill.source_type || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Source Ref */}
            {selectedSkill.source_ref && (
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  {t(K.page.skills.detailSourceRef)}
                </Typography>
                <Typography variant="body1">{selectedSkill.source_ref}</Typography>
              </Box>
            )}

            {/* Category */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skills.detailCategory)}
              </Typography>
              <Typography variant="body1">{selectedSkill.category || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Created At */}
            {selectedSkill.created_at && (
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  {t(K.page.skills.detailCreatedAt)}
                </Typography>
                <Typography variant="body1">
                  {new Date(selectedSkill.created_at * 1000).toLocaleString()}
                </Typography>
              </Box>
            )}

            {/* Updated At */}
            {selectedSkill.updated_at && (
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  {t(K.page.skills.detailUpdatedAt)}
                </Typography>
                <Typography variant="body1">
                  {new Date(selectedSkill.updated_at * 1000).toLocaleString()}
                </Typography>
              </Box>
            )}
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
