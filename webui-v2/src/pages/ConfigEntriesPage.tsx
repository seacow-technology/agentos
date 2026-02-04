/**
 * ConfigEntriesPage - 配置项管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - 🚀 API Integration: 完整CRUD集成（P0+P1任务）
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ i18n Compliance: 所有文本使用 page.configEntries.* 命名空间
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Button } from '@/ui'
// eslint-disable-next-line no-restricted-imports
import { Grid } from '@mui/material'
import { usePageHeader } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DialogForm, ConfirmDialog, DetailDrawer } from '@/ui/interaction'
import type { GridColDef } from '@/ui'
import {
  systemService,
  type ConfigEntry,
  type ConfigEntryVersion,
  type ConfigVersionDiff,
} from '@services'


/**
 * ConfigEntriesPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🚀 API Integration: 完整CRUD集成
 */
export function ConfigEntriesContent({ readOnly = true }: { readOnly?: boolean }) {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [entries, setEntries] = useState<ConfigEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  // ===================================
  // State - Filters & Pagination
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [scopeFilter, setScopeFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)

  // ===================================
  // State - Dialogs & Drawers
  // ===================================
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [versionDialogOpen, setVersionDialogOpen] = useState(false)
  const [diffDialogOpen, setDiffDialogOpen] = useState(false)
  const [selectedEntry, setSelectedEntry] = useState<ConfigEntry | null>(null)

  // ===================================
  // State - Version History & Diff
  // ===================================
  const [versions, setVersions] = useState<ConfigEntryVersion[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [selectedFromVersion, setSelectedFromVersion] = useState<number | null>(null)
  const [selectedToVersion, setSelectedToVersion] = useState<number | null>(null)
  const [diff, setDiff] = useState<ConfigVersionDiff | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)

  // ===================================
  // State - Form Fields (Create)
  // ===================================
  const [entryKey, setEntryKey] = useState('')
  const [entryValue, setEntryValue] = useState('')
  const [entryType, setEntryType] = useState<'String' | 'Integer' | 'Boolean' | 'JSON'>('String')
  const [entryScope, setEntryScope] = useState('')
  const [entryDescription, setEntryDescription] = useState('')

  // ===================================
  // State - Form Fields (Edit)
  // ===================================
  const [editValue, setEditValue] = useState('')
  const [editType, setEditType] = useState<'String' | 'Integer' | 'Boolean' | 'JSON'>('String')
  const [editScope, setEditScope] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // ===================================
  // Data Fetching
  // ===================================
  const fetchEntries = async () => {
    setLoading(true)
    try {
      const params = {
        search: searchQuery || undefined,
        scope: scopeFilter !== 'all' ? scopeFilter : undefined,
        type: typeFilter !== 'all' ? typeFilter : undefined,
        page: page + 1, // Backend uses 1-indexed
        limit: pageSize,
      }
      const response = await systemService.listConfigEntries(params)
      setEntries(response.entries)
      setTotal(response.total)
    } catch (err) {
      console.error('Failed to fetch config entries:', err)
      toast.error(t('common.errorLoadData'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEntries()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize])

  // ===================================
  // Export Handler
  // ===================================
  const handleExport = () => {
    try {
      // Prepare export data with timestamp
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)
      const exportData = {
        exportedAt: new Date().toISOString(),
        totalEntries: entries.length,
        entries: entries.map((entry) => ({
          id: entry.id,
          key: entry.key,
          value: entry.value,
          type: entry.type,
          scope: entry.scope,
          description: entry.description,
          lastModified: entry.lastModified,
        })),
      }

      // Create blob and download
      const jsonString = JSON.stringify(exportData, null, 2)
      const blob = new Blob([jsonString], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `config_export_${timestamp}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to export config entries:', error)
      toast.error(t('common.errorSave'))
    }
  }

  const isReadOnly = readOnly

  // ===================================
  // CRUD Handlers
  // ===================================
  const handleCreateSubmit = async () => {
    if (isReadOnly) {
      toast.info(t('common.readOnly'))
      return
    }
    try {
      await systemService.createConfigEntry({
        key: entryKey,
        value: entryValue,
        type: entryType,
        scope: entryScope || undefined,
        description: entryDescription || undefined,
      })
      setCreateDialogOpen(false)
      // Reset form
      setEntryKey('')
      setEntryValue('')
      setEntryType('String')
      setEntryScope('')
      setEntryDescription('')
      // Refresh list
      await fetchEntries()
    } catch (error) {
      console.error('Failed to create config entry:', error)
      toast.error(t('common.errorSave'))
    }
  }

  const handleEditSubmit = async () => {
    if (!selectedEntry) return
    if (isReadOnly) {
      toast.info(t('common.readOnly'))
      return
    }
    try {
      await systemService.updateConfigEntry(selectedEntry.id, {
        value: editValue,
        type: editType,
        scope: editScope || undefined,
        description: editDescription || undefined,
      })
      setEditDialogOpen(false)
      setDrawerOpen(false)
      // Refresh list
      await fetchEntries()
    } catch (error) {
      console.error('Failed to update config entry:', error)
      toast.error(t('common.errorSave'))
    }
  }

  const handleDeleteConfirm = async () => {
    if (!selectedEntry) return
    if (isReadOnly) {
      toast.info(t('common.readOnly'))
      return
    }
    try {
      await systemService.deleteConfigEntry(selectedEntry.id)
      setDeleteDialogOpen(false)
      setDrawerOpen(false)
      // Refresh list
      await fetchEntries()
    } catch (error) {
      console.error('Failed to delete config entry:', error)
      toast.error(t('common.errorDelete'))
    }
  }

  const handleRowClick = (row: ConfigEntry) => {
    setSelectedEntry(row)
    setDrawerOpen(true)
  }

  const handleEditClick = () => {
    if (!selectedEntry) return
    if (isReadOnly) {
      toast.info(t('common.readOnly'))
      return
    }
    setEditValue(selectedEntry.value)
    setEditType(selectedEntry.type)
    setEditScope(selectedEntry.scope)
    setEditDescription(selectedEntry.description)
    setEditDialogOpen(true)
  }

  const handleDeleteClick = () => {
    if (isReadOnly) {
      toast.info(t('common.readOnly'))
      return
    }
    setDeleteDialogOpen(true)
  }

  const handleApplyFilters = () => {
    setPage(0) // Reset to first page
    fetchEntries()
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setScopeFilter('all')
    setTypeFilter('all')
    setPage(0)
  }

  // ===================================
  // Version History Handlers
  // ===================================
  const handleViewVersions = async () => {
    if (!selectedEntry) return
    setVersionsLoading(true)
    try {
      const response = await systemService.listConfigVersions(selectedEntry.id)
      setVersions(response.versions)
      setVersionDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch version history:', error)
      toast.error(t('page.configEntries.toastVersionHistoryError'))
    } finally {
      setVersionsLoading(false)
    }
  }

  const handleCompareVersions = async () => {
    if (!selectedEntry || selectedFromVersion === null || selectedToVersion === null) {
      toast.error(t('page.configEntries.toastSelectVersions'))
      return
    }
    setDiffLoading(true)
    try {
      const response = await systemService.getConfigDiff(
        selectedEntry.id,
        selectedFromVersion,
        selectedToVersion
      )
      setDiff(response.diff)
      setDiffDialogOpen(true)
    } catch (error) {
      console.error('Failed to fetch version diff:', error)
      toast.error(t('page.configEntries.toastDiffError'))
    } finally {
      setDiffLoading(false)
    }
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t('page.configEntries.columnId'),
      width: 70,
    },
    {
      field: 'key',
      headerName: t('page.configEntries.columnKey'),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'value',
      headerName: t('page.configEntries.columnValue'),
      width: 150,
    },
    {
      field: 'type',
      headerName: t('page.configEntries.columnType'),
      width: 100,
    },
    {
      field: 'scope',
      headerName: t('page.configEntries.columnScope'),
      width: 120,
    },
    {
      field: 'description',
      headerName: t('page.configEntries.columnDescription'),
      flex: 2,
      minWidth: 250,
    },
    {
      field: 'lastModified',
      headerName: t('page.configEntries.columnLastModified'),
      width: 180,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
    <TableShell
      loading={loading}
      rows={entries}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t('page.configEntries.searchPlaceholder')}
                  fullWidth
                  size='small' // eslint-disable-line react/jsx-no-literals
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size='small' // eslint-disable-line react/jsx-no-literals
                  value={scopeFilter}
                  onChange={(e) => setScopeFilter(e.target.value)}
                >
                  {/* eslint-disable react/jsx-no-literals */}
                  <MenuItem value='all'>{t('page.configEntries.scopeAll')}</MenuItem>
                  <MenuItem value='System'>{t('page.configEntries.scopeSystem')}</MenuItem>
                  <MenuItem value='API'>{t('page.configEntries.scopeApi')}</MenuItem>
                  <MenuItem value='UI'>{t('page.configEntries.scopeUi')}</MenuItem>
                  <MenuItem value='Security'>{t('page.configEntries.scopeSecurity')}</MenuItem>
                  <MenuItem value='LLM'>{t('page.configEntries.scopeLlm')}</MenuItem>
                  <MenuItem value='Demo'>{t('page.configEntries.scopeDemo')}</MenuItem>
                  {/* eslint-enable react/jsx-no-literals */}
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size='small' // eslint-disable-line react/jsx-no-literals
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  {/* eslint-disable react/jsx-no-literals */}
                  <MenuItem value='all'>{t('page.configEntries.typeAll')}</MenuItem>
                  <MenuItem value='String'>{t('page.configEntries.typeString')}</MenuItem>
                  <MenuItem value='Integer'>{t('page.configEntries.typeInteger')}</MenuItem>
                  <MenuItem value='Boolean'>{t('page.configEntries.typeBoolean')}</MenuItem>
                  <MenuItem value='JSON'>{t('page.configEntries.typeJson')}</MenuItem>
                  {/* eslint-enable react/jsx-no-literals */}
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: handleResetFilters,
            },
            {
              key: 'apply',
              label: t('common.apply'),
              variant: 'contained',
              onClick: handleApplyFilters,
            },
            {
              key: 'export',
              label: t('page.configEntries.exportConfig'),
              variant: 'outlined',
              onClick: handleExport,
            },
            {
              key: 'create',
              label: (
                <span title={t('common.readOnly')}>{t('page.configEntries.addEntry')}</span>
              ),
              variant: 'contained',
              disabled: true,
              onClick: () => {},
            },
          ]}
        />
      }
      emptyState={{
        title: t('page.configEntries.noEntries'),
        description: t('page.configEntries.noEntriesDesc'),
        actions: [
          {
            label: t('page.configEntries.addEntry'),
            onClick: () => {},
            disabled: true,
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
      onRowClick={handleRowClick}
    />

    {/* Create Config Entry Dialog */}
    <DialogForm
      open={createDialogOpen}
      onClose={() => setCreateDialogOpen(false)}
      title={t('page.configEntries.dialogTitle')}
      submitText={t('common.create')}
      cancelText={t('common.cancel')}
      onSubmit={handleCreateSubmit}
      submitDisabled={!entryKey.trim() || !entryValue.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldKey')}
            placeholder={t('page.configEntries.fieldKeyPlaceholder')}
            value={entryKey}
            onChange={(e) => setEntryKey(e.target.value)}
            fullWidth
            required
            autoFocus
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldValue')}
            placeholder={t('page.configEntries.fieldValuePlaceholder')}
            value={entryValue}
            onChange={(e) => setEntryValue(e.target.value)}
            fullWidth
            required
          />
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t('page.configEntries.fieldType')}
            fullWidth
            value={entryType}
            onChange={(e) => setEntryType(e.target.value as 'String' | 'Integer' | 'Boolean' | 'JSON')}
          >
            {/* eslint-disable react/jsx-no-literals */}
            <MenuItem value='String'>{t('page.configEntries.typeString')}</MenuItem>
            <MenuItem value='Integer'>{t('page.configEntries.typeInteger')}</MenuItem>
            <MenuItem value='Boolean'>{t('page.configEntries.typeBoolean')}</MenuItem>
            <MenuItem value='JSON'>{t('page.configEntries.typeJson')}</MenuItem>
            {/* eslint-enable react/jsx-no-literals */}
          </Select>
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldScope')}
            placeholder={t('page.configEntries.fieldScopePlaceholder')}
            value={entryScope}
            onChange={(e) => setEntryScope(e.target.value)}
            fullWidth
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldDescription')}
            placeholder={t('page.configEntries.fieldDescriptionPlaceholder')}
            value={entryDescription}
            onChange={(e) => setEntryDescription(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </Grid>
      </Grid>
    </DialogForm>

    {/* Edit Config Entry Dialog */}
    <DialogForm
      open={editDialogOpen}
      onClose={() => setEditDialogOpen(false)}
      title={t('page.configEntries.dialogEditTitle')}
      submitText={t('common.save')}
      cancelText={t('common.cancel')}
      onSubmit={handleEditSubmit}
      submitDisabled={!editValue.trim()}
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldValue')}
            placeholder={t('page.configEntries.fieldValuePlaceholder')}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            fullWidth
            required
            autoFocus
          />
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t('page.configEntries.fieldType')}
            fullWidth
            value={editType}
            onChange={(e) => setEditType(e.target.value as 'String' | 'Integer' | 'Boolean' | 'JSON')}
          >
            {/* eslint-disable react/jsx-no-literals */}
            <MenuItem value='String'>{t('page.configEntries.typeString')}</MenuItem>
            <MenuItem value='Integer'>{t('page.configEntries.typeInteger')}</MenuItem>
            <MenuItem value='Boolean'>{t('page.configEntries.typeBoolean')}</MenuItem>
            <MenuItem value='JSON'>{t('page.configEntries.typeJson')}</MenuItem>
            {/* eslint-enable react/jsx-no-literals */}
          </Select>
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldScope')}
            placeholder={t('page.configEntries.fieldScopePlaceholder')}
            value={editScope}
            onChange={(e) => setEditScope(e.target.value)}
            fullWidth
          />
        </Grid>
        <Grid item xs={12}>
          <TextField
            label={t('page.configEntries.fieldDescription')}
            placeholder={t('page.configEntries.fieldDescriptionPlaceholder')}
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />
        </Grid>
      </Grid>
    </DialogForm>

    {/* Delete Confirmation Dialog */}
    <ConfirmDialog
      open={deleteDialogOpen}
      onClose={() => setDeleteDialogOpen(false)}
      onConfirm={handleDeleteConfirm}
      title={t('page.configEntries.deleteDialogTitle')}
      message={t('page.configEntries.deleteDialogMessage', { key: selectedEntry?.key || '' })}
      confirmText={t('common.delete')}
      cancelText={t('common.cancel')}
      color='error' // eslint-disable-line react/jsx-no-literals
    />

    {/* Detail Drawer */}
    <DetailDrawer
      open={drawerOpen}
      onClose={() => setDrawerOpen(false)}
      title={selectedEntry?.key || ''}
      actions={
        <>
          <Button
            variant='outlined' // eslint-disable-line react/jsx-no-literals
            onClick={handleViewVersions}
            disabled={versionsLoading}
          >
            {versionsLoading ? t('common.loading') : t('page.configEntries.viewVersions')}
          </Button>
          <Button
            variant='outlined' // eslint-disable-line react/jsx-no-literals
            onClick={handleEditClick}
            disabled={isReadOnly}
            title={isReadOnly ? t('common.readOnly') : undefined}
          >
            {t('common.edit')}
          </Button>
          <Button
            variant='outlined' // eslint-disable-line react/jsx-no-literals
            color='error' // eslint-disable-line react/jsx-no-literals
            onClick={handleDeleteClick}
            disabled={isReadOnly}
            title={isReadOnly ? t('common.readOnly') : undefined}
          >
            {t('common.delete')}
          </Button>
        </>
      }
    >
      {selectedEntry && (
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnId')}
              value={selectedEntry.id}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnKey')}
              value={selectedEntry.key}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnValue')}
              value={selectedEntry.value}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t('page.configEntries.columnType')}
              value={selectedEntry.type}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t('page.configEntries.columnScope')}
              value={selectedEntry.scope}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnDescription')}
              value={selectedEntry.description}
              fullWidth
              multiline
              rows={3}
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnLastModified')}
              value={selectedEntry.lastModified}
              fullWidth
              disabled
            />
          </Grid>
        </Grid>
      )}
    </DetailDrawer>

    {/* Version History Dialog */}
    <DialogForm
      open={versionDialogOpen}
      onClose={() => {
        setVersionDialogOpen(false)
        setSelectedFromVersion(null)
        setSelectedToVersion(null)
      }}
      title={t('page.configEntries.versionHistoryTitle')}
      submitText={t('page.configEntries.compareVersions')}
      cancelText={t('common.close')}
      onSubmit={handleCompareVersions}
      submitDisabled={selectedFromVersion === null || selectedToVersion === null || diffLoading}
      maxWidth='md' // eslint-disable-line react/jsx-no-literals
    >
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Select
            label={t('page.configEntries.fromVersion')}
            fullWidth
            value={selectedFromVersion ?? ''}
            onChange={(e) => setSelectedFromVersion(Number(e.target.value))}
          >
            {/* eslint-disable react/jsx-no-literals */}
            <MenuItem value='' disabled>
              {t('page.configEntries.selectVersion')}
            </MenuItem>
            {versions.map((v) => (
              <MenuItem key={v.id} value={v.version}>
                v{v.version} - {v.changed_at} ({v.changed_by})
              </MenuItem>
            ))}
            {/* eslint-enable react/jsx-no-literals */}
          </Select>
        </Grid>
        <Grid item xs={12}>
          <Select
            label={t('page.configEntries.toVersion')}
            fullWidth
            value={selectedToVersion ?? ''}
            onChange={(e) => setSelectedToVersion(Number(e.target.value))}
          >
            {/* eslint-disable react/jsx-no-literals */}
            <MenuItem value='' disabled>
              {t('page.configEntries.selectVersion')}
            </MenuItem>
            {versions.map((v) => (
              <MenuItem key={v.id} value={v.version}>
                v{v.version} - {v.changed_at} ({v.changed_by})
              </MenuItem>
            ))}
            {/* eslint-enable react/jsx-no-literals */}
          </Select>
        </Grid>
      </Grid>
    </DialogForm>

    {/* Diff Viewer Dialog */}
    <DialogForm
      open={diffDialogOpen}
      onClose={() => {
        setDiffDialogOpen(false)
        setDiff(null)
      }}
      title={t('page.configEntries.diffViewerTitle')}
      submitText={t('common.close')}
      cancelText='' // eslint-disable-line react/jsx-no-literals
      onSubmit={() => {
        setDiffDialogOpen(false)
        setDiff(null)
      }}
      maxWidth='lg' // eslint-disable-line react/jsx-no-literals
    >
      {diff && (
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t('page.configEntries.columnKey')}
              value={diff.entry_key}
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t('page.configEntries.fromVersionLabel')}
              value={'v' + diff.from_version}  
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={6}>
            <TextField
              label={t('page.configEntries.toVersionLabel')}
              value={'v' + diff.to_version}  
              fullWidth
              disabled
            />
          </Grid>
          <Grid item xs={12}>
            <div style={{
              backgroundColor: '#f5f5f5',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              padding: '16px',
              fontFamily: 'monospace',
              fontSize: '14px',
              maxHeight: '400px',
              overflow: 'auto',
            }}>
              {diff.diff_lines.map((line, index) => (
                <div
                  key={index}
                  style={{
                    backgroundColor:
                      line.type === 'added'
                        ? '#e6ffed'
                        : line.type === 'removed'
                        ? '#ffebe9'
                        : 'transparent',
                    color:
                      line.type === 'added'
                        ? '#22863a'
                        : line.type === 'removed'
                        ? '#cb2431'
                        : '#24292e',
                    padding: '2px 8px',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                  }}
                >
                  {line.type === 'added' ? '+ ' : line.type === 'removed' ? '- ' : '  '}
                  {line.content}
                </div>
              ))}
            </div>
          </Grid>
        </Grid>
      )}
    </DialogForm>
    </>
  )
}

export default function ConfigEntriesPage() {
  const { t } = useTextTranslation()

  usePageHeader({
    title: t('page.configEntries.title'),
    subtitle: t('page.configEntries.subtitle'),
  })

  return <ConfigEntriesContent readOnly />
}
