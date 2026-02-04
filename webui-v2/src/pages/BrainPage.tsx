/**
 * BrainPage - Brain 控制台页面
 *
 * 🔒 Phase 6.1 Cleanup - Batch 5:
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Four States: Loading/Error/Empty/Success
 * - ⚠️ API Status: Pending backend implementation
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard } from '@/ui'
import { BrainIcon, MemoryIcon, SpeedIcon } from '@/ui/icons'
import { useTextTranslation, K } from '@/ui/text'
import { brainosService } from '@/services/brainos.service'

/**
 * BrainPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3 columns, 3 StatCard + 3 MetricCard
 */
export default function BrainPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<any>(null)
  const [coverage, setCoverage] = useState<any>(null)
  const [blindSpots, setBlindSpots] = useState<any>(null)

  // ===================================
  // Data Fetching - Real API
  // ===================================
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch all brain data in parallel (V1 pattern)
      const [statsRes, coverageRes, blindSpotsRes] = await Promise.all([
        brainosService.getBrainStats(),
        brainosService.getBrainCoverage(),
        brainosService.getBrainBlindSpots(10)
      ])

      if (statsRes.ok && coverageRes.ok && blindSpotsRes.ok) {
        setStats(statsRes.data)
        setCoverage(coverageRes.data)
        setBlindSpots(blindSpotsRes.data)
      } else {
        setError('Failed to load brain dashboard data')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch brain stats')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.brainConsole.title'),
    subtitle: t('page.brainConsole.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        await fetchData()
      },
    },
    {
      key: 'optimize',
      label: t('page.brainConsole.optimize'),
      variant: 'contained',
      onClick: async () => {
        if (window.confirm('Rebuild BrainOS index? This may take a few minutes.')) {
          try {
            const result = await brainosService.buildBrainIndex(false)
            if (result.ok) {
              alert('Index build started successfully!')
              await fetchData()
            } else {
              alert(`Build failed: ${result.error || 'Unknown error'}`)
            }
          } catch (err) {
            alert(`Build failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
          }
        }
      },
    },
  ])

  // ===================================
  // Derived Data - StatCards from API
  // ===================================
  const statCards = stats ? [
    {
      title: t('page.brainConsole.statGraphNodes'),
      value: (stats.entities || 0).toLocaleString(),
      change: '',
      changeType: 'increase' as const,
      icon: <BrainIcon />,
    },
    {
      title: t('page.brainConsole.statRelationships'),
      value: (stats.edges || 0).toLocaleString(),
      change: '',
      changeType: 'increase' as const,
      icon: <MemoryIcon />,
    },
    {
      title: t('page.brainConsole.statCoverage'),
      value: coverage ? `${(coverage.code_coverage * 100).toFixed(1)}%` : '0%',
      change: '',
      changeType: 'increase' as const,
      icon: <SpeedIcon />,
    },
  ] : []

  // ===================================
  // Derived Data - MetricCards from API
  // ===================================
  const metricCards = coverage && blindSpots ? [
    {
      title: t('page.brainConsole.metricKnowledgeHealth'),
      description: t('page.brainConsole.metricKnowledgeHealthDesc'),
      metrics: [
        {
          key: 'code',
          label: 'Code Coverage',
          value: `${(coverage.code_coverage * 100).toFixed(1)}%`,
          valueColor: coverage.code_coverage >= 0.7 ? 'success.main' : coverage.code_coverage >= 0.4 ? 'warning.main' : 'error.main'
        },
        {
          key: 'doc',
          label: 'Doc Coverage',
          value: `${(coverage.doc_coverage * 100).toFixed(1)}%`,
          valueColor: coverage.doc_coverage >= 0.7 ? 'success.main' : coverage.doc_coverage >= 0.4 ? 'warning.main' : 'error.main'
        },
        {
          key: 'dep',
          label: 'Dependency Coverage',
          value: `${(coverage.dependency_coverage * 100).toFixed(1)}%`,
          valueColor: coverage.dependency_coverage >= 0.7 ? 'success.main' : coverage.dependency_coverage >= 0.4 ? 'warning.main' : 'error.main'
        },
      ],
    },
    {
      title: t('page.brainConsole.metricRecentUpdates'),
      description: t('page.brainConsole.metricRecentUpdatesDesc'),
      metrics: [
        { key: 'total_files', label: 'Total Files', value: coverage.total_files.toString() },
        { key: 'covered', label: 'Covered Files', value: coverage.covered_files.toString() },
        { key: 'uncovered', label: 'Uncovered Files', value: coverage.uncovered_files.length.toString() },
      ],
    },
    {
      title: 'Blind Spots',
      description: 'Areas where BrainOS knows it doesn\'t know',
      metrics: [
        { key: 'total', label: 'Total Blind Spots', value: blindSpots.total_blind_spots.toString() },
        { key: 'high', label: 'High Severity', value: blindSpots.by_severity.high.toString(), valueColor: 'error.main' },
        { key: 'medium', label: 'Medium Severity', value: blindSpots.by_severity.medium.toString(), valueColor: 'warning.main' },
      ],
    },
  ] : []

  // ===================================
  // Render: DashboardGrid Pattern with States
  // ===================================
  if (loading) {
    return <DashboardGrid columns={3} gap={16}><div>{t(K.component.loadingState.loading)}</div></DashboardGrid>
  }

  if (error) {
    return <DashboardGrid columns={3} gap={16}><div>Error: {error}</div></DashboardGrid>
  }

  // Empty state: No index built yet
  if (stats && !stats.last_build) {
    return (
      <DashboardGrid columns={2} gap={16}>
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <h3>{t('page.brainConsole.noIndexTitle')}</h3>
          <p>{t('page.brainConsole.noIndexDesc')}</p>
          <button
            onClick={async () => {
              if (window.confirm(t('page.brainConsole.buildIndexConfirm'))) {
                try {
                  const result = await brainosService.buildBrainIndex(false)
                  if (result.ok) {
                    alert(t('page.brainConsole.buildIndexSuccess'))
                    await fetchData()
                  } else {
                    alert(`${t('page.brainConsole.buildIndexFailed')}: ${result.error || 'Unknown error'}`)
                  }
                } catch (err) {
                  alert(`${t('page.brainConsole.buildIndexFailed')}: ${err instanceof Error ? err.message : 'Unknown error'}`)
                }
              }
            }}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              fontSize: '1rem',
              cursor: 'pointer'
            }}
          >
            {t('page.brainConsole.buildIndexNow')}
          </button>
        </div>
      </DashboardGrid>
    )
  }

  return (
    <DashboardGrid columns={3} gap={16}>
      {/* Row 1: Stat Cards */}
      {statCards.map((stat, index) => (
        <StatCard
          key={index}
          title={stat.title}
          value={stat.value}
          change={stat.change}
          changeType={stat.changeType}
          icon={stat.icon}
          onClick={() => {
            console.log('View stat details')
          }}
        />
      ))}

      {/* Row 2: Metric Cards */}
      {metricCards.map((metric, index) => (
        <MetricCard
          key={index}
          title={metric.title}
          description={metric.description}
          metrics={metric.metrics}
          actions={[
            {
              key: 'view',
              label: t('common.view'),
              onClick: () => {
                console.log('View metric details')
              },
            },
          ]}
        />
      ))}
    </DashboardGrid>
  )
}
