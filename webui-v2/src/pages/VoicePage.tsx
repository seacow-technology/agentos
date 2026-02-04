/**
 * VoicePage - Voice Communication Dashboard
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 *
 * Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState } from '@/ui'
import { PhoneIcon, CheckCircleIcon, SpeedIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { Alert } from '@mui/material'

/**
 * VoicePage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 */
export default function VoicePage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hasData, setHasData] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.voice.title),
    subtitle: t(K.page.voice.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {
        fetchData()
      },
    },
    {
      key: 'newCall',
      label: t(K.page.voice.newCall),
      variant: 'contained',
      onClick: () => {
        toast.info(t(K.page.voice.newCall))
      },
    },
  ])

  // ===================================
  // Data Fetching
  // ===================================
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      // API skeleton - ready for real implementation when voiceService is available
      // const response = await voiceService.getVoiceStats()
      // setHasData(response.data.length > 0)

      // Temporary: Set hasData for demo
      setHasData(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setHasData(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // ===================================
  // Mock Data
  // ===================================
  const stats = [
    {
      title: t(K.page.voice.statTotalCalls),
      value: '234',
      change: '+12%',
      changeType: 'increase' as const,
      icon: <PhoneIcon />,
    },
    {
      title: t(K.page.voice.statActiveSessions),
      value: '12',
      change: '+3',
      changeType: 'increase' as const,
      icon: <CheckCircleIcon />,
    },
    {
      title: t(K.page.voice.statAvgDuration),
      value: '3.2min',
      change: '-0.3min',
      changeType: 'decrease' as const,
      icon: <SpeedIcon />,
    },
  ]

  const metrics = [
    {
      title: t(K.page.voice.metricRecentCalls),
      description: t(K.page.voice.metricRecentCallsDesc),
      metrics: [
        { key: 'today', label: t(K.page.voice.today), value: '45' },
        { key: 'week', label: t(K.page.voice.week), value: '234' },
        { key: 'month', label: t(K.page.voice.month), value: '1,042' },
      ],
    },
    {
      title: t(K.page.voice.metricCallQuality),
      description: t(K.page.voice.metricCallQualityDesc),
      metrics: [
        { key: 'excellent', label: t(K.page.voice.excellent), value: '78%', valueColor: 'success.main' },
        { key: 'good', label: t(K.page.voice.good), value: '18%', valueColor: 'success.main' },
        { key: 'fair', label: t(K.page.voice.fair), value: '4%', valueColor: 'warning.main' },
      ],
    },
    {
      title: t(K.page.voice.metricChannelDistribution),
      description: t(K.page.voice.metricChannelDistributionDesc),
      metrics: [
        { key: 'phone', label: t(K.page.voice.phone), value: '45%' },
        { key: 'web', label: t(K.page.voice.web), value: '35%' },
        { key: 'mobile', label: t(K.page.voice.mobile), value: '20%' },
      ],
    },
  ]

  // ===================================
  // Render: DashboardGrid Pattern
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>
  }

  if (!hasData) {
    return <Alert severity="info">{t(K.component.emptyState.noData)}</Alert>
  }

  return (
    <DashboardGrid columns={3} gap={16}>
      {/* Row 1: Stat Cards (3 columns) */}
      {stats.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          change={stat.change}
          changeType={stat.changeType}
          icon={stat.icon}
          onClick={() => {
            toast.info(`${stat.title}: ${stat.value}`)
          }}
        />
      ))}

      {/* Row 2: Metric Cards (3 columns) */}
      {metrics.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          description={metric.description}
          metrics={metric.metrics}
          actions={[
            {
              key: 'details',
              label: t(K.page.voice.viewDetails),
              onClick: () => {
                toast.info(`${t(K.page.voice.viewDetails)}: ${metric.title}`)
              },
            },
          ]}
        />
      ))}
    </DashboardGrid>
  )
}
