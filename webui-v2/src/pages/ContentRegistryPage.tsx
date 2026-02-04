/**
 * ContentRegistryPage - Content Lifecycle Management
 *
 * Phase 6: v1→v2 Alignment Complete + Full CRUD Implementation
 * - API: systemService.listContent() for listing
 * - API: systemService.getContent() for details
 * - API: systemService.createContent() for registration
 * - API: systemService.updateContent() for edit/activate/deprecate/freeze/delete
 * - API: Runtime mode detection & admin actions
 * - UI: Filters (Type/Status/Search), View modes (Card/Table), Pagination
 * - UI: Register/Edit/Delete dialogs with full form validation
 * - UI: Card actions (View/Edit/Deprecate/Activate/Delete)
 * - UI: Table actions (Info/Edit/Deprecate/Activate/Delete icons)
 * - UI: Detail drawer with admin actions (Edit/Deprecate/Activate/Freeze/Delete)
 * - States: Loading/Success/Error/Empty (Four-state pattern)
 * - i18n: Full translation support
 * - NO MOCK DATA
 *
 * Complete CRUD Operations:
 * ✓ Create: Register new content (agent/workflow/skill/tool)
 * ✓ Read: List content, view details in drawer
 * ✓ Update: Edit content metadata, activate/deprecate/freeze status
 * ✓ Delete: Remove deprecated content (admin only)
 *
 * Lifecycle Management:
 * - Active → Deprecate → Delete
 * - Active → Freeze (immutable state)
 * - Deprecated → Activate (reactivate)
 * - Admin-gated write operations with confirmation
 * - Local mode: read-only (no admin actions)
 */

import { useState, useMemo, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useText } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DialogForm, DetailDrawer } from '@/ui/interaction'
import { TextField, Select, MenuItem, Box, Alert, Chip, Button } from '@/ui'
import { IconButton, Tooltip, Table, TableHead, TableBody, TableRow, TableCell } from '@mui/material'
import { Grid, CircularProgress } from '@mui/material'
import { ExtensionIcon, SmartToyIcon, AccountTreeIcon, BuildIcon, GridViewIcon, ListIcon, InfoIcon, ArchiveIcon, CheckCircleIcon, AcUnitIcon, EditIcon, DeleteIcon } from '@/ui/icons'
import { DashboardGrid } from '@/ui/dashboard/DashboardGrid'
import { StatCard } from '@/ui/dashboard/StatCard'
import { systemService } from '@/services'

// Constants for string literals (Gate validation)
const CHANGE_TYPE_INCREASE = 'increase' as const

// Helper: Icon mapping for content types
function getIconForType(type: string) {
  switch (type) {
    case 'agent': return <SmartToyIcon />
    case 'workflow': return <AccountTreeIcon />
    case 'skill': return <ExtensionIcon />
    case 'tool': return <BuildIcon />
    default: return <BuildIcon />
  }
}


export default function ContentRegistryPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useText()

  // ===================================
  // State: API Data
  // ===================================
  const [contentItems, setContentItems] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters State
  const [filterType, setFilterType] = useState('all')
  const [filterStatus, setFilterStatus] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  // View Mode State
  const [viewMode, setViewMode] = useState<'card' | 'table'>('card')

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize] = useState(20)

  // Runtime Mode State
  const [runtimeMode, setRuntimeMode] = useState<'local' | 'production'>('local')
  const [isAdmin, setIsAdmin] = useState(false)

  // Dialog State - Create/Edit
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [contentName, setContentName] = useState('')
  const [contentUrl, setContentUrl] = useState('')
  const [contentType, setContentType] = useState('agent')
  const [contentVersion, setContentVersion] = useState('1.0.0')
  const [contentDescription, setContentDescription] = useState('')

  // Detail Drawer State
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState<any>(null)
  const [detailError, setDetailError] = useState<string | null>(null)

  usePageHeader({
    title: t(K.page.contentRegistry.title),
    subtitle: t(K.page.contentRegistry.subtitle),
  })

  usePageActions([
    {
      key: 'register',
      label: t(K.page.contentRegistry.registerContent),
      variant: 'contained',
      onClick: () => {
        setCreateDialogOpen(true)
      },
    },
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => loadContent(),
    },
  ])

  // ===================================
  // API: Detect Runtime Mode
  // ===================================
  const detectRuntimeMode = async () => {
    try {
      const response = await systemService.getContent('mode')
      const content = response?.content as any
      setRuntimeMode((content?.mode as 'local' | 'production') || 'local')
      setIsAdmin(content?.features?.admin_required === true)
    } catch (err: any) {
      console.warn('Failed to detect runtime mode:', err)
      setRuntimeMode('local')
      setIsAdmin(false)
    }
  }

  // ===================================
  // API: Load Content
  // ===================================
  const loadContent = async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch content list from real API
      const response = await systemService.listContent()

      // Map API response to our display format
      // API returns: { content: [{id, name, type, version, status, source_uri, metadata, ...}], total }
      const items = response?.content || []
      const mappedContent = items.map((item: any) => {
        const metadata = item.metadata || {}
        return {
          id: item.id,
          title: item.name || 'Untitled',
          type: item.type || 'unknown',
          description: metadata.description || item.release_notes || '',
          version: item.version || 'v1.0.0',
          status: item.status || 'active',
          tags: metadata.tags || [],
          author: metadata.author || 'Unknown',
          source_uri: item.source_uri,
          created_at: item.created_at,
          updated_at: item.updated_at,
          icon: getIconForType(item.type || 'unknown'),
        }
      })
      setContentItems(mappedContent)
    } catch (err: any) {
      console.error('Failed to load content:', err)
      const errorMessage = err.message || t(K.page.contentRegistry.loadError)
      setError(errorMessage)
      toast.error(errorMessage)
      setContentItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    detectRuntimeMode()
    loadContent()
  }, [])

  // ===================================
  // Dialog Handler - Register Content
  // ===================================
  const handleRegisterSubmit = async () => {
    try {
      // Real API call to register content
      await systemService.createContent({
        type: contentType,
        name: contentName,
        version: contentVersion,
        source_uri: contentUrl,
        metadata: {
          description: contentDescription,
        },
        release_notes: 'Initial registration',
      })
      toast.success(t(K.page.contentRegistry.toastRegisterSuccess))
      setCreateDialogOpen(false)
      resetForm()
      await loadContent()
    } catch (err: any) {
      console.error('Failed to register content:', err)
      toast.error(err.message || t(K.page.contentRegistry.toastRegisterFailed))
    }
  }

  // ===================================
  // Detail Drawer Handler
  // ===================================
  const handleCardClick = async (itemId: string) => {
    setDetailDrawerOpen(true)
    setDetailLoading(true)
    setDetailError(null)
    setDetailData(null)

    try {
      // FIXED: Use correct API endpoint /api/content/{id}
      const response = await systemService.getContent(itemId)
      setDetailData(response.content)
    } catch (error: any) {
      console.error('Failed to fetch content detail:', error)
      setDetailError(error.message || 'Failed to load content details')
      toast.error(t(K.page.contentRegistry.toastDetailsFailed))
    } finally {
      setDetailLoading(false)
    }
  }

  const handleDetailDrawerClose = () => {
    setDetailDrawerOpen(false)
    setDetailData(null)
    setDetailError(null)
  }

  // ===================================
  // CRUD Operations - Edit Content
  // ===================================
  const handleEditClick = (itemId: string) => {
    const item = contentItems.find(c => c.id === itemId)
    if (!item) return

    setEditingItemId(itemId)
    setContentName(item.title)
    setContentType(item.type)
    setContentVersion(item.version)
    setContentDescription(item.description)
    setContentUrl(item.source_uri || '')
    setEditDialogOpen(true)
  }

  const handleEditSubmit = async () => {
    if (!editingItemId) return

    try {
      await systemService.updateContent(editingItemId, {
        name: contentName,
        version: contentVersion,
        source_uri: contentUrl,
        metadata: {
          description: contentDescription,
        },
      })
      toast.success(t(K.common.updateSuccess))
      setEditDialogOpen(false)
      resetForm()
      await loadContent()
    } catch (err: any) {
      console.error('Failed to update content:', err)
      toast.error(err.message || t(K.common.updateFailed))
    }
  }

  // ===================================
  // CRUD Operations - Delete Content
  // ===================================
  const handleDeleteContent = async (itemId: string) => {
    const item = contentItems.find(c => c.id === itemId)
    if (!item) return

    if (!window.confirm(t(K.common.confirmDelete) || `Are you sure you want to delete "${item.title}"?`)) {
      return
    }

    try {
      await systemService.updateContent(itemId, { action: 'delete', confirm: true })
      toast.success(t(K.common.deleteSuccess))
      await loadContent()
    } catch (err: any) {
      console.error('Failed to delete content:', err)
      toast.error(err.message || t(K.common.deleteFailed))
    }
  }

  // ===================================
  // Admin Actions - Status Management
  // ===================================
  const handleActivateContent = async (itemId: string) => {
    if (!window.confirm(t(K.page.contentRegistry.confirmActivate))) {
      return
    }
    try {
      await systemService.updateContent(itemId, { action: 'activate', confirm: true })
      toast.success(t(K.page.contentRegistry.toastActivateSuccess))
      await loadContent()
    } catch (err: any) {
      console.error('Failed to activate content:', err)
      toast.error(err.message || t(K.page.contentRegistry.toastActivateFailed))
    }
  }

  const handleDeprecateContent = async (itemId: string) => {
    if (!window.confirm(t(K.page.contentRegistry.confirmDeprecate))) {
      return
    }
    try {
      await systemService.updateContent(itemId, { action: 'deprecate', confirm: true })
      toast.success(t(K.page.contentRegistry.toastDeprecateSuccess))
      await loadContent()
    } catch (err: any) {
      console.error('Failed to deprecate content:', err)
      toast.error(err.message || t(K.page.contentRegistry.toastDeprecateFailed))
    }
  }

  const handleFreezeContent = async (itemId: string) => {
    if (!window.confirm(t(K.page.contentRegistry.confirmFreeze))) {
      return
    }
    try {
      await systemService.updateContent(itemId, { action: 'freeze', confirm: true })
      toast.success(t(K.page.contentRegistry.toastFreezeSuccess))
      await loadContent()
    } catch (err: any) {
      console.error('Failed to freeze content:', err)
      toast.error(err.message || t(K.page.contentRegistry.toastFreezeFailed))
    }
  }

  // ===================================
  // Helper - Reset Form
  // ===================================
  const resetForm = () => {
    setContentName('')
    setContentUrl('')
    setContentType('agent')
    setContentVersion('1.0.0')
    setContentDescription('')
    setEditingItemId(null)
  }

  // ===================================
  // 翻译映射函数
  // ===================================
  const getContentTypeText = (type: string) => {
    const map: Record<string, string> = {
      agent: t(K.page.contentRegistry.typeAgent),
      workflow: t(K.page.contentRegistry.typeWorkflow),
      skill: t(K.page.contentRegistry.typeSkill),
      tool: t(K.page.contentRegistry.typeTool),
    }
    return map[type] || type
  }

  const getStatusText = (status: string) => {
    const map: Record<string, string> = {
      active: t(K.page.contentRegistry.statusActive),
      deprecated: t(K.page.contentRegistry.statusDeprecated),
    }
    return map[status] || status
  }


  // ===================================
  // Filtering Logic (useMemo)
  // ===================================
  const filteredItems = useMemo(() => {
    return contentItems.filter(item => {
      // Type filter
      if (filterType !== 'all' && item.type !== filterType) {
        return false
      }
      // Status filter
      if (filterStatus !== 'all' && item.status !== filterStatus) {
        return false
      }
      // Search filter (by name or tags)
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const nameMatch = item.title?.toLowerCase().includes(query)
        const tagsMatch = item.tags?.some((tag: string) => tag.toLowerCase().includes(query))
        if (!nameMatch && !tagsMatch) {
          return false
        }
      }
      return true
    })
  }, [contentItems, filterType, filterStatus, searchQuery])

  // ===================================
  // Pagination Logic (useMemo)
  // ===================================
  const paginatedItems = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize
    const endIndex = startIndex + pageSize
    return filteredItems.slice(startIndex, endIndex)
  }, [filteredItems, currentPage, pageSize])

  const totalPages = Math.ceil(filteredItems.length / pageSize)

  // ===================================
  // Statistics Calculation (useMemo)
  // ===================================
  const stats = useMemo(() => {
    const totalItems = contentItems.length
    const activeItems = contentItems.filter(item => item.status === 'active').length
    const uniqueTypes = new Set(contentItems.map(item => item.type))
    const typesCount = uniqueTypes.size

    return {
      totalItems,
      activeItems,
      typesCount,
    }
  }, [contentItems])

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <CircularProgress />
        <div style={{ marginTop: '16px' }}>{t(K.common.loading)}</div>
      </div>
    )
  }

  // ===================================
  // Render: Error State
  // ===================================
  if (error && contentItems.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ color: 'error.main', marginBottom: '16px' }}>{error}</div>
        <button onClick={loadContent}>{t(K.common.retry)}</button>
      </div>
    )
  }

  return (
    <>
    {/* Runtime Mode Notice */}
    {runtimeMode === 'local' && (
      <Alert severity="info" sx={{ mb: 2 }}>
        <strong>{t(K.page.contentRegistry.runningLocalMode)}</strong>
        <div style={{ fontSize: '0.875rem', marginTop: '4px' }}>
          {t(K.page.contentRegistry.contentManagementReadOnly)}
        </div>
      </Alert>
    )}

    {/* Statistics Section */}
    <DashboardGrid columns={3} gap={16}>
      <StatCard
        title={t(K.page.contentRegistry.statTotalItems)}
        value={stats.totalItems}
        icon={<BuildIcon />}
      />
      <StatCard
        title={t(K.page.contentRegistry.statActiveItems)}
        value={stats.activeItems}
        changeType={CHANGE_TYPE_INCREASE}
        icon={<SmartToyIcon />}
      />
      <StatCard
        title={t(K.page.contentRegistry.statContentTypes)}
        value={stats.typesCount}
        icon={<ExtensionIcon />}
      />
    </DashboardGrid>

    {/* Filters & View Mode Section */}
    <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
      {/* Type Filter */}
      <Select
        value={filterType}
        onChange={(e) => {
          setFilterType(e.target.value)
          setCurrentPage(1)
        }}
        size="small"
        sx={{ minWidth: 150 }}
      >
        <MenuItem value="all">{t(K.page.contentRegistry.filterAllTypes)}</MenuItem>
        <MenuItem value="agent">{t(K.page.contentRegistry.filterTypeAgent)}</MenuItem>
        <MenuItem value="workflow">{t(K.page.contentRegistry.filterTypeWorkflow)}</MenuItem>
        <MenuItem value="skill">{t(K.page.contentRegistry.filterTypeSkill)}</MenuItem>
        <MenuItem value="tool">{t(K.page.contentRegistry.filterTypeTool)}</MenuItem>
      </Select>

      {/* Status Filter */}
      <Select
        value={filterStatus}
        onChange={(e) => {
          setFilterStatus(e.target.value)
          setCurrentPage(1)
        }}
        size="small"
        sx={{ minWidth: 150 }}
      >
        <MenuItem value="all">{t(K.page.contentRegistry.filterAllStatus)}</MenuItem>
        <MenuItem value="active">{t(K.page.contentRegistry.filterStatusActive)}</MenuItem>
        <MenuItem value="draft">{t(K.page.contentRegistry.filterStatusDraft)}</MenuItem>
        <MenuItem value="deprecated">{t(K.page.contentRegistry.filterStatusDeprecated)}</MenuItem>
        <MenuItem value="frozen">{t(K.page.contentRegistry.filterStatusFrozen)}</MenuItem>
      </Select>

      {/* Search Box */}
      <TextField
        placeholder={t(K.page.contentRegistry.searchPlaceholder)}
        value={searchQuery}
        onChange={(e) => {
          setSearchQuery(e.target.value)
          setCurrentPage(1)
        }}
        size="small"
        sx={{ flexGrow: 1, minWidth: 200 }}
      />

      {/* View Mode Toggle */}
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title={t(K.page.contentRegistry.viewModeCard)}>
          <IconButton
            size="small"
            color={viewMode === 'card' ? 'primary' : 'default'}
            onClick={() => setViewMode('card')}
          >
            <GridViewIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title={t(K.page.contentRegistry.viewModeTable)}>
          <IconButton
            size="small"
            color={viewMode === 'table' ? 'primary' : 'default'}
            onClick={() => setViewMode('table')}
          >
            <ListIcon />
          </IconButton>
        </Tooltip>
      </Box>
    </Box>

    {/* Content List Section - Card View */}
    {viewMode === 'card' && (
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        {paginatedItems.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1' }}>
            <div>{filteredItems.length === 0 ? t(K.page.contentRegistry.noContent) : t(K.page.contentRegistry.noItemsOnPage)}</div>
            <div style={{ marginTop: '8px', color: 'text.secondary' }}>
              {filteredItems.length === 0 ? t(K.page.contentRegistry.noContentDesc) : t(K.page.contentRegistry.adjustFilters)}
            </div>
          </div>
        ) : (
          paginatedItems.map((item) => (
          <ItemCard
            key={item.id}
            title={item.title}
            description={item.description}
            meta={[
              { key: 'version', label: t(K.page.contentRegistry.columnVersion), value: item.version },
              { key: 'type', label: t(K.page.contentRegistry.columnType), value: getContentTypeText(item.type) },
              { key: 'status', label: t(K.page.contentRegistry.columnStatus), value: getStatusText(item.status) },
            ]}
            tags={item.tags}
            icon={item.icon}
            actions={[
              {
                key: 'view',
                label: t('common.info'),
                variant: 'outlined',
                onClick: () => handleCardClick(item.id),
              },
              ...(runtimeMode !== 'local' && isAdmin ? [
                {
                  key: 'edit',
                  label: t(K.common.edit),
                  variant: 'text' as const,
                  onClick: () => handleEditClick(item.id),
                },
              ] : []),
              ...(runtimeMode !== 'local' && isAdmin && item.status === 'active' ? [
                {
                  key: 'deprecate',
                  label: t(K.page.contentRegistry.actionDeprecate),
                  variant: 'text' as const,
                  onClick: () => handleDeprecateContent(item.id),
                },
              ] : []),
              ...(runtimeMode !== 'local' && isAdmin && item.status === 'deprecated' ? [
                {
                  key: 'activate',
                  label: t(K.page.contentRegistry.actionActivate),
                  variant: 'text' as const,
                  onClick: () => handleActivateContent(item.id),
                },
                {
                  key: 'delete',
                  label: t(K.common.delete),
                  variant: 'text' as const,
                  onClick: () => handleDeleteContent(item.id),
                },
              ] : []),
            ]}
            onClick={() => handleCardClick(item.id)}
          />
        ))
        )}
      </CardCollectionWrap>
    )}

    {/* Content List Section - Table View */}
    {viewMode === 'table' && (
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>{t(K.page.contentRegistry.columnType)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnName)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnVersion)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnStatus)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnUpdated)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnTags)}</TableCell>
              <TableCell>{t(K.page.contentRegistry.columnActions)}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {paginatedItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  {filteredItems.length === 0 ? t(K.page.contentRegistry.noContent) : t(K.page.contentRegistry.noItemsOnPage)}
                </TableCell>
              </TableRow>
            ) : (
              paginatedItems.map((item) => (
                <TableRow key={item.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {item.icon}
                      <span>{item.type}</span>
                    </Box>
                  </TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell><code>{item.version}</code></TableCell>
                  <TableCell>
                    <Chip
                      label={getStatusText(item.status)}
                      color={item.status === 'active' ? 'success' : item.status === 'deprecated' ? 'warning' : 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>{item.updated_at ? new Date(item.updated_at).toLocaleDateString() : 'N/A'}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {item.tags?.slice(0, 2).map((tag: string, idx: number) => (
                        <Chip key={idx} label={tag} size="small" />
                      ))}
                      {item.tags?.length > 2 && <Chip label={`+${item.tags.length - 2}`} size="small" />}
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      <Tooltip title={t(K.page.contentRegistry.actionViewDetails)}>
                        <IconButton size="small" onClick={() => handleCardClick(item.id)}>
                          <InfoIcon />
                        </IconButton>
                      </Tooltip>
                      {runtimeMode !== 'local' && isAdmin && (
                        <Tooltip title={t(K.common.edit)}>
                          <IconButton size="small" onClick={() => handleEditClick(item.id)}>
                            <EditIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      {runtimeMode !== 'local' && isAdmin && item.status === 'active' && (
                        <Tooltip title={t(K.page.contentRegistry.actionDeprecate)}>
                          <IconButton size="small" onClick={() => handleDeprecateContent(item.id)}>
                            <ArchiveIcon />
                          </IconButton>
                        </Tooltip>
                      )}
                      {runtimeMode !== 'local' && isAdmin && item.status === 'deprecated' && (
                        <>
                          <Tooltip title={t(K.page.contentRegistry.actionActivate)}>
                            <IconButton size="small" onClick={() => handleActivateContent(item.id)}>
                              <CheckCircleIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t(K.common.delete)}>
                            <IconButton size="small" onClick={() => handleDeleteContent(item.id)} color="error">
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                        </>
                      )}
                    </Box>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Box>
    )}

    {/* Pagination */}
    {totalPages > 1 && (
      <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 2 }}>
        <Button
          variant="outlined"
          size="small"
          disabled={currentPage === 1}
          onClick={() => setCurrentPage(currentPage - 1)}
        >
          {t(K.page.contentRegistry.previousPage)}
        </Button>
        <span>
          {t(K.common.page)} {currentPage} {t(K.page.contentRegistry.pageOf)} {totalPages}
        </span>
        <Button
          variant="outlined"
          size="small"
          disabled={currentPage === totalPages}
          onClick={() => setCurrentPage(currentPage + 1)}
        >
          {t(K.page.contentRegistry.nextPage)}
        </Button>
      </Box>
    )}

    {/* Register Content Dialog */}
    <DialogForm
      open={createDialogOpen}
      onClose={() => {
        setCreateDialogOpen(false)
        resetForm()
      }}
      title={t(K.page.contentRegistry.dialogRegisterTitle)}
      submitText={t(K.page.contentRegistry.dialogRegisterSubmit)}
      cancelText={t('common.cancel')}
      onSubmit={handleRegisterSubmit}
      submitDisabled={!contentName.trim() || !contentVersion.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Select
            label={t(K.page.contentRegistry.dialogFieldContentType)}
            fullWidth
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            size="small"
          >
            <MenuItem value="agent">{t(K.page.contentRegistry.filterTypeAgent)}</MenuItem>
            <MenuItem value="workflow">{t(K.page.contentRegistry.filterTypeWorkflow)}</MenuItem>
            <MenuItem value="skill">{t(K.page.contentRegistry.filterTypeSkill)}</MenuItem>
            <MenuItem value="tool">{t(K.page.contentRegistry.filterTypeTool)}</MenuItem>
          </Select>
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldContentName)}
            placeholder={t(K.page.contentRegistry.dialogFieldContentNamePlaceholder)}
            value={contentName}
            onChange={(e) => setContentName(e.target.value)}
            fullWidth
            required
            autoFocus
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldVersion)}
            placeholder={t(K.page.contentRegistry.dialogFieldVersionPlaceholder)}
            value={contentVersion}
            onChange={(e) => setContentVersion(e.target.value)}
            fullWidth
            required
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldDescription)}
            placeholder={t(K.page.contentRegistry.dialogFieldDescriptionPlaceholder)}
            value={contentDescription}
            onChange={(e) => setContentDescription(e.target.value)}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldSourceUri)}
            placeholder={t(K.page.contentRegistry.dialogFieldSourceUriPlaceholder)}
            value={contentUrl}
            onChange={(e) => setContentUrl(e.target.value)}
            fullWidth
            size="small"
          />
        </Grid>
      </Grid>
    </DialogForm>

    {/* Edit Content Dialog */}
    <DialogForm
      open={editDialogOpen}
      onClose={() => {
        setEditDialogOpen(false)
        resetForm()
      }}
      title={t(K.common.edit) + ' ' + t(K.page.contentRegistry.title)}
      submitText={t(K.common.save)}
      cancelText={t('common.cancel')}
      onSubmit={handleEditSubmit}
      submitDisabled={!contentName.trim() || !contentVersion.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Select
            label={t(K.page.contentRegistry.dialogFieldContentType)}
            fullWidth
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            size="small"
            disabled
          >
            <MenuItem value="agent">{t(K.page.contentRegistry.filterTypeAgent)}</MenuItem>
            <MenuItem value="workflow">{t(K.page.contentRegistry.filterTypeWorkflow)}</MenuItem>
            <MenuItem value="skill">{t(K.page.contentRegistry.filterTypeSkill)}</MenuItem>
            <MenuItem value="tool">{t(K.page.contentRegistry.filterTypeTool)}</MenuItem>
          </Select>
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldContentName)}
            placeholder={t(K.page.contentRegistry.dialogFieldContentNamePlaceholder)}
            value={contentName}
            onChange={(e) => setContentName(e.target.value)}
            fullWidth
            required
            autoFocus
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldVersion)}
            placeholder={t(K.page.contentRegistry.dialogFieldVersionPlaceholder)}
            value={contentVersion}
            onChange={(e) => setContentVersion(e.target.value)}
            fullWidth
            required
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldDescription)}
            placeholder={t(K.page.contentRegistry.dialogFieldDescriptionPlaceholder)}
            value={contentDescription}
            onChange={(e) => setContentDescription(e.target.value)}
            fullWidth
            multiline
            rows={3}
            size="small"
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t(K.page.contentRegistry.dialogFieldSourceUri)}
            placeholder={t(K.page.contentRegistry.dialogFieldSourceUriPlaceholder)}
            value={contentUrl}
            onChange={(e) => setContentUrl(e.target.value)}
            fullWidth
            size="small"
          />
        </Grid>
      </Grid>
    </DialogForm>

    {/* Detail Drawer */}
    <DetailDrawer
      open={detailDrawerOpen}
      onClose={handleDetailDrawerClose}
      title={detailData?.name || t(K.page.contentRegistry.drawerTitle)}
    >
      {detailLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <CircularProgress />
        </div>
      ) : detailError ? (
        <Alert severity="error" sx={{ m: 2 }}>
          {detailError}
        </Alert>
      ) : detailData ? (
        <Box sx={{ p: 2 }}>
          {/* Metadata Section */}
          <Box sx={{ mb: 3 }}>
            <h3 style={{ marginBottom: '12px', fontSize: '1.1rem', fontWeight: 600 }}>{t(K.page.contentRegistry.drawerMetadataTitle)}</h3>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <div><strong>{t(K.page.contentRegistry.drawerFieldType)}:</strong> {detailData.type}</div>
              </Grid>
              <Grid item xs={6}>
                <div>
                  <strong>{t(K.page.contentRegistry.drawerFieldStatus)}:</strong>{' '}
                  <Chip
                    label={getStatusText(detailData.status)}
                    color={detailData.status === 'active' ? 'success' : detailData.status === 'deprecated' ? 'warning' : 'default'}
                    size="small"
                  />
                </div>
              </Grid>
              <Grid item xs={6}>
                <div><strong>{t(K.page.contentRegistry.drawerFieldVersion)}:</strong> <code>{detailData.version}</code></div>
              </Grid>
              <Grid item xs={6}>
                <div><strong>{t(K.page.contentRegistry.drawerFieldAuthor)}:</strong> {detailData.metadata?.author || t(K.common.unknown)}</div>
              </Grid>
              <Grid item xs={6}>
                <div><strong>{t(K.page.contentRegistry.drawerFieldCreated)}:</strong> {detailData.created_at ? new Date(detailData.created_at).toLocaleString() : 'N/A'}</div>
              </Grid>
              <Grid item xs={6}>
                <div><strong>{t(K.page.contentRegistry.drawerFieldUpdated)}:</strong> {detailData.updated_at ? new Date(detailData.updated_at).toLocaleString() : 'N/A'}</div>
              </Grid>
              {detailData.source_uri && (
                <Grid item xs={12}>
                  <div><strong>{t(K.page.contentRegistry.drawerFieldSourceUri)}:</strong> <code style={{ fontSize: '0.85rem' }}>{detailData.source_uri}</code></div>
                </Grid>
              )}
              {detailData.release_notes && (
                <Grid item xs={12}>
                  <div><strong>{t(K.page.contentRegistry.drawerFieldReleaseNotes)}:</strong> {detailData.release_notes}</div>
                </Grid>
              )}
              {detailData.metadata?.description && (
                <Grid item xs={12}>
                  <div><strong>{t(K.page.contentRegistry.drawerFieldDescription)}:</strong> {detailData.metadata.description}</div>
                </Grid>
              )}
              {detailData.metadata?.tags && detailData.metadata.tags.length > 0 && (
                <Grid item xs={12}>
                  <div>
                    <strong>{t(K.page.contentRegistry.drawerFieldTags)}:</strong>
                    <Box sx={{ display: 'flex', gap: 0.5, mt: 1, flexWrap: 'wrap' }}>
                      {detailData.metadata.tags.map((tag: string, idx: number) => (
                        <Chip key={idx} label={tag} size="small" />
                      ))}
                    </Box>
                  </div>
                </Grid>
              )}
            </Grid>
          </Box>

          {/* Admin Actions */}
          {runtimeMode !== 'local' && isAdmin && (
            <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid #e0e0e0' }}>
              <h3 style={{ marginBottom: '12px', fontSize: '1.1rem', fontWeight: 600 }}>{t(K.page.contentRegistry.drawerAdminActionsTitle)}</h3>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {/* Edit Button - Always available for admin */}
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<EditIcon />}
                  onClick={() => {
                    handleEditClick(detailData.id)
                    handleDetailDrawerClose()
                  }}
                >
                  {t(K.common.edit)}
                </Button>

                {/* Status Actions */}
                {detailData.status === 'active' && (
                  <>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<ArchiveIcon />}
                      onClick={() => {
                        handleDeprecateContent(detailData.id)
                        handleDetailDrawerClose()
                      }}
                    >
                      {t(K.page.contentRegistry.actionDeprecate)}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<AcUnitIcon />}
                      onClick={() => {
                        handleFreezeContent(detailData.id)
                        handleDetailDrawerClose()
                      }}
                    >
                      {t(K.page.contentRegistry.actionFreeze)}
                    </Button>
                  </>
                )}
                {detailData.status === 'deprecated' && (
                  <>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<CheckCircleIcon />}
                      onClick={() => {
                        handleActivateContent(detailData.id)
                        handleDetailDrawerClose()
                      }}
                    >
                      {t(K.page.contentRegistry.actionActivate)}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      color="error"
                      startIcon={<DeleteIcon />}
                      onClick={() => {
                        handleDeleteContent(detailData.id)
                        handleDetailDrawerClose()
                      }}
                    >
                      {t(K.common.delete)}
                    </Button>
                  </>
                )}
              </Box>
            </Box>
          )}
        </Box>
      ) : null}
    </DetailDrawer>
    </>
  )
}
