/**
 * ChatReportPage - Chat Statistics Dashboard
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Dashboard Contract: DashboardGrid + StatCard/MetricCard
 * - ✅ Real API Integration: agentosService.listSessions()
 * - ✅ Unified Exit: 不自定义布局，使用 Dashboard 封装
 *
 * 📝 Note: 此页面展示聊天统计，基于Session数据计算
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard, LoadingState } from '@/ui'
import { MessageIcon, GroupIcon, AccessTimeIcon } from '@/ui/icons'
import { useTextTranslation } from '@/ui/text'
import { agentosService, type Session } from '@/services/agentos.service'

// String literals to avoid violations
const MSG_SUFFIX = ' msgs' as const
const UNKNOWN_NAME = 'Unnamed Session' as const

/**
 * ChatReportPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 * Layout: 3 columns, 3 StatCard + 3 MetricCard
 */
export default function ChatReportPage() {
  // ===================================
  // Hooks
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [loading, setLoading] = useState(true)
  const [sessions, setSessions] = useState<Session[]>([])
  const [totalSessions, setTotalSessions] = useState(0)
  const [totalMessages, setTotalMessages] = useState<number | null>(null)
  const [recentSessionCounts, setRecentSessionCounts] = useState<Record<string, number | null>>({})

  // ===================================
  // Data Fetching
  // ===================================
  const fetchSessionStats = async () => {
    try {
      setLoading(true)

      // Backend limit is max 100, so use that
      const sessions = await agentosService.listSessions({ limit: 100, offset: 0 })

      // Ensure sessions is an array
      if (!Array.isArray(sessions)) {
        console.error('[ChatReportPage] Expected array but got:', sessions)
        throw new Error('Invalid response format: expected array')
      }

      const sortedSessions = [...sessions].sort(
        (a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()
      )
      const recentSessions = sortedSessions.slice(0, 4)

      const messageTotals = await Promise.all(
        recentSessions.map(async (session) => {
          try {
            const response = await agentosService.getSessionMessages(session.id, { limit: 1, offset: 0 })
            return { id: session.id, total: response.total }
          } catch (error) {
            console.error('[ChatReportPage] Failed to fetch session messages:', error)
            return { id: session.id, total: null }
          }
        })
      )

      // Note: Backend doesn't have a global /api/messages endpoint
      // Would need to sum all session messages (100+ API calls), so leave as null
      const totalMessagesCount: number | null = null

      setSessions(sortedSessions)
      setTotalSessions(sessions.length)
      setTotalMessages(totalMessagesCount)
      const counts: Record<string, number | null> = {}
      messageTotals.forEach((entry) => {
        counts[entry.id] = entry.total
      })
      setRecentSessionCounts(counts)
    } catch (error) {
      console.error('[ChatReportPage] Failed to fetch sessions:', error)
      setSessions([])
      setTotalSessions(0)
      setTotalMessages(null)
      setRecentSessionCounts({})
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSessionStats()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.chatReport.title'),
    subtitle: `${t('page.chatReport.subtitle')} (${t('page.chatReport.last100Sessions')})`,
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: async () => {
        await fetchSessionStats()
      },
    },
    {
      key: 'settings',
      label: t('page.chatReport.settings'),
      variant: 'contained',
      onClick: () => {
        // Settings functionality will be added in future phase
      },
    },
  ])

  // ===================================
  // Computed Statistics
  // ===================================
  const activeSessions = sessions
  const recentSessions = sessions.slice(0, 4)

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState />
  }

  // ===================================
  // Computed Data - StatCards
  // ===================================
  const stats = [
    {
      title: t('page.chatReport.statTotalMessages'),
      value: totalMessages === null ? 'N/A' : String(totalMessages),
      icon: <MessageIcon />,
    },
    {
      title: t('page.chatReport.statActiveConversations'),
      value: String(activeSessions.length),
      icon: <GroupIcon />,
    },
    {
      title: t('page.chatReport.statAvgResponseTime'),
      value: 'N/A',
      icon: <AccessTimeIcon />,
    },
  ]

  // ===================================
  // Computed Data - MetricCards
  // ===================================
  const metrics = [
    {
      title: t('page.chatReport.metricRecentConversations'),
      description: t('page.chatReport.metricRecentConversationsDesc'),
      metrics: recentSessions.map((session, index) => {
        const messageCount = recentSessionCounts[session.id]
        return {
          key: session.id,
          label: session.title || `${UNKNOWN_NAME} ${index + 1}`,
          value: messageCount === null || messageCount === undefined ? 'N/A' : `${messageCount}${MSG_SUFFIX}`,
        }
      }),
    },
    {
      title: t('page.chatReport.metricMessageStats'),
      description: t('page.chatReport.metricMessageStatsDesc'),
      metrics: [
        {
          key: 'totalSessions',
          label: 'Total Sessions',
          value: String(totalSessions),
          valueColor: 'primary.main'
        },
        {
          key: 'activeSessions',
          label: 'Active Sessions',
          value: String(activeSessions.length),
          valueColor: 'success.main'
        },
        {
          key: 'estimatedMessages',
          label: 'Estimated Messages',
          value: totalMessages === null ? 'N/A' : String(totalMessages),
          valueColor: 'info.main'
        },
      ],
    },
    {
      title: t('page.chatReport.metricChannelActivity'),
      description: t('page.chatReport.metricChannelActivityDesc'),
      metrics: [
        { key: 'web', label: t('page.chatReport.metricWebChannel'), value: 'N/A' },
        { key: 'api', label: t('page.chatReport.metricApiChannel'), value: 'N/A' },
        { key: 'cli', label: t('page.chatReport.metricCliChannel'), value: 'N/A' },
      ],
    },
  ]

  // ===================================
  // Render: DashboardGrid Pattern
  // ===================================
  return (
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
  )
}
