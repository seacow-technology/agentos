/**
 * SessionsPage - 会话管理页面
 *
 * Phase 6: Real API Integration
 * - API: agentosService.listSessions(), deleteSession()
 * - States: Loading/Success/Error/Empty
 * - Interactions: Delete API, DetailDrawer, Filter Logic
 * - i18n: Full translation support
 */

import { useState, useMemo, useEffect } from 'react'
import { Box, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem, Button } from '@/ui'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import { httpClient } from '@platform/http'
import { agentosService } from '@/services'
import type { Session as ApiSession } from '@/services/agentos.service'


/**
 * Session type definition
 */
interface Session {
  id: number
  sessionId: string
  type: string
  user: string
  startedAt: string
  duration: string
  messageCount: number
  status: string
  createdAt: string
  lastActive: string
}

/**
 * Constants
 */
const SIZE_SMALL = 'small' as const
const VALUE_ALL = 'all' as const
const VALUE_CHAT = 'chat' as const
const VALUE_VOICE = 'voice' as const
const VALUE_API = 'api' as const
const VALUE_ACTIVE = 'active' as const
const VALUE_ENDED = 'ended' as const
const VARIANT_CONTAINED = 'contained' as const
const COLOR_ERROR = 'error' as const
const VARIANT_H6 = 'h6' as const
const VARIANT_CAPTION = 'caption' as const
const VARIANT_BODY1 = 'body1' as const
const COLOR_TEXT_SECONDARY = 'text.secondary' as const

/**
 * SessionsPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🔧 P1 Interactions: Delete API, DetailDrawer, Filter Logic
 */
export default function SessionsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State (P1-29: Filter Logic)
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>(VALUE_ALL)
  const [statusFilter, setStatusFilter] = useState<string>(VALUE_ALL)
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  // ===================================
  // State (P1-28: Detail Drawer)
  // ===================================
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)

  // ===================================
  // State (P1-1: Delete Confirmation)
  // ===================================
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [sessionToDelete, setSessionToDelete] = useState<Session | null>(null)
  const [deleting, setDeleting] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.sessions.title),
    subtitle: t(K.page.sessions.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => loadSessions(),
    },
  ])

  // ===================================
  // API: Load Sessions
  // ===================================
  const loadSessions = async () => {
    setLoading(true)
    try {
      // Backend returns array directly: Session[]
      const sessions = await agentosService.listSessions()
      // Map API sessions to our display format
      const mappedSessions = sessions.map((s: ApiSession, index: number) => ({
        id: index + 1,
        sessionId: s.id,
        type: s.title?.includes('voice') ? 'Voice' : s.title?.includes('api') ? 'API' : 'Chat',
        user: 'System', // API doesn't provide user info
        startedAt: s.created_at,
        duration: calculateDuration(s.created_at, s.updated_at),
        messageCount: 0, // Not provided by API
        status: 'Active', // Status not provided by backend
        createdAt: s.created_at,
        lastActive: s.updated_at || s.created_at,
      }))
      setSessions(mappedSessions)
      toast.success(t('page.sessions.refreshSuccess'))
    } catch (err: any) {
      console.error('Failed to load sessions:', err)
      const errorMessage = err.message || t('page.sessions.loadError')
      setSessions([])
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // Helper to calculate duration
  const calculateDuration = (start: string, end?: string) => {
    try {
      const startTime = new Date(start).getTime()
      const endTime = end ? new Date(end).getTime() : Date.now()
      const diff = Math.abs(endTime - startTime)
      const minutes = Math.floor(diff / 60000)
      const hours = Math.floor(minutes / 60)
      const remainingMinutes = minutes % 60
      if (hours > 0) {
        return `${hours}h ${remainingMinutes}m`
      }
      return `${minutes}m`
    } catch {
      return 'N/A'
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  // ===================================
  // P1-29: Filter Logic - Apply filters to sessions
  // ===================================
  const filteredSessions = useMemo(() => {
    return sessions.filter((session) => {
      // Search filter: match sessionId or user
      const matchesSearch =
        searchQuery === '' ||
        session.sessionId.toLowerCase().includes(searchQuery.toLowerCase()) ||
        session.user.toLowerCase().includes(searchQuery.toLowerCase())

      // Type filter
      const matchesType =
        typeFilter === VALUE_ALL ||
        session.type.toLowerCase() === typeFilter.toLowerCase()

      // Status filter
      const matchesStatus =
        statusFilter === VALUE_ALL ||
        session.status.toLowerCase() === statusFilter.toLowerCase()

      return matchesSearch && matchesType && matchesStatus
    })
  }, [sessions, searchQuery, typeFilter, statusFilter])

  // ===================================
  // P1-28: Handle row click - Open DetailDrawer
  // ===================================
  const handleRowClick = (row: Session) => {
    setSelectedSession(row)
    setDrawerOpen(true)
  }

  const handleDrawerClose = () => {
    setDrawerOpen(false)
    setSelectedSession(null)
  }

  // ===================================
  // P1-1: Delete Session - API Call
  // ===================================
  const handleDeleteClick = (session: Session) => {
    setSessionToDelete(session)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!sessionToDelete) return

    setDeleting(true)
    try {
      // Phase 6: Use real API with httpClient
      await httpClient.delete(`/api/sessions/${sessionToDelete.sessionId}`)

      // Success: show toast
      toast.success(t('page.sessions.deleteSuccess'))

      // Close drawer if the deleted session is currently open
      if (selectedSession?.id === sessionToDelete.id) {
        setDrawerOpen(false)
        setSelectedSession(null)
      }

      // Remove session from list
      setSessions((prev) => prev.filter((s) => s.id !== sessionToDelete.id))

      // Close dialog
      setDeleteDialogOpen(false)
      setSessionToDelete(null)
    } catch (error) {
      console.error('Failed to delete session:', error)
      toast.error(t('page.sessions.deleteFailed'))
    } finally {
      setDeleting(false)
    }
  }

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false)
    setSessionToDelete(null)
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: t(K.page.sessions.columnId),
      width: 80,
    },
    {
      field: 'sessionId',
      headerName: t(K.page.sessions.columnSessionId),
      width: 180,
    },
    {
      field: 'type',
      headerName: t(K.page.sessions.columnType),
      width: 100,
    },
    {
      field: 'user',
      headerName: t(K.page.sessions.columnUser),
      width: 150,
    },
    {
      field: 'startedAt',
      headerName: t(K.page.sessions.columnStartedAt),
      width: 180,
    },
    {
      field: 'duration',
      headerName: t(K.page.sessions.columnDuration),
      width: 120,
    },
    {
      field: 'messageCount',
      headerName: t(K.page.sessions.columnMessageCount),
      width: 110,
    },
    {
      field: 'status',
      headerName: t('form.field.status'),
      width: 100,
    },
  ]

  // ===================================
  // Render: TableShell Pattern (P1-29: Use filtered data)
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={filteredSessions}
        columns={columns}
      filterBar={
        <FilterBar
          filters={[
            {
              width: 6,
              component: (
                <TextField
                  label={t('common.search')}
                  placeholder={t('page.sessions.searchPlaceholder')}
                  fullWidth
                  size={SIZE_SMALL}
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
                  size={SIZE_SMALL}
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                >
                  <MenuItem value={VALUE_ALL}>{t('page.sessions.allTypes')}</MenuItem>
                  <MenuItem value={VALUE_CHAT}>{t('page.sessions.typeChat')}</MenuItem>
                  <MenuItem value={VALUE_VOICE}>{t('page.sessions.typeVoice')}</MenuItem>
                  <MenuItem value={VALUE_API}>{t('page.sessions.typeApi')}</MenuItem>
                </Select>
              ),
            },
            {
              width: 3,
              component: (
                <Select
                  fullWidth
                  size={SIZE_SMALL}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <MenuItem value={VALUE_ALL}>{t('page.sessions.allStatus')}</MenuItem>
                  <MenuItem value={VALUE_ACTIVE}>{t('page.sessions.statusActive')}</MenuItem>
                  <MenuItem value={VALUE_ENDED}>{t('page.sessions.statusEnded')}</MenuItem>
                </Select>
              ),
            },
          ]}
          actions={[
            {
              key: 'reset',
              label: t('common.reset'),
              onClick: () => {
                // P1-29: Reset all filters
                setSearchQuery('')
                setTypeFilter(VALUE_ALL)
                setStatusFilter(VALUE_ALL)
              },
            },
          ]}
        />
      }
      emptyState={{
        title: filteredSessions.length === 0 && sessions.length > 0
          ? t('page.sessions.noSessionsFiltered')
          : t('page.sessions.noSessions'),
        description: filteredSessions.length === 0 && sessions.length > 0
          ? t('page.sessions.noSessionsFilteredDesc')
          : t('page.sessions.noSessionsDesc'),
        actions: [
          {
            label: t('common.refresh'),
            onClick: () => loadSessions(),
            variant: VARIANT_CONTAINED,
          },
        ],
      }}
      pagination={{
        page: 0,
        pageSize: 25,
        total: filteredSessions.length,
        onPageChange: () => {}, // Pagination not implemented yet
      }}
      onRowClick={handleRowClick}
    />

    {/* P1-28: Session Detail Drawer */}
    <DetailDrawer
      open={drawerOpen}
      onClose={handleDrawerClose}
      title={t('page.sessions.detailTitle', { id: selectedSession?.sessionId || '' })}
      subtitle={selectedSession ? `${selectedSession.type} • ${selectedSession.user}` : ''}
      actions={
        <Button
          variant={VARIANT_CONTAINED}
          color={COLOR_ERROR}
          onClick={() => selectedSession && handleDeleteClick(selectedSession)}
        >
          {t('common.delete')}
        </Button>
      }
    >
      {selectedSession && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Basic Information */}
          <Box>
            <Typography variant={VARIANT_H6} gutterBottom>
              {t('page.sessions.basicInfo')}
            </Typography>
            <Box sx={{ display: 'grid', gap: 2 }}>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.columnSessionId')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.sessionId}</Typography>
              </Box>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.columnType')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.type}</Typography>
              </Box>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.columnUser')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.user}</Typography>
              </Box>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('form.field.status')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.status}</Typography>
              </Box>
            </Box>
          </Box>

          {/* Timing Information */}
          <Box>
            <Typography variant={VARIANT_H6} gutterBottom>
              {t('page.sessions.timing')}
            </Typography>
            <Box sx={{ display: 'grid', gap: 2 }}>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.created')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.createdAt}</Typography>
              </Box>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.lastActive')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.lastActive}</Typography>
              </Box>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.columnDuration')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.duration}</Typography>
              </Box>
            </Box>
          </Box>

          {/* Activity Information */}
          <Box>
            <Typography variant={VARIANT_H6} gutterBottom>
              {t('page.sessions.activity')}
            </Typography>
            <Box sx={{ display: 'grid', gap: 2 }}>
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                  {t('page.sessions.columnMessageCount')}
                </Typography>
                <Typography variant={VARIANT_BODY1}>{selectedSession.messageCount}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      )}
    </DetailDrawer>

    {/* P1-1: Delete Confirmation Dialog */}
    <ConfirmDialog
      open={deleteDialogOpen}
      onClose={handleDeleteCancel}
      title={t('page.sessions.deleteTitle')}
      message={t('page.sessions.deleteMessage', {
        id: sessionToDelete?.sessionId || '',
        user: sessionToDelete?.user || '',
      })}
      confirmText={t('common.delete')}
      onConfirm={handleDeleteConfirm}
      loading={deleting}
    />
  </>
  )
}
