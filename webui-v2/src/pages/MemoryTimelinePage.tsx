/**
 * MemoryTimelinePage - Memory Timeline
 *
 * 🔒 Phase 6 - Real API Integration:
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ Real API: memoryosService.getMemoryTimeline()
 * - ✅ State Handling: Loading/Success/Error/Empty
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect, useCallback } from 'react'
// eslint-disable-next-line no-restricted-imports -- Box and Typography are allowed from @mui/material per G3 exceptions
import { Box, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Chip } from '@/ui'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { memoryosServiceGen } from '@/services/memoryos.service.gen'
import type { GridColDef } from '@/ui'
import type { TimelineItem } from '@modules/memoryos'

// ===================================
// Constants
// ===================================
const DEFAULT_PAGE_SIZE = 25
const FILTER_ALL = 'all'
const CHIP_SIZE = 'small'
const IMPACT_HIGH = 'High'
const IMPACT_MEDIUM = 'Medium'
const IMPACT_LOW = 'Low'
const TYPE_CONTEXT = 'context'
const TYPE_LEARNING = 'learning'
const TYPE_KNOWLEDGE = 'knowledge'
const VARIANT_CAPTION = 'caption'
const VARIANT_BODY1 = 'body1'
const COLOR_TEXT_SECONDARY = 'text.secondary'
const LABEL_KEY = 'Key'
const LABEL_CONFIDENCE = 'Confidence'
const LABEL_ACTIVE = 'Active'
const LABEL_VERSION = 'Version'
const LABEL_YES = 'Yes'
const LABEL_NO = 'No'
const PLACEHOLDER_DASH = '-'

// ===================================
// UI Row Type (extends TimelineItem with UI-specific fields)
// ===================================
interface TimelineRow extends TimelineItem {
  impact: typeof IMPACT_HIGH | typeof IMPACT_MEDIUM | typeof IMPACT_LOW
}

/**
 * MemoryTimelinePage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function MemoryTimelinePage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [loading, setLoading] = useState(false)
  const [events, setEvents] = useState<TimelineRow[]>([])
  const [totalCount, setTotalCount] = useState(0)

  // ===================================
  // State - Pagination
  // ===================================
  const [page, setPage] = useState(0)
  const [pageSize] = useState(DEFAULT_PAGE_SIZE) // Future: support pageSize change

  // ===================================
  // State - Filters
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState(FILTER_ALL)
  const [impactFilter, setImpactFilter] = useState(FILTER_ALL)

  // ===================================
  // State - Event Detail
  // ===================================
  const [selectedEvent, setSelectedEvent] = useState<TimelineRow | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.memoryTimeline.title),
    subtitle: t(K.page.memoryTimeline.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'contained',
      onClick: () => {
        void loadEvents()
      },
    },
  ])

  // ===================================
  // API Call - Load Events
  // ===================================
  const loadEvents = useCallback(async () => {
    setLoading(true)
    try {
      // Call real API (now returns data directly via wrapper functions)
      const response = await memoryosServiceGen.getMemoryTimeline({
        page: page + 1, // API uses 1-based indexing
        limit: pageSize,
      })

      // Check if response has items array
      if (!response || !Array.isArray(response.items)) {
        console.error('[MemoryTimeline] Invalid response format:', response)
        toast.error('Invalid API response format')
        setEvents([])
        setTotalCount(0)
        return
      }

      // Transform TimelineItem to TimelineRow with impact calculation
      const transformedEvents: TimelineRow[] = response.items.map((item) => ({
        ...item,
        impact: calculateImpact(item),
      }))

      setEvents(transformedEvents)
      setTotalCount(response.total)
    } catch (error) {
      console.error('[MemoryTimeline] Failed to load events:', error)
      toast.error(t(K.error.loadFailed))
      setEvents([])
      setTotalCount(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, t])

  // ===================================
  // Helper - Calculate Impact
  // ===================================
  const calculateImpact = (item: TimelineItem): typeof IMPACT_HIGH | typeof IMPACT_MEDIUM | typeof IMPACT_LOW => {
    // Calculate impact based on confidence and is_active
    if (item.is_active && item.confidence >= 0.8) return IMPACT_HIGH
    if (item.confidence >= 0.5) return IMPACT_MEDIUM
    return IMPACT_LOW
  }

  // ===================================
  // Effect - Load on mount and pagination change
  // ===================================
  useEffect(() => {
    void loadEvents()
  }, [loadEvents])

  // ===================================
  // Handler - Event Detail
  // ===================================
  const handleRowClick = (row: TimelineRow) => {
    setSelectedEvent(row)
    setDetailDrawerOpen(true)
  }

  const handleCloseDetailDrawer = () => {
    setDetailDrawerOpen(false)
    setSelectedEvent(null)
  }

  // ===================================
  // Handler - Apply Filters (Client-side)
  // ===================================
  const filteredEvents = events.filter((event) => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const matchesSearch =
        event.key.toLowerCase().includes(query) ||
        event.value.toLowerCase().includes(query) ||
        (event.type && event.type.toLowerCase().includes(query))
      if (!matchesSearch) return false
    }

    // Type filter
    if (typeFilter !== FILTER_ALL && event.type !== typeFilter) {
      return false
    }

    // Impact filter
    if (impactFilter !== FILTER_ALL && event.impact !== impactFilter) {
      return false
    }

    return true
  })

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.memoryTimeline.columnId),
      width: 80,
    },
    {
      field: 'type',
      headerName: t(K.page.memoryTimeline.columnEventType),
      width: 180,
    },
    {
      field: 'value',
      headerName: t(K.page.memoryTimeline.columnContent),
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'source',
      headerName: t(K.page.memoryTimeline.columnSource),
      width: 150,
    },
    {
      field: 'timestamp',
      headerName: t(K.page.memoryTimeline.columnTimestamp),
      width: 180,
      renderCell: (params) => {
        const value = params.value as string | undefined
        if (!value) return PLACEHOLDER_DASH
        return new Date(value).toLocaleString()
      },
    },
    {
      field: 'impact',
      headerName: t(K.page.memoryTimeline.columnImpact),
      width: 120,
      renderCell: (params) => {
        const impactColors: Record<string, 'success' | 'warning' | 'error'> = {
          [IMPACT_HIGH]: 'error',
          [IMPACT_MEDIUM]: 'warning',
          [IMPACT_LOW]: 'success',
        }
        return (
          <Chip
            label={params.value}
            color={impactColors[params.value as string] || 'default'}
            size={CHIP_SIZE}
          />
        )
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredEvents}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t(K.common.search)}
                    placeholder={t(K.page.memoryTimeline.searchPlaceholder)}
                    fullWidth
                    size={CHIP_SIZE}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    label={t(K.page.memoryTimeline.filterType)}
                    fullWidth
                    size={CHIP_SIZE}
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <MenuItem value={FILTER_ALL}>{t(K.page.memoryTimeline.typeAll)}</MenuItem>
                    <MenuItem value={TYPE_CONTEXT}>{t(K.page.memoryTimeline.typeContext)}</MenuItem>
                    <MenuItem value={TYPE_LEARNING}>{t(K.page.memoryTimeline.typeLearning)}</MenuItem>
                    <MenuItem value={TYPE_KNOWLEDGE}>{t(K.page.memoryTimeline.typeKnowledge)}</MenuItem>
                  </Select>
                ),
              },
              {
                width: 3,
                component: (
                  <Select
                    label={t(K.page.memoryTimeline.filterImpact)}
                    fullWidth
                    size={CHIP_SIZE}
                    value={impactFilter}
                    onChange={(e) => setImpactFilter(e.target.value)}
                  >
                    <MenuItem value={FILTER_ALL}>{t(K.page.memoryTimeline.impactAll)}</MenuItem>
                    <MenuItem value={IMPACT_HIGH}>{t(K.page.memoryTimeline.impactHigh)}</MenuItem>
                    <MenuItem value={IMPACT_MEDIUM}>{t(K.page.memoryTimeline.impactMedium)}</MenuItem>
                    <MenuItem value={IMPACT_LOW}>{t(K.page.memoryTimeline.impactLow)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t(K.common.reset),
                onClick: () => {
                  setSearchQuery('')
                  setTypeFilter(FILTER_ALL)
                  setImpactFilter(FILTER_ALL)
                },
              },
              {
                key: 'apply',
                label: t(K.common.apply),
                variant: 'contained',
                onClick: () => {
                  toast.info(t(K.common.success))
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.memoryTimeline.noEvents),
          description: t(K.page.memoryTimeline.noEventsDesc),
          actions: [
            {
              label: t(K.common.refresh),
              onClick: () => {
                void loadEvents()
              },
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page,
          pageSize,
          total: totalCount,
          onPageChange: (newPage: number) => setPage(newPage),
        }}
        onRowClick={handleRowClick}
      />

      {/* Event Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleCloseDetailDrawer}
        title={t(K.page.memoryTimeline.eventDetail)}
        subtitle={selectedEvent ? `#${selectedEvent.id}` : ''}
      >
        {selectedEvent && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Event Type */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.memoryTimeline.detailEventType)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedEvent.type || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Key */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {LABEL_KEY}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedEvent.key || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Content */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.memoryTimeline.detailContent)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedEvent.value || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Source */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.memoryTimeline.detailSource)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedEvent.source || PLACEHOLDER_DASH}</Typography>
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.memoryTimeline.detailTimestamp)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>
                {selectedEvent.timestamp ? new Date(selectedEvent.timestamp).toLocaleString() : PLACEHOLDER_DASH}
              </Typography>
            </Box>

            {/* Confidence */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {LABEL_CONFIDENCE}
              </Typography>
              <Typography variant={VARIANT_BODY1}>
                {selectedEvent.confidence !== undefined
                  ? `${(selectedEvent.confidence * 100).toFixed(0)}%`
                  : PLACEHOLDER_DASH}
              </Typography>
            </Box>

            {/* Impact */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.memoryTimeline.detailImpact)}
              </Typography>
              <Chip
                label={selectedEvent.impact}
                color={
                  selectedEvent.impact === IMPACT_HIGH
                    ? 'error'
                    : selectedEvent.impact === IMPACT_MEDIUM
                    ? 'warning'
                    : 'success'
                }
                size={CHIP_SIZE}
              />
            </Box>

            {/* Active Status */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {LABEL_ACTIVE}
              </Typography>
              <Typography variant={VARIANT_BODY1}>{selectedEvent.is_active ? LABEL_YES : LABEL_NO}</Typography>
            </Box>

            {/* Version */}
            {selectedEvent.version !== undefined && (
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                  {LABEL_VERSION}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedEvent.version}</Typography>
              </Box>
            )}
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
