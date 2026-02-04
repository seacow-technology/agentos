/**
 * RemoteControlPage - Remote Control Management View
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 6: 真实API集成（listRemoteConnections, executeRemoteCommand, terminateRemoteConnection）
 * - ✅ State Handling: Loading/Success/Error/Empty states
 *
 * Features:
 * - Remote connection list with status filtering
 * - Connection details view with command history
 * - Execute remote commands via dialog
 * - Terminate connections with confirmation
 */

import { useState, useEffect } from 'react'
// eslint-disable-next-line no-restricted-imports -- Box and Typography are allowed per G3
import { Box, Typography } from '@mui/material'
import { TextField, Select, MenuItem, Button, Chip, Dialog, DialogTitle, DialogContent, DialogActions } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { TableShell } from '@/ui'
import { DetailDrawer, ConfirmDialog } from '@/ui/interaction'
import { RefreshIcon, CodeIcon } from '@/ui/icons'
import type { GridColDef } from '@/ui'
import {
  networkosService,
  type RemoteConnectionDetail,
} from '@/services/networkos.service'

// ===================================
// Types
// ===================================

interface RemoteConnectionRow {
  id: string
  conn_id: string
  remote_node: string
  status: 'active' | 'idle' | 'terminated'
  established_at: string
  last_activity_at: string
  command_count: number
}

/**
 * RemoteControlPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + DetailDrawer + Dialogs）
 * 🔌 API:
 *   - GET /api/remote/connections → networkosService.listRemoteConnections()
 *   - GET /api/remote/connections/:id → networkosService.getRemoteConnection()
 *   - POST /api/remote/connections/:id/execute → networkosService.executeRemoteCommand()
 *   - DELETE /api/remote/connections/:id → networkosService.terminateRemoteConnection()
 */
export default function RemoteControlPage() {
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [connections, setConnections] = useState<RemoteConnectionRow[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)

  // ===================================
  // State - Filters
  // ===================================
  const [statusFilter, setStatusFilter] = useState<'active' | 'idle' | 'terminated' | 'all'>('all')

  // ===================================
  // State - Detail Drawer
  // ===================================
  const [selectedConnId, setSelectedConnId] = useState<string | null>(null)
  const [connectionDetail, setConnectionDetail] = useState<RemoteConnectionDetail | null>(null)

  // ===================================
  // State - Execute Command Dialog
  // ===================================
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false)
  const [executeConnId, setExecuteConnId] = useState<string | null>(null)
  const [commandInput, setCommandInput] = useState('')
  const [executing, setExecuting] = useState(false)

  // ===================================
  // State - Terminate Confirmation
  // ===================================
  const [terminateDialogOpen, setTerminateDialogOpen] = useState(false)
  const [terminateConnId, setTerminateConnId] = useState<string | null>(null)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.remoteControl.title'),
    subtitle: t('page.remoteControl.subtitle'),
  })

  // ===================================
  // Data Fetching
  // ===================================
  const fetchConnections = async () => {
    try {
      setLoading(true)
      const response = await networkosService.listRemoteConnections({
        status: statusFilter === 'all' ? undefined : statusFilter,
        page,
        limit: pageSize,
      })

      const rows: RemoteConnectionRow[] = response.connections.map((conn) => ({
        id: conn.conn_id,
        conn_id: conn.conn_id,
        remote_node: conn.remote_node,
        status: conn.status,
        established_at: conn.established_at,
        last_activity_at: conn.last_activity_at,
        command_count: conn.command_count,
      }))

      setConnections(rows)
      setTotal(response.total)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('page.remoteControl.loadFailed')
      toast.error(errorMessage)
      setConnections([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  const fetchConnectionDetail = async (connId: string) => {
    try {
      const response = await networkosService.getRemoteConnection(connId)
      setConnectionDetail(response.connection)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('page.remoteControl.loadFailed')
      toast.error(errorMessage)
      setSelectedConnId(null)
    }
  }

  // Initial load
  useEffect(() => {
    fetchConnections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, page, pageSize])

  // ===================================
  // Event Handlers
  // ===================================
  const handleViewDetails = (connId: string) => {
    setSelectedConnId(connId)
    fetchConnectionDetail(connId)
  }

  const handleCloseDetail = () => {
    setSelectedConnId(null)
    setConnectionDetail(null)
  }

  const handleOpenExecuteDialog = (connId: string) => {
    setExecuteConnId(connId)
    setCommandInput('')
    setExecuteDialogOpen(true)
  }

  const handleCloseExecuteDialog = () => {
    setExecuteDialogOpen(false)
    setExecuteConnId(null)
    setCommandInput('')
  }

  const handleExecuteCommand = async () => {
    if (!executeConnId || !commandInput.trim()) {
      toast.error(t('page.remoteControl.commandPlaceholder'))
      return
    }

    try {
      setExecuting(true)
      const response = await networkosService.executeRemoteCommand(executeConnId, {
        command: commandInput.trim(),
      })

      if (response.status === 'success') {
        toast.success(t('page.remoteControl.executeSuccess'))
      } else {
        const errorMsg = response.error || t('page.remoteControl.executeFailed')
        toast.error(`${t('page.remoteControl.executeFailed')}: ${errorMsg}`)
      }

      handleCloseExecuteDialog()
      fetchConnections()

      // Refresh detail if viewing the same connection
      if (selectedConnId === executeConnId) {
        fetchConnectionDetail(executeConnId)
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('page.remoteControl.executeFailed')
      toast.error(errorMessage)
    } finally {
      setExecuting(false)
    }
  }

  const handleOpenTerminateDialog = (connId: string) => {
    setTerminateConnId(connId)
    setTerminateDialogOpen(true)
  }

  const handleCloseTerminateDialog = () => {
    setTerminateDialogOpen(false)
    setTerminateConnId(null)
  }

  const handleTerminateConnection = async () => {
    if (!terminateConnId) return

    try {
      await networkosService.terminateRemoteConnection(terminateConnId)
      toast.success(t('page.remoteControl.terminateSuccess'))
      handleCloseTerminateDialog()

      // Close detail if viewing the terminated connection
      if (selectedConnId === terminateConnId) {
        handleCloseDetail()
      }

      fetchConnections()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t('page.remoteControl.terminateFailed')
      toast.error(errorMessage)
    }
  }

  // ===================================
  // Page Actions
  // ===================================
  usePageActions([
    {
      key: 'refresh',
      label: t('page.remoteControl.refresh'),
      variant: 'outlined',
      onClick: fetchConnections,
      icon: <RefreshIcon />,
    },
  ])

  // ===================================
  // Helper Functions
  // ===================================
  const getStatusColor = (status: string): 'success' | 'warning' | 'error' | 'default' => {
    const colorMap: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
      active: 'success',
      idle: 'warning',
      terminated: 'error',
    }
    return colorMap[status] || 'default'
  }

  const getStatusLabel = (status: string): string => {
    const labelMap: Record<string, string> = {
      active: t('page.remoteControl.statusActive'),
      idle: t('page.remoteControl.statusIdle'),
      terminated: t('page.remoteControl.statusTerminated'),
    }
    return labelMap[status] || status
  }

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleString()
  }

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'conn_id',
      headerName: t('page.remoteControl.connectionId'),
      flex: 1,
      minWidth: 150,
    },
    {
      field: 'remote_node',
      headerName: t('page.remoteControl.remoteNode'),
      flex: 1,
      minWidth: 150,
    },
    {
      field: 'status',
      headerName: t('page.remoteControl.status'),
      width: 120,
      renderCell: (params) => (
        <Chip
          label={getStatusLabel(params.value as string)}
          color={getStatusColor(params.value as string)}
          size={'small' as const}
        />
      ),
    },
    {
      field: 'established_at',
      headerName: t('page.remoteControl.establishedAt'),
      flex: 1,
      minWidth: 180,
      renderCell: (params) => formatTimestamp(params.value as string),
    },
    {
      field: 'last_activity_at',
      headerName: t('page.remoteControl.lastActivity'),
      flex: 1,
      minWidth: 180,
      renderCell: (params) => formatTimestamp(params.value as string),
    },
    {
      field: 'command_count',
      headerName: t('page.remoteControl.commandCount'),
      width: 120,
      type: 'number',
    },
    {
      field: 'actions',
      headerName: '',
      width: 300,
      sortable: false,
      renderCell: (params) => {
        const row = params.row as RemoteConnectionRow
        return (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              size={'small' as const}
              variant={'text' as const}
              onClick={() => handleViewDetails(row.conn_id)}
            >
              {t('page.remoteControl.viewDetails')}
            </Button>
            <Button
              size={'small' as const}
              variant={'text' as const}
              onClick={() => handleOpenExecuteDialog(row.conn_id)}
              disabled={row.status === 'terminated'}
            >
              {t('page.remoteControl.executeCommand')}
            </Button>
            <Button
              size={'small' as const}
              variant={'text' as const}
              color={'error' as const}
              onClick={() => handleOpenTerminateDialog(row.conn_id)}
              disabled={row.status === 'terminated'}
            >
              {t('page.remoteControl.terminateConnection')}
            </Button>
          </Box>
        )
      },
    },
  ]

  // ===================================
  // Render: Main Table
  // ===================================
  return (
    <Box>
      <TableShell
        loading={loading}
        rows={connections}
        columns={columns}
        filterBar={
          <Box sx={{ mb: 2, display: 'flex', gap: 2 }}>
            <Select
              label={t('page.remoteControl.status')}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'active' | 'idle' | 'terminated' | 'all')}
              size={'small' as const}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value={'all' as const}>{t('common.all')}</MenuItem>
              <MenuItem value={'active' as const}>{t('page.remoteControl.statusActive')}</MenuItem>
              <MenuItem value={'idle' as const}>{t('page.remoteControl.statusIdle')}</MenuItem>
              <MenuItem value={'terminated' as const}>{t('page.remoteControl.statusTerminated')}</MenuItem>
            </Select>
          </Box>
        }
        emptyState={{
          title: t('page.remoteControl.emptyTitle'),
          description: t('page.remoteControl.emptyDescription'),
        }}
        pagination={{
          page,
          pageSize,
          total,
          onPageChange: setPage,
          onPageSizeChange: setPageSize,
        }}
        onRowClick={(row) => handleViewDetails((row as RemoteConnectionRow).conn_id)}
      />

      {/* Detail Drawer */}
      <DetailDrawer
        open={!!selectedConnId}
        onClose={handleCloseDetail}
        title={t('page.remoteControl.viewDetails')}
      >
        {connectionDetail && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Connection Info */}
            <Box>
              <Typography variant={'h6' as const} gutterBottom>
                {t('page.remoteControl.connectionId')}{': '}{connectionDetail.conn_id}
              </Typography>
              <Typography variant={'body2' as const} color={'text.secondary' as const}>
                {t('page.remoteControl.remoteNode')}{': '}{connectionDetail.remote_node}
              </Typography>
              <Box sx={{ mt: 1 }}>
                <Chip
                  label={getStatusLabel(connectionDetail.status)}
                  color={getStatusColor(connectionDetail.status)}
                  size={'small' as const}
                />
              </Box>
            </Box>

            {/* Command History */}
            <Box>
              <Typography variant={'h6' as const} gutterBottom>
                {t('page.remoteControl.commandHistory')} {'('}{connectionDetail.command_history.length}{')'}
              </Typography>
              {connectionDetail.command_history.length === 0 ? (
                <Typography variant={'body2' as const} color={'text.secondary' as const}>
                  {t('page.remoteControl.noCommandsYet')}
                </Typography>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {connectionDetail.command_history.map((cmd) => (
                    <Box
                      key={cmd.command_id}
                      sx={{
                        p: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 1,
                        bgcolor: 'background.paper',
                      }}
                    >
                      <Typography variant={'body2' as const} sx={{ fontFamily: 'monospace', mb: 1 }}>
                        {'$ '}{cmd.command}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                        <Chip
                          label={cmd.status}
                          color={cmd.status === 'success' ? 'success' : 'error'}
                          size={'small' as const}
                        />
                        <Typography variant={'caption' as const} color={'text.secondary' as const}>
                          {formatTimestamp(cmd.executed_at)}
                        </Typography>
                      </Box>
                      {cmd.result && (
                        <Typography variant={'body2' as const} sx={{ fontFamily: 'monospace', color: 'success.main' }}>
                          {cmd.result}
                        </Typography>
                      )}
                      {cmd.error && (
                        <Typography variant={'body2' as const} sx={{ fontFamily: 'monospace', color: 'error.main' }}>
                          {t('page.remoteControl.errorLabel')}{': '}{cmd.error}
                        </Typography>
                      )}
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Execute Command Dialog */}
      <Dialog
        open={executeDialogOpen}
        onClose={handleCloseExecuteDialog}
        maxWidth={'sm' as const}
        fullWidth
      >
        <DialogTitle>{t('page.remoteControl.commandDialogTitle')}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            multiline
            rows={4}
            label={t('page.remoteControl.commandPlaceholder')}
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseExecuteDialog} variant={'text' as const}>
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleExecuteCommand}
            variant={'contained' as const}
            disabled={executing || !commandInput.trim()}
            startIcon={<CodeIcon />}
          >
            {t('page.remoteControl.execute')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Terminate Confirmation Dialog */}
      <ConfirmDialog
        open={terminateDialogOpen}
        onClose={handleCloseTerminateDialog}
        onConfirm={handleTerminateConnection}
        title={t('page.remoteControl.terminateConfirmTitle')}
        message={t('page.remoteControl.terminateConfirmMessage')}
        confirmText={t('page.remoteControl.terminateConnection')}
        color={'error' as const}
      />
    </Box>
  )
}
