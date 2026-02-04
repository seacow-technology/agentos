/**
 * AuthProfilesPage - 认证配置页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Button, Alert, AlertTitle } from '@/ui'
import { Grid } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DialogForm } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import { systemService } from '@/services/system.service'


/**
 * AuthProfilesPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function AuthProfilesPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [authProfiles, setAuthProfiles] = useState<any[]>([])
  const [filteredProfiles, setFilteredProfiles] = useState<any[]>([])

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [providerFilter, setProviderFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // Dialog State
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [profileName, setProfileName] = useState('')
  const [profileProvider, setProfileProvider] = useState('openai')
  const [profileType, setProfileType] = useState('api-key')

  // ===================================
  // Data Fetching - Real API
  // ===================================
  useEffect(() => {
    const fetchAuthProfiles = async () => {
      setLoading(true)
      setError(null)
      try {
        const response = await systemService.listAuthProfiles()
        setAuthProfiles(response.profiles || [])
      } catch (err) {
        console.error('Failed to fetch auth profiles:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
        setAuthProfiles([])
      } finally {
        setLoading(false)
      }
    }

    fetchAuthProfiles()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.authProfiles.title'),
    subtitle: t('page.authProfiles.subtitle'),
  })

  usePageActions([
    {
      key: 'create',
      label: t('common.add'),
      variant: 'contained',
      onClick: () => {
        setCreateDialogOpen(true)
      },
    },
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        setLoading(true)
        setError(null)
        try {
          const response = await systemService.listAuthProfiles()
          setAuthProfiles(response.profiles || [])
        } catch (err) {
          console.error('Failed to refresh auth profiles:', err)
          setError(err instanceof Error ? err.message : 'Unknown error')
        } finally {
          setLoading(false)
        }
      },
    },
  ])

  // ===================================
  // Filter Logic
  // ===================================
  const applyFilters = () => {
    let filtered = [...authProfiles]

    if (searchQuery) {
      filtered = filtered.filter(p =>
        (p.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.host || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    }

    if (providerFilter !== 'all') {
      filtered = filtered.filter(p =>
        (p.provider || '').toLowerCase() === providerFilter
      )
    }

    if (statusFilter !== 'all') {
      filtered = filtered.filter(p =>
        (p.status || '').toLowerCase() === statusFilter
      )
    }

    setFilteredProfiles(filtered)
  }

  // Apply filters when authProfiles changes
  useEffect(() => {
    applyFilters()
  }, [authProfiles])

  // ===================================
  // Validate Profile Handler
  // ===================================
  const handleValidateProfile = async (profileId: string) => {
    try {
      const response = await systemService.validateAuthProfile(profileId)
      // Update profile status in state
      setAuthProfiles(prev =>
        prev.map(p =>
          p.id === profileId
            ? { ...p, status: response.valid ? 'valid' : 'invalid' }
            : p
        )
      )
    } catch (err) {
      console.error('Failed to validate profile:', err)
      setError(err instanceof Error ? err.message : 'Validation failed')
    }
  }

  // ===================================
  // Dialog Handler
  // ===================================
  const handleCreateSubmit = () => {
    console.log('Create Auth Profile:', {
      name: profileName,
      provider: profileProvider,
      type: profileType,
    })
    // Removed toast
    setCreateDialogOpen(false)
    setProfileName('')
    setProfileProvider('openai')
    setProfileType('api-key')
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 70,
    },
    {
      field: 'name',
      headerName: t('page.authProfiles.name'),
      flex: 1,
      minWidth: 180,
    },
    {
      field: 'host',
      headerName: t('page.authProfiles.host'),
      width: 160,
    },
    {
      field: 'type',
      headerName: t('page.authProfiles.type'),
      width: 100,
    },
    {
      field: 'status',
      headerName: t('page.authProfiles.status'),
      width: 120,
    },
    {
      field: 'created_at',
      headerName: t('page.authProfiles.createdAt'),
      width: 180,
    },
    {
      field: 'actions',
      headerName: t('common.actions'),
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Button
          size="small"
          variant="outlined"
          onClick={(e) => {
            e.stopPropagation()
            handleValidateProfile(params.row.id)
          }}
        >
          {t('common.validate')}
        </Button>
      ),
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  const displayRows = searchQuery || providerFilter !== 'all' || statusFilter !== 'all'
    ? filteredProfiles
    : authProfiles

  return (
    <>
    {/* CLI-Only Banner */}
    <Alert severity="info" sx={{ mb: 2 }}>
      <AlertTitle>{t(K.page.authProfiles.readOnlyTitle)}</AlertTitle>
      {t(K.page.authProfiles.readOnlyMessage)}
      <br />
      <code style={{ display: 'block', marginTop: '8px', padding: '4px 8px', background: '#f5f5f5', borderRadius: '4px' }}>
        {t(K.page.authProfiles.readOnlyCommand)}
      </code>
    </Alert>

    {/* Error Display */}
    {error && (
      <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
        <AlertTitle>{t(K.common.error)}</AlertTitle>
        {error}
      </Alert>
    )}

    <TableShell
      loading={loading}
      rows={displayRows}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 4,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t(K.common.search)}
                  fullWidth
                  size="small"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={providerFilter}
                  onChange={(e) => setProviderFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.authProfiles.allProviders)}</MenuItem>
                  <MenuItem value="openai">{t(K.page.authProfiles.providerOpenAI)}</MenuItem>
                  <MenuItem value="anthropic">{t(K.page.authProfiles.providerAnthropic)}</MenuItem>
                  <MenuItem value="ollama">{t(K.page.authProfiles.providerOllama)}</MenuItem>
                  <MenuItem value="lmstudio">{t(K.page.authProfiles.providerLMStudio)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 4,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.authProfiles.allStatus)}</MenuItem>
                  <MenuItem value="active">{t(K.page.authProfiles.statusActive)}</MenuItem>
                  <MenuItem value="inactive">{t(K.page.authProfiles.statusInactive)}</MenuItem>
                  <MenuItem value="error">{t(K.page.authProfiles.statusError)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setProviderFilter('all')
                setStatusFilter('all')
              },
            },
            {
              key: 'apply',
              label: t('common.apply'),
              variant: 'contained',
              onClick: applyFilters,
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.authProfiles.noAuthProfiles),
        description: t(K.page.authProfiles.noAuthProfilesDesc),
        actions: [
          {
            label: t('common.add'),
            onClick: () => {
              setCreateDialogOpen(true)
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: displayRows.length,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('Auth profile row clicked (migration stage):', row)
      }}
    />

    {/* Create Auth Profile Dialog */}
    <DialogForm
      open={createDialogOpen}
      onClose={() => setCreateDialogOpen(false)}
      title={t('common.add')}
      submitText={t('common.create')}
      cancelText={t('common.cancel')}
      onSubmit={handleCreateSubmit}
      submitDisabled={!profileName.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.authProfiles.fieldProfileName)}
            placeholder={t(K.page.authProfiles.fieldProfileNamePlaceholder)}
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            fullWidth
            required           />
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t(K.page.authProfiles.fieldProvider)}
            fullWidth
            value={profileProvider}
            onChange={(e) => setProfileProvider(e.target.value)}
          >
            <MenuItem value="openai">{t(K.page.authProfiles.providerOpenAI)}</MenuItem>
            <MenuItem value="anthropic">{t(K.page.authProfiles.providerAnthropic)}</MenuItem>
            <MenuItem value="ollama">{t(K.page.authProfiles.providerOllama)}</MenuItem>
            <MenuItem value="lmstudio">{t(K.page.authProfiles.providerLMStudio)}</MenuItem>
          </Select>
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t(K.page.authProfiles.fieldType)}
            fullWidth
            value={profileType}
            onChange={(e) => setProfileType(e.target.value)}
          >
            <MenuItem value="api-key">{t(K.page.authProfiles.typeApiKey)}</MenuItem>
            <MenuItem value="local">{t(K.page.authProfiles.typeLocal)}</MenuItem>
          </Select>
        </Grid>
      </Grid>
    </DialogForm>
    </>
  )
}
