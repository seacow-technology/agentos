/**
 * ExtensionsPage - 扩展管理
 *
 * Phase 6: 真实API接入
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ CardGrid Pattern: CardCollectionWrap + ItemCard
 * - ✅ Real API: skillosService 真实数据交互
 * - ✅ Toast: 操作反馈使用 toast
 * - ✅ State Management: loading/success/error 状态处理
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { AddIcon, UploadIcon, ExtensionIcon, CodeIcon, IntegrationIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer, DeleteConfirmDialog } from '@/ui/interaction'
import { Box, Typography, Chip, Button, CircularProgress } from '@/ui'
import { toast } from '@/ui/feedback'
import { skillosService, type Extension } from '@/services/skillos.service'
import { UploadExtensionDialog } from './ExtensionsPage/UploadExtensionDialog'
import { InstallUrlDialog } from './ExtensionsPage/InstallUrlDialog'
import { ConfigureExtensionDialog } from './ExtensionsPage/ConfigureExtensionDialog'

// ===================================
// Constants
// ===================================

const VARIANT_H6 = 'h6' as const
const VARIANT_BODY1 = 'body1' as const
const VARIANT_BODY2 = 'body2' as const
const VARIANT_CONTAINED = 'contained' as const
const VARIANT_OUTLINED = 'outlined' as const
const COLOR_TEXT_SECONDARY = 'text.secondary' as const
const COLOR_ERROR = 'error' as const
const COLOR_WARNING = 'warning' as const
const COLOR_SUCCESS = 'success' as const
const COLOR_DEFAULT = 'default' as const
const SIZE_SMALL = 'small' as const
const LAYOUT_GRID = 'grid' as const
const RESOURCE_TYPE_EXTENSION = 'Extension' as const

// ===================================
// Types
// ===================================

interface ExtensionRow {
  id: string
  name: string
  version: string
  status: 'enabled' | 'disabled'
  author: string
  description: string
  installedAt: string
}

// ===================================
// Helper Functions
// ===================================

// Icon mapping
const getExtensionIcon = (index: number) => {
  const icons = [<CodeIcon key="code" />, <ExtensionIcon key="ext" />, <IntegrationIcon key="int" />]
  return icons[index % icons.length]
}

// Convert backend Extension to ExtensionRow
function extensionToRow(ext: Extension): ExtensionRow {
  return {
    id: ext.id,
    name: ext.name,
    version: ext.version,
    status: ext.status,
    author: 'Unknown', // Backend doesn't provide author field yet
    description: ext.description || '',
    installedAt: ext.created_at ? new Date(ext.created_at).toLocaleDateString() : '-',
  }
}

// ===================================
// Component
// ===================================

export default function ExtensionsPage() {
  const { t } = useTextTranslation()

  // ===================================
  // State (Data & Loading)
  // ===================================
  const [loading, setLoading] = useState(true)
  const [extensions, setExtensions] = useState<Extension[]>([])

  // ===================================
  // State (UI)
  // ===================================
  const [selectedExtension, setSelectedExtension] = useState<ExtensionRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [installUrlDialogOpen, setInstallUrlDialogOpen] = useState(false)
  const [configureDialogOpen, setConfigureDialogOpen] = useState(false)

  // ===================================
  // State (Actions)
  // ===================================
  const [toggling, setToggling] = useState<string | null>(null) // Track which extension is toggling
  const [deleting, setDeleting] = useState(false)

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.extensions.title),
    subtitle: t(K.page.extensions.subtitle),
  })

  usePageActions([
    {
      key: 'upload',
      label: t(K.page.extensions.uploadExtension),
      icon: <UploadIcon />,
      variant: 'outlined',
      onClick: () => setUploadDialogOpen(true),
    },
    {
      key: 'install',
      label: t(K.page.extensions.installFromUrl),
      icon: <AddIcon />,
      variant: 'contained',
      onClick: () => setInstallUrlDialogOpen(true),
    },
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => loadExtensions(),
    },
  ])

  // ===================================
  // Load Extensions
  // ===================================
  const loadExtensions = async () => {
    setLoading(true)
    try {
      const response = await skillosService.listExtensions()
      setExtensions(response.extensions || [])
    } catch (error) {
      console.error('Failed to load extensions:', error)
      toast.error(t('common.error.loadFailed'))
      setExtensions([])
    } finally {
      setLoading(false)
    }
  }

  // ===================================
  // Effect: Load on mount
  // ===================================
  useEffect(() => {
    loadExtensions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Handlers
  // ===================================
  const handleCardClick = (extension: ExtensionRow) => {
    setSelectedExtension(extension)
    setDrawerOpen(true)
  }

  const handleToggleExtension = async (extensionId: string, currentStatus: 'enabled' | 'disabled') => {
    setToggling(extensionId)
    try {
      if (currentStatus === 'enabled') {
        await skillosService.disableExtension(extensionId)
        toast.success(t('page.extensions.disableSuccess'))
      } else {
        await skillosService.enableExtension(extensionId)
        toast.success(t('page.extensions.enableSuccess'))
      }
      // Reload to get updated status
      await loadExtensions()

      // Update selected extension if drawer is open
      if (selectedExtension && selectedExtension.id === extensionId) {
        const updatedExt = extensions.find(e => e.id === extensionId)
        if (updatedExt) {
          setSelectedExtension(extensionToRow(updatedExt))
        }
      }
    } catch (error) {
      console.error('Failed to toggle extension:', error)
      toast.error(currentStatus === 'enabled' ? t('page.extensions.disableFailed') : t('page.extensions.enableFailed'))
    } finally {
      setToggling(null)
    }
  }

  const handleDelete = async () => {
    if (!selectedExtension) return

    setDeleting(true)
    try {
      await skillosService.deleteExtension(selectedExtension.id)
      toast.success(t('page.extensions.deleteSuccess'))
      setDeleteDialogOpen(false)
      setDrawerOpen(false)
      setSelectedExtension(null)
      // Reload extensions
      await loadExtensions()
    } catch (error) {
      console.error('Failed to delete extension:', error)
      toast.error(t('page.extensions.deleteFailed'))
    } finally {
      setDeleting(false)
    }
  }

  // Status tag mapping
  const getStatusTag = (status: ExtensionRow['status']) => {
    const tagMap: Record<ExtensionRow['status'], string> = {
      enabled: t('common.enabled'),
      disabled: t('common.disabled'),
    }
    return tagMap[status]
  }

  // ===================================
  // Render
  // ===================================

  // Loading state
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    )
  }

  // Empty state
  if (extensions.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <ExtensionIcon sx={{ fontSize: 64, color: COLOR_TEXT_SECONDARY, mb: 2 }} />
        <Typography variant={VARIANT_H6} color={COLOR_TEXT_SECONDARY} gutterBottom>
          {t('page.extensions.noExtensions')}
        </Typography>
        <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
          {t('page.extensions.noExtensionsDesc')}
        </Typography>
      </Box>
    )
  }

  const extensionRows = extensions.map(extensionToRow)

  return (
    <>
      <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16}>
        {extensionRows.map((extension, index) => (
          <ItemCard
            key={extension.id}
            title={extension.name}
            description={extension.description}
            meta={[
              { key: 'version', label: t(K.page.extensions.columnVersion), value: extension.version },
              { key: 'author', label: t(K.page.extensions.columnAuthor), value: extension.author },
              { key: 'installed', label: t(K.page.extensions.columnInstalledAt), value: extension.installedAt },
            ]}
            tags={[getStatusTag(extension.status)]}
            icon={getExtensionIcon(index)}
            actions={[
              {
                key: 'view',
                label: t('common.view'),
                variant: 'outlined',
                onClick: () => handleCardClick(extension),
              },
              {
                key: 'toggle',
                label: extension.status === 'enabled' ? t('common.disable') : t('common.enable'),
                variant: 'contained',
                onClick: () => handleToggleExtension(extension.id, extension.status),
                disabled: toggling === extension.id,
              },
            ]}
            onClick={() => handleCardClick(extension)}
          />
        ))}
      </CardCollectionWrap>

      {/* Detail Drawer */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedExtension?.name || ''}
        actions={
          <>
            <Button
              variant={VARIANT_CONTAINED}
              color={selectedExtension?.status === 'enabled' ? COLOR_WARNING : COLOR_SUCCESS}
              onClick={() => {
                if (selectedExtension) {
                  handleToggleExtension(selectedExtension.id, selectedExtension.status)
                }
              }}
              disabled={!!toggling}
            >
              {toggling === selectedExtension?.id ? (
                <CircularProgress size={20} />
              ) : (
                selectedExtension?.status === 'enabled' ? t('common.disable') : t('common.enable')
              )}
            </Button>
            <Button
              variant={VARIANT_OUTLINED}
              onClick={() => {
                setDrawerOpen(false)
                setConfigureDialogOpen(true)
              }}
            >
              {t(K.page.extensions.configure)}
            </Button>
            <Button
              variant={VARIANT_OUTLINED}
              color={COLOR_ERROR}
              onClick={() => {
                setDrawerOpen(false)
                setDeleteDialogOpen(true)
              }}
              disabled={deleting}
            >
              {t('common.delete')}
            </Button>
          </>
        }
      >
        {selectedExtension && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Version */}
            <Box>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.extensions.columnVersion)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedExtension.version}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.extensions.columnStatus)}
              </Typography>
              <Chip
                label={selectedExtension.status}
                color={selectedExtension.status === 'enabled' ? COLOR_SUCCESS : COLOR_DEFAULT}
                size={SIZE_SMALL}
              />
            </Box>

            {/* Author */}
            <Box>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.extensions.columnAuthor)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedExtension.author}</Typography>
            </Box>

            {/* Description */}
            <Box>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.extensions.columnDescription)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedExtension.description}</Typography>
            </Box>

            {/* Installed At */}
            <Box>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.extensions.columnInstalledAt)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedExtension.installedAt}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Delete Confirm Dialog */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType={RESOURCE_TYPE_EXTENSION}
        resourceName={selectedExtension?.name}
      />

      {/* Upload Extension Dialog */}
      <UploadExtensionDialog
        open={uploadDialogOpen}
        onClose={() => setUploadDialogOpen(false)}
        onSuccess={() => {
          loadExtensions()
        }}
      />

      {/* Install from URL Dialog */}
      <InstallUrlDialog
        open={installUrlDialogOpen}
        onClose={() => setInstallUrlDialogOpen(false)}
        onSuccess={() => {
          loadExtensions()
        }}
      />

      {/* Configure Extension Dialog */}
      {selectedExtension && (
        <ConfigureExtensionDialog
          open={configureDialogOpen}
          onClose={() => {
            setConfigureDialogOpen(false)
            // Optionally reopen drawer
            setTimeout(() => setDrawerOpen(true), 100)
          }}
          onSuccess={() => {
            loadExtensions()
          }}
          extensionId={selectedExtension.id}
          extensionName={selectedExtension.name}
        />
      )}
    </>
  )
}
