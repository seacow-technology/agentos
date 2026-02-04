// @ts-nocheck
/**
 * IndexJobsPage - 索引任务页面
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getIndexJobs()
 * ✅ States: loading, error, empty, success
 * 
 * 🔒 No-Interaction Contract:
 * - 所有 onClick 为空函数
 * - 使用 API 数据
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { agentosService } from '@/services'
import type { GridColDef } from '@/ui'
import { toast } from '@/ui/feedback'


/**
 * IndexJobsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function IndexJobsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()


  // ===================================
  // API State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any[]>([])

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')


  // ===================================
  // API Call
  // ===================================
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const response = await agentosService.getIndexJobs()
        // Transform backend data to frontend format
        const transformedData = (response.data || []).map((job: any) => ({
          id: job.job_id,
          source: job.type,
          status: job.status,
          progress: `${job.progress}%`,
          startedAt: job.created_at,
          completedAt: job.updated_at,
          itemsProcessed: job.files_processed + job.chunks_processed,
        }))
        setData(transformedData)
      } catch (err) {
        console.error('Failed to fetch index jobs:', err)
        setData([]) // Ensure data is always an array even on error
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.indexJobs.title),
    subtitle: t(K.page.indexJobs.subtitle),
  })

  usePageActions([
    {
      key: 'create',
      label: t(K.page.knowledgeJobs.createJob),
      variant: 'contained',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {}, // 🔒 No-Interaction: 空函数
    },
  ])

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.indexJobs.columnId),
      width: 70,
    },
    {
      field: 'source',
      headerName: t(K.page.indexJobs.columnSource),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'status',
      headerName: t(K.page.indexJobs.columnStatus),
      width: 120,
    },
    {
      field: 'progress',
      headerName: t(K.page.indexJobs.columnProgress),
      width: 100,
    },
    {
      field: 'startedAt',
      headerName: t(K.page.indexJobs.columnStartedAt),
      width: 180,
    },
    {
      field: 'completedAt',
      headerName: t(K.page.indexJobs.columnCompletedAt),
      width: 180,
    },
    {
      field: 'itemsProcessed',
      headerName: t(K.page.indexJobs.columnItemsProcessed),
      width: 140,
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <TableShell
      loading={loading}
      rows={data}
      columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 4,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.page.indexJobs.searchPlaceholder)}
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
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                >
                  <MenuItem value="all">{t(K.page.indexJobs.filterAllSources)}</MenuItem>
                  <MenuItem value="docs">{t(K.page.indexJobs.filterDocs)}</MenuItem>
                  <MenuItem value="git">{t(K.page.indexJobs.filterGit)}</MenuItem>
                  <MenuItem value="wiki">{t(K.page.indexJobs.filterWiki)}</MenuItem>
                  <MenuItem value="files">{t(K.page.indexJobs.filterFiles)}</MenuItem>
                  <MenuItem value="web">{t(K.page.indexJobs.filterWeb)}</MenuItem>
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
                  <MenuItem value="all">{t(K.page.indexJobs.filterAllStatus)}</MenuItem>
                  <MenuItem value="pending">{t(K.page.indexJobs.filterPending)}</MenuItem>
                  <MenuItem value="running">{t(K.page.indexJobs.filterRunning)}</MenuItem>
                  <MenuItem value="completed">{t(K.page.indexJobs.filterCompleted)}</MenuItem>
                  <MenuItem value="failed">{t(K.page.indexJobs.filterFailed)}</MenuItem>
                  <MenuItem value="cancelled">{t(K.page.indexJobs.filterCancelled)}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                // 🔒 No-Interaction: 仅重置 state
                setSearchQuery('')
                setSourceFilter('all')
                setStatusFilter('all')
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: () => {}, // 🔒 No-Interaction: 空函数
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.indexJobs.noJobs),
        description: t(K.page.indexJobs.noJobsDesc),
        actions: [
          {
            label: t(K.page.knowledgeJobs.createJob),
            onClick: () => {
              toast.info(t(K.page.knowledgeJobs.createJob))
            },
            variant: 'contained',
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: data?.length || 0,
        onPageChange: () => {}, // 🔒 No-Interaction: 空函数
      }}
      onRowClick={(row) => {
        // 🔒 No-Interaction: 迁移阶段不打开 DetailDrawer
        console.log('Index job row clicked (migration stage):', row)
      }}
    />
  )
}
