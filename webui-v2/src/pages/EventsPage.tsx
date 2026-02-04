// @ts-nocheck
/**
 * EventsPage - 事件日志页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.events.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 3 Integration: 添加 DetailDrawer
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ Real-time Streaming: Live event updates
 * - ✅ Clear All: Confirmation dialog for dangerous operations
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Box, Typography, Chip, IconButton, Switch, FormControlLabel, Alert, Button } from '@mui/material'
import { ContentCopy as CopyIcon, FilterList as FilterIcon } from '@mui/icons-material'
import { TextField, Select, MenuItem } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { K, useText } from '@/ui/text'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { systemService } from '@/services'

/**
 * Event data structure from API
 */
interface EventRow {
  id?: string
  event_id?: string
  type: string
  timestamp?: string
  created_at?: string
  task_id?: string
  session_id?: string
  message?: string
  description?: string
}

/**
 * EventsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function EventsPage() {
  const [loading, setLoading] = useState(true)
  const [events, setEvents] = useState<any[]>([])

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useText()

  // ===================================
  // State (Filter - 迁移阶段不触发过滤)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedEvent, setSelectedEvent] = useState<EventRow | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Clear All Confirmation Dialog State
  // ===================================
  const [clearDialogOpen, setClearDialogOpen] = useState(false)
  const [clearLoading, setClearLoading] = useState(false)

  // ===================================
  // Real-time Streaming State
  // ===================================
  const [streamMode, setStreamMode] = useState(false)
  const [lastEventTimestamp, setLastEventTimestamp] = useState<string | null>(null)
  const streamIntervalRef = useRef<number | null>(null)
  const STREAM_POLL_INTERVAL = 3000 // 3 seconds

  // ===================================
  // Data Fetching - Real API
  // ===================================
  const fetchEvents = useCallback(async (showToast = false) => {
    setLoading(true)
    try {
      const params: { type?: string; task_id?: string; session_id?: string; limit?: number } = {
        limit: 200,
      }

      if (typeFilter && typeFilter !== 'all') {
        params.type = typeFilter
      }

      const response = await systemService.listEvents(params)
      const eventsData = Array.isArray(response.events) ? response.events : []

      // Sort by timestamp desc
      eventsData.sort((a: any, b: any) => {
        const timeA = new Date(a.timestamp || a.created_at || 0).getTime()
        const timeB = new Date(b.timestamp || b.created_at || 0).getTime()
        return timeB - timeA
      })

      // Update last event timestamp for streaming
      if (eventsData.length > 0) {
        const firstEvent = eventsData[0]
        const timestamp: string | null = (firstEvent.timestamp || firstEvent.created_at) as string || null
        setLastEventTimestamp(timestamp)
      }

      // Client-side filter by search query
      let filtered = eventsData
      if (searchQuery) {
        filtered = eventsData.filter((e: any) => {
          const searchLower = searchQuery.toLowerCase()
          return (
            (e.event_id && e.event_id.includes(searchLower)) ||
            (e.type && e.type.toLowerCase().includes(searchLower)) ||
            (e.message && e.message.toLowerCase().includes(searchLower)) ||
            (e.description && e.description.toLowerCase().includes(searchLower))
          )
        })
      }

      setEvents(filtered)

      if (showToast) {
        toast.success(`Loaded ${filtered.length} event(s)`)
      }
    } catch (err) {
      console.error('Failed to fetch events:', err)
      toast.error('Failed to load events')
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [typeFilter, searchQuery])

  // ===================================
  // Real-time Streaming - Fetch New Events
  // ===================================
  const fetchNewEvents = useCallback(async () => {
    try {
      const params: { type?: string; limit?: number; since?: string } = {
        limit: 50,
      }

      // Only fetch events after the last known timestamp
      if (lastEventTimestamp) {
        params.since = lastEventTimestamp
      }

      // Apply current filters
      if (typeFilter && typeFilter !== 'all') {
        params.type = typeFilter
      }

      const response = await systemService.listEvents(params)
      const newEvents = Array.isArray(response.events) ? response.events : []

      if (newEvents.length > 0) {
        // Prepend new events (avoid duplicates)
        setEvents((prevEvents) => {
          const existingIds = new Set(prevEvents.map((e) => e.event_id || e.id))
          const uniqueNew = newEvents.filter((e) => !existingIds.has(e.event_id || e.id))

          if (uniqueNew.length > 0) {
            // Update last timestamp
            const firstNew = uniqueNew[0]
            const newTimestamp: string | null = (firstNew.timestamp || firstNew.created_at) as string || null
            setLastEventTimestamp(newTimestamp)

            // Show notification
            toast.info(`${uniqueNew.length} new event(s)`)

            // Sort combined events by timestamp desc
            const combined = [...uniqueNew, ...prevEvents]
            combined.sort((a: any, b: any) => {
              const timeA = new Date(a.timestamp || a.created_at || 0).getTime()
              const timeB = new Date(b.timestamp || b.created_at || 0).getTime()
              return timeB - timeA
            })

            return combined
          }

          return prevEvents
        })
      }
    } catch (error) {
      console.error('Failed to fetch new events:', error)
      // Don't show error toast during streaming - just log it
    }
  }, [lastEventTimestamp, typeFilter])

  // ===================================
  // Real-time Streaming - Start/Stop
  // ===================================
  const startStreaming = useCallback(() => {
    if (streamIntervalRef.current) {
      return
    }

    // Initial fetch
    fetchNewEvents()

    // Poll for new events
    streamIntervalRef.current = window.setInterval(() => {
      fetchNewEvents()
    }, STREAM_POLL_INTERVAL)
  }, [fetchNewEvents])

  const stopStreaming = useCallback(() => {
    if (streamIntervalRef.current) {
      clearInterval(streamIntervalRef.current)
      streamIntervalRef.current = null
    }
  }, [])

  // ===================================
  // Stream Mode Toggle Handler
  // ===================================
  const handleStreamToggle = useCallback(
    (enabled: boolean) => {
      setStreamMode(enabled)
      if (enabled) {
        startStreaming()
      } else {
        stopStreaming()
      }
    },
    [startStreaming, stopStreaming]
  )

  // ===================================
  // Clear All Events Handler
  // ===================================
  const handleClearAll = async () => {
    setClearLoading(true)
    try {
      // Note: Backend may not have a clear events API,
      // so we just clear the local state
      setEvents([])
      setLastEventTimestamp(null)
      setClearDialogOpen(false)
      toast.success('All events cleared')
    } catch (error) {
      console.error('Failed to clear events:', error)
      toast.error('Failed to clear events')
    } finally {
      setClearLoading(false)
    }
  }

  // ===================================
  // Initial Load & Cleanup
  // ===================================
  useEffect(() => {
    fetchEvents()

    // Cleanup on unmount
    return () => {
      stopStreaming()
    }
  }, [fetchEvents, stopStreaming])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.events.title),
    subtitle: t(K.page.events.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => fetchEvents(true),
    },
    {
      key: 'clear',
      label: t(K.page.events.clearAll),
      variant: 'outlined',
      color: 'error',
      onClick: () => setClearDialogOpen(true),
      disabled: events.length === 0,
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleRowClick = (row: EventRow) => {
    setSelectedEvent(row)
    setDrawerOpen(true)
  }

  // ===================================
  // Event Action Handlers
  // ===================================
  const handleCopyEventId = useCallback((eventId: string) => {
    navigator.clipboard.writeText(eventId)
    toast.success('Event ID copied to clipboard')
  }, [])

  const handleFilterByType = useCallback((type: string) => {
    setTypeFilter(type)
    setDrawerOpen(false)
    // Trigger refetch with new filter
    setTimeout(() => {
      fetchEvents()
    }, 100)
  }, [fetchEvents])

  // ===================================
  // Helper Functions
  // ===================================
  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return 'N/A'
    try {
      const date = new Date(timestamp)
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    } catch {
      return timestamp
    }
  }

  const renderEventType = (type: string) => {
    const typeMap: Record<string, { color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' }> = {
      'task.created': { color: 'info' },
      'task.started': { color: 'info' },
      'task.completed': { color: 'success' },
      'task.failed': { color: 'error' },
      'session.created': { color: 'info' },
      'session.ended': { color: 'warning' },
      'message.sent': { color: 'default' },
      'message.received': { color: 'default' },
      error: { color: 'error' },
      system: { color: 'secondary' },
    }
    const config = typeMap[type] || { color: 'default' as const }
    return <Chip label={type} color={config.color} size="small" />
  }

  // ===================================
  // Table Columns Definition (aligned with v1)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'timestamp',
      headerName: t(K.page.events.timestamp),
      width: 180,
      renderCell: (params) => formatTimestamp(params.row.timestamp || params.row.created_at),
    },
    {
      field: 'type',
      headerName: t(K.page.events.type),
      width: 200,
      renderCell: (params) => renderEventType(params.value),
    },
    {
      field: 'task_id',
      headerName: t(K.page.events.taskId),
      width: 150,
      renderCell: (params) =>
        params.value ? <code style={{ fontSize: '0.875rem' }}>{params.value.substring(0, 8)}...</code> : 'N/A',
    },
    {
      field: 'session_id',
      headerName: t(K.page.events.sessionId),
      width: 150,
      renderCell: (params) =>
        params.value ? <code style={{ fontSize: '0.875rem' }}>{params.value.substring(0, 8)}...</code> : 'N/A',
    },
    {
      field: 'message',
      headerName: t(K.page.events.message),
      flex: 1,
      minWidth: 400,
      renderCell: (params) => {
        const msg = params.row.message || params.row.description || 'No message'
        return msg.length > 60 ? msg.substring(0, 60) + '...' : msg
      },
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 3 Interactions
  // ===================================
  return (
    <>
      {/* Live Stream Status Banner */}
      {streamMode && (
        <Alert
          severity="info"
          sx={{ mb: 2 }}
          icon={
            <Box
              sx={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                bgcolor: 'info.main',
                animation: 'pulse 2s infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 },
                },
              }}
            />
          }
        >
          {t(K.page.events.liveStreamingBanner)}
        </Alert>
      )}

      <TableShell
        loading={loading}
        rows={events}
        columns={columns}
        filterBar={
        <FilterBar
          filters={[
            {
              width: 3,
              component: (
                <TextField
                  label={t(K.common.search)}
                  placeholder={t(K.form.placeholder.search)}
                  fullWidth
                  size="small"
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
                  size="small"
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.events.allTypes)}</MenuItem>
                  <MenuItem value="system">{t(K.page.events.typeSystem)}</MenuItem>
                  <MenuItem value="model">{t(K.page.events.typeModel)}</MenuItem>
                  <MenuItem value="task">{t(K.page.events.typeTask)}</MenuItem>
                  <MenuItem value="memory">{t(K.page.events.typeMemory)}</MenuItem>
                  <MenuItem value="extension">{t(K.page.events.typeExtension)}</MenuItem>
                  <MenuItem value="api">{t(K.page.events.typeAPI)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size="small"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  displayEmpty
                >
                  <MenuItem value="all">{t(K.page.events.allStatus)}</MenuItem>
                  <MenuItem value="success">{t(K.common.success)}</MenuItem>
                  <MenuItem value="error">{t(K.common.error)}</MenuItem>
                  <MenuItem value="pending">{t(K.common.pending)}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={streamMode}
                        onChange={(e) => handleStreamToggle(e.target.checked)}
                        size="small"
                      />
                    }
                    label={t(K.page.events.liveStream)}
                    sx={{ m: 0 }}
                  />
                </Box>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t(K.common.reset),
              onClick: () => {
                setSearchQuery('')
                setTypeFilter('all')
                setStatusFilter('all')
              },
            },
            {
              key: 'apply',
              label: t(K.common.apply),
              variant: 'contained',
              onClick: () => fetchEvents(),
            },
          ]}
        />
      }
      emptyState={{
        title: t(K.page.events.noEvents),
        description: t(K.page.events.noEventsDesc),
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: events.length,
        onPageChange: () => {},
      }}
      onRowClick={handleRowClick}
      />

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedEvent?.type || t(K.page.events.eventDetails)}
        actions={
          selectedEvent ? (
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                size="small"
                startIcon={<CopyIcon />}
                onClick={() =>
                  handleCopyEventId(selectedEvent.event_id || selectedEvent.id || '')
                }
                disabled={!selectedEvent.event_id && !selectedEvent.id}
              >
                {t(K.page.events.copyId)}
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<FilterIcon />}
                onClick={() => handleFilterByType(selectedEvent.type)}
              >
                {t(K.page.events.filterByType)}
              </Button>
            </Box>
          ) : undefined
        }
      >
        {selectedEvent && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Event ID with Copy Button */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.events.eventId)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="body1" sx={{ fontFamily: 'monospace', flex: 1 }}>
                  {selectedEvent.event_id || selectedEvent.id || 'N/A'}
                </Typography>
                {(selectedEvent.event_id || selectedEvent.id) && (
                  <IconButton
                    size="small"
                    onClick={() =>
                      handleCopyEventId(selectedEvent.event_id || selectedEvent.id || '')
                    }
                    title={t(K.page.events.copyId)}
                  >
                    <CopyIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            </Box>

            {/* Type with Filter Button */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.events.type)}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1 }}>{renderEventType(selectedEvent.type)}</Box>
              </Box>
            </Box>

            {/* Timestamp */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.events.timestamp)}
              </Typography>
              <Typography variant="body1">
                {formatTimestamp(selectedEvent.timestamp || selectedEvent.created_at)}
              </Typography>
            </Box>

            {/* Task ID */}
            {selectedEvent.task_id && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.events.taskId)}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', flex: 1 }}>
                    {selectedEvent.task_id}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={() => handleCopyEventId(selectedEvent.task_id || '')}
                    title={t(K.page.events.copyId)}
                  >
                    <CopyIcon fontSize="small" />
                  </IconButton>
                </Box>
              </Box>
            )}

            {/* Session ID */}
            {selectedEvent.session_id && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.events.sessionId)}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', flex: 1 }}>
                    {selectedEvent.session_id}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={() => handleCopyEventId(selectedEvent.session_id || '')}
                    title={t(K.page.events.copyId)}
                  >
                    <CopyIcon fontSize="small" />
                  </IconButton>
                </Box>
              </Box>
            )}

            {/* Message */}
            {(selectedEvent.message || selectedEvent.description) && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.events.message)}
                </Typography>
                <Typography variant="body1">{selectedEvent.message || selectedEvent.description}</Typography>
              </Box>
            )}

            {/* Raw Event Data */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.events.rawEventData)}
              </Typography>
              <Box
                component="pre"
                sx={{
                  bgcolor: 'background.default',
                  p: 2,
                  borderRadius: 1,
                  overflow: 'auto',
                  fontSize: '0.875rem',
                  fontFamily: 'monospace',
                  maxHeight: 300,
                }}
              >
                {JSON.stringify(selectedEvent, null, 2)}
              </Box>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Clear All Confirmation Dialog */}
      <ConfirmDialog
        open={clearDialogOpen}
        onClose={() => setClearDialogOpen(false)}
        title={t(K.page.events.clearAllTitle)}
        message={t(K.page.events.clearAllMessage)}
        confirmText={t(K.page.events.clearAllConfirm)}
        cancelText={t(K.common.cancel)}
        onConfirm={handleClearAll}
        loading={clearLoading}
        color="error"
      />
    </>
  )
}
