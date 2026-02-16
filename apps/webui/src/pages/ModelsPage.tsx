/**
 * ModelsPage - 本地模型管理页面
 *
 * 规格:
 * - 固定三段: Ollama / LM Studio / llama.cpp
 * - 下载/删除在此页面完成
 * - 下载由后端调用 CLI 执行, 并以任务形式回传进度
 * - 输入模型名称前做存在性检测
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Box, Grid, Typography, TextField, Button, LinearProgress, Alert } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useTextTranslation } from '@/ui/text'
import { LoadingState } from '@/ui'
import { systemService, type Model } from '@/services'
import { toast } from '@/ui/feedback'
import { SmartToyIcon } from '@/ui/icons'

const H6_VARIANT = 'h6' as const
const BODY2_VARIANT = 'body2' as const
const CAPTION_VARIANT = 'caption' as const
const TEXT_SECONDARY = 'text.secondary' as const
const TEXT_DISABLED = 'text.disabled' as const

type ProviderId = 'ollama' | 'lmstudio' | 'llamacpp'

const PROVIDERS: Array<{ id: ProviderId; label: string }> = [
  { id: 'ollama', label: 'Ollama' },
  { id: 'lmstudio', label: 'LM Studio' },
  { id: 'llamacpp', label: 'llama.cpp' },
]

const predictArtifactName = (providerId: ProviderId, input: string): string => {
  const source = String(input || '').trim()
  if (!source) return ''
  if (providerId === 'ollama') return source
  if (source.startsWith('http://') || source.startsWith('https://')) {
    return source.split('/').pop() || source
  }
  if (providerId === 'lmstudio' && source.includes('/')) {
    return source.replace(/\//g, '_')
  }
  return source
}

type DownloadState = {
  taskId: string
  progress: number
  status: string
  message?: string
  indeterminate?: boolean
  error?: string | null
}

export default function ModelsPage() {
  const { t } = useTextTranslation()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, Model[]>>({})
  const [inputByProvider, setInputByProvider] = useState<Record<string, string>>({})
  const [downloadsByModelId, setDownloadsByModelId] = useState<Record<string, DownloadState>>({})
  const pollTimers = useRef<Record<string, number>>({})

  const modelNameSetByProvider = useMemo(() => {
    const out: Record<string, Set<string>> = {}
    for (const p of PROVIDERS) {
      const models = modelsByProvider[p.id] || []
      out[p.id] = new Set(models.map((m) => String(m.name)))
    }
    return out
  }, [modelsByProvider])

  const loadProviderModels = async (providerId: ProviderId) => {
    const resp = await systemService.listModelsApiModelsListGet({ provider_id: providerId })
    const models = Array.isArray(resp?.models) ? (resp.models as Model[]) : []
    setModelsByProvider((prev) => ({ ...prev, [providerId]: models }))
  }

  const loadAll = async () => {
    try {
      setLoading(true)
      setError(null)
      await Promise.all(PROVIDERS.map((p) => loadProviderModels(p.id)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load models')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadAll()
    return () => {
      Object.values(pollTimers.current).forEach((id) => window.clearInterval(id))
      pollTimers.current = {}
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
        await loadAll()
      },
    },
  ])

  const startPolling = (modelId: string, taskId: string, providerId: ProviderId, modelName: string) => {
    if (pollTimers.current[taskId]) return
    const timer = window.setInterval(async () => {
      try {
        const res = await systemService.pullModelProgressApiModelsPullTaskIdProgressGet(taskId)
        const progress = Number(res?.progress || 0)
        const status = String(res?.status || 'running')
        setDownloadsByModelId((prev) => ({
          ...prev,
          [modelId]: {
            taskId,
            progress,
            status,
            message: res?.message,
            indeterminate: Boolean(res?.indeterminate),
            error: res?.error || null,
          },
        }))

        if (status === 'completed' || status === 'failed') {
          window.clearInterval(timer)
          delete pollTimers.current[taskId]
          setDownloadsByModelId((prev) => {
            const next = { ...prev }
            delete next[modelId]
            return next
          })
          await loadProviderModels(providerId)
          if (status === 'failed') {
            toast.error(res?.error || t(K.page.models.downloadFailed, { model: modelName }))
          } else {
            toast.success(t(K.page.models.downloadSuccess, { model: modelName }))
          }
        }
      } catch (e) {
        window.clearInterval(timer)
        delete pollTimers.current[taskId]
        toast.error(e instanceof Error ? e.message : 'Failed to poll progress')
        setDownloadsByModelId((prev) => {
          const next = { ...prev }
          delete next[modelId]
          return next
        })
        await loadProviderModels(providerId)
      }
    }, 800)
    pollTimers.current[taskId] = timer
  }

  const handleDownload = async (providerId: ProviderId) => {
    const modelName = String(inputByProvider[providerId] || '').trim()
    if (!modelName) return

    const artifact = predictArtifactName(providerId, modelName)
    if (artifact && modelNameSetByProvider[providerId]?.has(artifact)) {
      toast.warning(t(K.page.models.modelExists))
      return
    }

    try {
      const res = await systemService.pullModelApiModelsPullPost({ model_name: modelName, provider_id: providerId })
      const taskId = String(res?.task_id || '')
      const returnedModelId = String(res?.model?.id || '')
      const returnedModelName = String(res?.model?.name || modelName)
      if (!taskId) {
        toast.error(t(K.page.models.downloadFailed, { model: modelName }))
        return
      }
      const modelId = returnedModelId || `${providerId}:${returnedModelName}`
      setDownloadsByModelId((prev) => ({
        ...prev,
        [modelId]: { taskId, progress: 0, status: 'running' },
      }))
      setInputByProvider((prev) => ({ ...prev, [providerId]: '' }))
      await loadProviderModels(providerId)
      startPolling(modelId, taskId, providerId, returnedModelName)
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || e?.message || t(K.page.models.downloadFailed))
      toast.error(detail)
      await loadProviderModels(providerId)
    }
  }

  const handleDelete = async (providerId: ProviderId, model: Model) => {
    try {
      await systemService.deleteModelApiModelsModelIdDelete(model.id)
      await loadProviderModels(providerId)
      toast.success(t(K.page.models.deleteSuccess, { model: model.name }))
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || e?.message || t(K.page.models.deleteFailed, { model: model.name }))
      toast.error(detail)
    }
  }

  if (loading) return <LoadingState />

  return (
    <Box>
      {error && (
        <Box sx={{ mb: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      {PROVIDERS.map((p) => {
        const models = modelsByProvider[p.id] || []
        return (
          <Box key={p.id} sx={{ mb: 4 }}>
            <Typography variant={H6_VARIANT} sx={{ mb: 1 }}>
              {t(K.page.models.sectionTitle, { provider: p.label, count: models.length })}
            </Typography>

            <Grid container spacing={1} alignItems="center" sx={{ mb: 2 }}>
              <Grid item xs={12} md>
                <TextField
                  size="small"
                  label={t(K.page.models.modelName)}
                  placeholder={t(K.page.models.inputPlaceholder)}
                  value={inputByProvider[p.id] || ''}
                  onChange={(e) => setInputByProvider((prev) => ({ ...prev, [p.id]: e.target.value }))}
                  fullWidth
                />
              </Grid>
              <Grid item xs={12} md="auto">
                <Button
                  variant="contained"
                  onClick={() => handleDownload(p.id)}
                  disabled={!String(inputByProvider[p.id] || '').trim()}
                  sx={{ minWidth: 140, whiteSpace: 'nowrap' }}
                >
                  {t(K.page.models.download)}
                </Button>
              </Grid>
            </Grid>

            {models.length === 0 ? (
              <Box sx={{ py: 3 }}>
                <Typography variant={BODY2_VARIANT} color={TEXT_SECONDARY}>
                  {t(K.page.models.noModels)}
                </Typography>
                <Typography variant={BODY2_VARIANT} color={TEXT_DISABLED}>
                  {t(K.page.models.createFirstModel)}
                </Typography>
              </Box>
            ) : (
              <CardCollectionWrap layout="grid" columns={3} gap={16}>
                {models.map((m) => {
                  const download = downloadsByModelId[m.id]
                  const isDownloading = m.status === 'downloading' || Boolean(download)
                  const progress = download?.progress || 0
                  const indeterminate = Boolean(download?.indeterminate)
                  const isInstalled = m.status === 'installed'
                  const canDelete = isInstalled && !isDownloading

                  return (
                    <ItemCard
                      key={m.id}
                      title={m.name}
                      description={p.label}
                      meta={[
                        { key: 'id', label: t(K.page.models.columnId), value: m.id },
                        { key: 'status', label: t(K.page.models.columnStatus), value: m.status },
                      ]}
                      tags={[m.status]}
                      icon={<SmartToyIcon />}
                      footer={
                        isDownloading ? (
                          <Box>
                            <Typography variant={CAPTION_VARIANT} color={TEXT_SECONDARY}>
                              {t(K.page.models.downloading)}
                              {download?.message ? `: ${download.message}` : ''}
                            </Typography>
                            <Box sx={{ mt: 1 }}>
                              <LinearProgress
                                variant={indeterminate ? 'indeterminate' : 'determinate'}
                                value={indeterminate ? undefined : progress}
                              />
                            </Box>
                            {!indeterminate && (
                              <Typography variant={CAPTION_VARIANT} color={TEXT_SECONDARY} sx={{ mt: 0.5 }}>
                                {progress}%
                              </Typography>
                            )}
                          </Box>
                        ) : null
                      }
                      actions={[
                        {
                          key: 'delete',
                          label: t(K.page.models.deleteModel),
                          variant: 'outlined',
                          disabled: !canDelete,
                          onClick: () => handleDelete(p.id, m),
                        },
                      ]}
                    />
                  )
                })}
              </CardCollectionWrap>
            )}
          </Box>
        )
      })}
    </Box>
  )
}
