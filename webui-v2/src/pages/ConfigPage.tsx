/**
 * ConfigPage - Configuration Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ API Integration: agentosService.getConfig()
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect, useMemo } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState, Box } from '@/ui'
import { SettingsIcon, CheckCircleIcon, LayersIcon } from '@/ui/icons'
import { useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { systemService, type Config, type ConfigEntry } from '@services'
import { ConfigEntriesContent } from './ConfigEntriesPage'

/**
 * ConfigPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3 columns, 3 StatCard + 3 MetricCard
 */
export default function ConfigPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const [entries, setEntries] = useState<ConfigEntry[]>([])
  const [entriesTotal, setEntriesTotal] = useState(0)

  // ===================================
  // Data Fetching - API Integration
  // ===================================
  useEffect(() => {
    const fetchConfig = async () => {
      setLoading(true)
      setError(null)
      try {
        const [configResponse, entriesResponse] = await Promise.all([
          systemService.getConfig(),
          systemService.listConfigEntries({ page: 1, limit: 200 }),
        ])
        setConfig(configResponse.config)
        setEntries(entriesResponse.entries || [])
        setEntriesTotal(entriesResponse.total || 0)
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Failed to fetch config'
        setError(errorMsg)
        toast.error(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    fetchConfig()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.config.title'),
    subtitle: t('page.config.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        setLoading(true)
        setError(null)
        try {
          const [configResponse, entriesResponse] = await Promise.all([
            systemService.getConfig(),
            systemService.listConfigEntries({ page: 1, limit: 200 }),
          ])
          setConfig(configResponse.config)
          setEntries(entriesResponse.entries || [])
          setEntriesTotal(entriesResponse.total || 0)
          toast.success(t('common.success'))
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to refresh'
          setError(errorMsg)
          toast.error(errorMsg)
        } finally {
          setLoading(false)
        }
      },
    },
  ])

  const configPairs = useMemo(() => {
    if (!config) return []
    return Object.entries(config).map(([key, value]) => ({
      key,
      value,
    }))
  }, [config])

  const formatConfigValue = (value: unknown) => {
    if (value === null || value === undefined) return 'N/A'
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return String(value)
    }
    try {
      const text = JSON.stringify(value)
      return text.length > 80 ? `${text.slice(0, 77)}...` : text
    } catch {
      return 'N/A'
    }
  }

  const scopedCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    entries.forEach((entry) => {
      if (!entry.scope) return
      counts[entry.scope] = (counts[entry.scope] || 0) + 1
    })
    return counts
  }, [entries])

  const stats = [
    {
      title: t('page.config.statTotalSettings'),
      value: String(entriesTotal),
      icon: <SettingsIcon />,
    },
    {
      title: t('page.config.statModified'),
      value: String(Object.keys(scopedCounts).length || 0),
      icon: <CheckCircleIcon />,
    },
    {
      title: t('page.config.statDefault'),
      value: config ? String(Object.keys(config).length) : 'N/A',
      icon: <LayersIcon />,
    },
  ]

  const metrics = [
    {
      title: t('page.config.metricSystemConfig'),
      description: t('page.config.metricSystemConfigDesc'),
      metrics: configPairs.slice(0, 4).map((pair) => ({
        key: pair.key,
        label: pair.key,
        value: formatConfigValue(pair.value),
      })),
    },
    {
      title: t('page.config.metricUserPreferences'),
      description: t('page.config.metricUserPreferencesDesc'),
      metrics: configPairs.slice(4, 8).map((pair) => ({
        key: pair.key,
        label: pair.key,
        value: formatConfigValue(pair.value),
      })),
    },
    {
      title: t('page.config.metricAdvancedSettings'),
      description: t('page.config.metricAdvancedSettingsDesc'),
      metrics: configPairs.slice(8, 12).map((pair) => ({
        key: pair.key,
        label: pair.key,
        value: formatConfigValue(pair.value),
      })),
    },
  ].map((metric) => ({
    ...metric,
    metrics: metric.metrics.length > 0 ? metric.metrics : [
      { key: 'none', label: t('common.info'), value: 'N/A' },
    ],
  }))

  // ===================================
  // Render: DashboardGrid Pattern with States
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  if (error) {
    return <DashboardGrid columns={3} gap={16}><div>Error: {error}</div></DashboardGrid>
  }

  return (
    <>
      <DashboardGrid columns={3} gap={16}>
        {/* Row 1: Stat Cards */}
        {stats.map((stat, index) => (
          <StatCard
            key={index}
            title={stat.title}
            value={stat.value}
            icon={stat.icon}
          />
        ))}

        {/* Row 2: Metric Cards */}
        {metrics.map((metric, index) => (
          <MetricCard
            key={index}
            title={metric.title}
            description={metric.description}
            metrics={metric.metrics}
          />
        ))}
      </DashboardGrid>

      <Box sx={{ mt: 3 }}>
        <ConfigEntriesContent readOnly />
      </Box>
    </>
  )
}
