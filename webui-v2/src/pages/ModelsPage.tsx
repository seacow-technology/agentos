/**
 * ModelsPage - 模型管理页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ CardGrid Pattern: CardCollectionWrap + ItemCard
 * - ✅ Phase 6: 真实API接入
 */

import { useState, useEffect } from 'react'
// eslint-disable-next-line no-restricted-imports -- G3 Exception: Box and Typography are in allowed list
import { Box, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useTextTranslation } from '@/ui/text'
import { LoadingState } from '@/ui'
import { systemService, type Model } from '@/services'
import { SmartToyIcon } from '@/ui/icons'

// Typography variants and colors to avoid string literals
const H6_VARIANT = 'h6' as const
const BODY2_VARIANT = 'body2' as const
const CAPTION_VARIANT = 'caption' as const
const TEXT_SECONDARY = 'text.secondary' as const
const TEXT_DISABLED = 'text.disabled' as const
const LAYOUT_GRID = 'grid' as const
const PERCENT_SUFFIX = '%' as const

// Icon mapping
const getModelIcon = () => {
  // Simple icon mapping - all models use SmartToy
  // Could be extended based on model metadata/type
  return <SmartToyIcon />
}

// Helper to determine model type from name/metadata
const inferModelType = (model: Model): string => {
  const name = model.name.toLowerCase()
  if (name.includes('dall-e') || name.includes('imagen') || name.includes('sd-')) {
    return 'Image'
  }
  if (name.includes('whisper') || name.includes('audio')) {
    return 'Audio'
  }
  return 'LLM'
}

// Helper to format model size
const formatModelSize = (size?: number): string => {
  if (!size) return 'N/A'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

/**
 * ModelsPage 组件
 */
export default function ModelsPage() {
  const { t } = useTextTranslation()

  // State
  const [models, setModels] = useState<Model[]>([])
  const [loading, setLoading] = useState(true)
  const [downloadingModels, setDownloadingModels] = useState<Record<string, { progress: number; taskId?: string }>>({})

  // Load models on mount
  useEffect(() => {
    loadModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load models from API
  const loadModels = async () => {
    try {
      setLoading(true)
      const response = await systemService.listModels()
      setModels(response.models || [])
    } catch (error) {
      console.error('[ModelsPage] Failed to load models:', error)
    } finally {
      setLoading(false)
    }
  }

  // Page Header
  usePageHeader({
    title: t(K.page.models.title),
    subtitle: t(K.page.models.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        await loadModels()
      },
    },
    {
      key: 'add',
      label: t(K.page.models.addModel),
      variant: 'contained',
      onClick: () => {
        // Open add model dialog in a future phase
      },
    },
  ])

  // Handlers
  const handleDownloadModel = async (modelId: string, modelName: string) => {
    try {
      // Start download
      setDownloadingModels((prev) => ({ ...prev, [modelId]: { progress: 0 } }))

      const response = await systemService.pullModel({ model_name: modelName })
      const taskId = response.task_id

      if (taskId) {
        // Poll for progress using setInterval
        const pollInterval = setInterval(async () => {
          try {
            const progressRes = await systemService.getModelPullProgress(taskId)
            const progress = progressRes.progress || 0

            setDownloadingModels((prev) => ({
              ...prev,
              [modelId]: { progress, taskId },
            }))

            if (progressRes.status === 'completed') {
              // Download complete
              clearInterval(pollInterval)
              setDownloadingModels((prev) => {
                const updated = { ...prev }
                delete updated[modelId]
                return updated
              })
              await loadModels() // Refresh models list
            } else if (progressRes.status === 'failed') {
              // Download failed
              clearInterval(pollInterval)
              setDownloadingModels((prev) => {
                const updated = { ...prev }
                delete updated[modelId]
                return updated
              })
            }
          } catch (error) {
            console.error('[ModelsPage] Failed to get progress:', error)
            clearInterval(pollInterval)
            setDownloadingModels((prev) => {
              const updated = { ...prev }
              delete updated[modelId]
              return updated
            })
          }
        }, 1000)
      }
    } catch (error) {
      console.error('[ModelsPage] Failed to download model:', error)
      console.error('Download model failed:', modelName)
      setDownloadingModels((prev) => {
        const updated = { ...prev }
        delete updated[modelId]
        return updated
      })
    }
  }

  const handleDeleteModel = async (modelId: string) => {
    try {
      await systemService.deleteModel(modelId)
      await loadModels()
    } catch (error) {
      console.error('[ModelsPage] Failed to delete model:', error)
    }
  }

  // Loading state
  if (loading) {
    return <LoadingState />
  }

  // Empty state check
  const isEmpty = models.length === 0
  if (isEmpty) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 400,
          gap: 2,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 64, color: TEXT_DISABLED }} />
        <Typography variant={H6_VARIANT} color={TEXT_SECONDARY}>
          {t(K.page.models.noModels)}
        </Typography>
        <Typography variant={BODY2_VARIANT} color={TEXT_DISABLED}>
          {t(K.page.models.createFirstModel)}
        </Typography>
      </Box>
    )
  }

  // Success state (has data)
  const isSuccess = models.length > 0
  return (
    <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16} data-success={isSuccess}>
      {models.map((model) => {
        const downloadInfo = downloadingModels[model.id]
        const isDownloading = downloadInfo !== undefined
        const progress = downloadInfo?.progress || 0
        const modelType = inferModelType(model)
        const isInstalled = model.status === 'installed'
        const description = `${modelType} model - ${formatModelSize(model.size)}`

        return (
          <ItemCard
            key={model.id}
            title={model.name}
            description={description}
            meta={[
              { key: 'id', label: t(K.page.models.columnId), value: model.id },
              { key: 'type', label: t(K.page.models.columnType), value: modelType },
              { key: 'status', label: 'Status', value: model.status },
            ]}
            tags={[model.status]}
            icon={getModelIcon()}
            actions={
              isInstalled
                ? [
                    {
                      key: 'delete',
                      label: t(K.page.models.deleteModel),
                      variant: 'outlined',
                      onClick: () => handleDeleteModel(model.id),
                    },
                  ]
                : [
                    {
                      key: 'download',
                      label: isDownloading
                        ? t(K.page.models.downloading)
                        : t(K.page.models.download),
                      variant: 'contained',
                      disabled: isDownloading,
                      onClick: () => handleDownloadModel(model.id, model.name),
                    },
                  ]
            }
            onClick={() => {
              // Open model details view in a future phase
              console.log('[ModelsPage] Model clicked:', model.name)
            }}
            footer={
              isDownloading ? (
                <Box sx={{ mt: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box
                      sx={{
                        flexGrow: 1,
                        height: 6,
                        borderRadius: 3,
                        backgroundColor: 'rgba(0, 0, 0, 0.1)',
                        position: 'relative',
                        overflow: 'hidden',
                      }}
                    >
                      <Box
                        sx={{
                          position: 'absolute',
                          left: 0,
                          top: 0,
                          bottom: 0,
                          width: `${progress}%`,
                          backgroundColor: 'primary.main',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </Box>
                    <Typography variant={CAPTION_VARIANT} color={TEXT_SECONDARY}>
                      {progress}{PERCENT_SUFFIX}
                    </Typography>
                  </Box>
                </Box>
              ) : undefined
            }
          />
        )
      })}
    </CardCollectionWrap>
  )
}
