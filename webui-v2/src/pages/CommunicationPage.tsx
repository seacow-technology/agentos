/**
 * CommunicationPage - CommunicationOS Control Panel
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.communication.xxx)
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Pattern Components: StatusCard + TableShell + AppTable
 * - ✅ Phase 6: 真实API接入
 */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, StatusCard, type GridColDef, type GridRowsProp } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { RefreshIcon, DownloadIcon, PowerOffIcon, VisibilityIcon, PowerIcon } from '@/ui/icons'
import {
  Box,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  CircularProgress,
} from '@/ui'
import { communicationosService } from '@/services/communicationos.service'

// ===================================
// Constants
// ===================================
const VARIANT_H6 = 'h6'
const VARIANT_BODY2 = 'body2'
const COLOR_TEXT_SECONDARY = 'text.secondary'
const SIZE_SMALL = 'small'
const MODE_OFF = 'OFF'
const MODE_READONLY = 'READONLY'
const MODE_ON = 'ON'

export default function CommunicationPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(false)
  const [auditsLoading, setAuditsLoading] = useState(false)
  const [networkMode, setNetworkMode] = useState<'OFF' | 'READONLY' | 'ON'>('READONLY')
  const [activeConnections, setActiveConnections] = useState(0)
  const [auditLogs, setAuditLogs] = useState<GridRowsProp>([])
  const [modeChanging, setModeChanging] = useState(false)
  const [serviceStatus, setServiceStatus] = useState<any>(null)
  const [policyConfig, setPolicyConfig] = useState<any>(null)

  // ===================================
  // API Handlers
  // ===================================
  const loadNetworkMode = useCallback(async () => {
    try {
      const response = await communicationosService.getNetworkMode()
      if (response?.current_state?.mode) {
        const mode = response.current_state.mode.toUpperCase() as 'OFF' | 'READONLY' | 'ON'
        setNetworkMode(mode)
      }
      // Also load status for active connections count
      const statusResponse = await communicationosService.getCommunicationStatus()
      // Count active connections from statistics
      if (statusResponse?.statistics?.total_requests !== undefined) {
        setActiveConnections(statusResponse.statistics.total_requests || 0)
      }
    } catch (error) {
      console.error('Failed to load network mode:', error)
      // Don't show toast for silent failures
    }
  }, [])

  const loadAuditLogs = useCallback(async () => {
    setAuditsLoading(true)
    try {
      const response = await communicationosService.listCommunicationAudits({ limit: 50 })
      const logs = (response?.audits || []).map(audit => ({
        id: audit.id,
        timestamp: audit.created_at,
        requestId: audit.request_id,
        connector: audit.connector_type,
        operation: audit.operation,
        status: audit.status,
        riskLevel: audit.risk_level || 'N/A',
      }))
      setAuditLogs(logs)
    } catch (error) {
      console.error('Failed to load audit logs:', error)
      toast.error(t('page.communication.loadAuditsFailed') || 'Failed to load audit logs')
    } finally {
      setAuditsLoading(false)
    }
  }, [t])

  const loadServiceStatus = useCallback(async () => {
    try {
      const response = await communicationosService.getCommunicationStatus()
      setServiceStatus(response)
    } catch (error) {
      console.error('Failed to load service status:', error)
    }
  }, [])

  const loadPolicyConfig = useCallback(async () => {
    try {
      const response = await communicationosService.getCommunicationPolicy()
      setPolicyConfig(response)
    } catch (error) {
      console.error('Failed to load policy config:', error)
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    setLoading(true)
    try {
      await Promise.all([
        loadNetworkMode(),
        loadAuditLogs(),
        loadServiceStatus(),
        loadPolicyConfig(),
      ])
    } catch (error) {
      console.error('Failed to refresh:', error)
      toast.error(t('page.communication.refreshFailed') || 'Failed to refresh data')
    } finally {
      setLoading(false)
    }
  }, [loadNetworkMode, loadAuditLogs, loadServiceStatus, loadPolicyConfig, t])

  const handleExport = useCallback(() => {
    try {
      const csvContent = [
        ['Timestamp', 'Request ID', 'Connector', 'Operation', 'Status', 'Risk Level'].join(','),
        ...auditLogs.map(log =>
          [
            log.timestamp,
            log.requestId,
            log.connector,
            log.operation,
            log.status,
            log.riskLevel,
          ].join(',')
        ),
      ].join('\n')

      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `communication-audit-${new Date().toISOString()}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to export:', error)
      toast.error(t('page.communication.exportFailed') || 'Failed to export audit log')
    }
  }, [auditLogs, t])

  const handleModeChange = useCallback(
    async (newMode: 'OFF' | 'READONLY' | 'ON') => {
      setModeChanging(true)
      try {
        const response = await communicationosService.setNetworkMode({
          mode: newMode.toLowerCase(),
          reason: 'Manual change from WebUI',
          updated_by: 'webui_user',
        })
        if (response?.new_mode) {
          setNetworkMode(response.new_mode.toUpperCase() as 'OFF' | 'READONLY' | 'ON')
          toast.success(t('page.communication.modeChangeSuccess') || `Network mode changed to ${newMode}`)
        }
      } catch (error) {
        console.error('Failed to change mode:', error)
        toast.error(t('page.communication.modeChangeFailed') || 'Failed to change network mode')
      } finally {
        setModeChanging(false)
      }
    },
    [t]
  )

  // ===================================
  // Effects
  // ===================================
  useEffect(() => {
    loadNetworkMode()
    loadAuditLogs()
    loadServiceStatus()
    loadPolicyConfig()
  }, [loadNetworkMode, loadAuditLogs, loadServiceStatus, loadPolicyConfig])

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.communication.title),
    subtitle: t(K.page.communication.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      icon: <RefreshIcon />,
      variant: 'outlined',
      onClick: handleRefresh,
      disabled: loading,
    },
    {
      key: 'export',
      label: t('common.download'),
      icon: <DownloadIcon />,
      variant: 'outlined',
      onClick: handleExport,
      disabled: auditLogs.length === 0,
    },
  ])

  // ===================================
  // 翻译映射函数
  // ===================================
  const getOperationText = (op: string) => {
    const map: Record<string, string> = {
      send_message: t(K.page.communication.opSendMessage),
      get_updates: t(K.page.communication.opGetUpdates),
      post_message: t(K.page.communication.opPostMessage),
      send_embed: t(K.page.communication.opSendEmbed),
    }
    return map[op] || op
  }

  const getStatusText = (status: string) => {
    const map: Record<string, string> = {
      success: t(K.page.communication.statusSuccess),
      failed: t(K.page.communication.statusFailed),
      blocked: t(K.page.communication.statusBlocked),
    }
    return map[status] || status
  }

  const getRiskLevelText = (risk: string) => {
    const map: Record<string, string> = {
      low: t(K.page.communication.riskLow),
      medium: t(K.page.communication.riskMedium),
      high: t(K.page.communication.riskHigh),
    }
    return map[risk] || risk
  }

  // ===================================
  // Data Transformation
  // ===================================
  const translatedAuditLogs: GridRowsProp = auditLogs.map((log) => ({
    ...log,
    operation: getOperationText(log.operation),
    status: getStatusText(log.status),
    riskLevel: getRiskLevelText(log.riskLevel),
  }))

  const columns: GridColDef[] = [
    { field: 'timestamp', headerName: t(K.page.communication.columnTimestamp), flex: 1, minWidth: 180 },
    { field: 'requestId', headerName: t(K.page.communication.columnRequestId), flex: 1, minWidth: 120 },
    { field: 'connector', headerName: t(K.page.communication.columnConnector), flex: 1, minWidth: 120 },
    { field: 'operation', headerName: t(K.page.communication.columnOperation), flex: 1, minWidth: 150 },
    { field: 'status', headerName: t(K.page.communication.columnStatus), flex: 0.7, minWidth: 100 },
    { field: 'riskLevel', headerName: t(K.page.communication.columnRiskLevel), flex: 0.7, minWidth: 100 },
  ]

  // ===================================
  // Render
  // ===================================
  if (loading && auditLogs.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '400px',
        }}
      >
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Network Status Section */}
      <Box>
        <StatusCard
          title={t(K.page.communication.networkStatus)}
          status={networkMode}
          statusLabel={t(K.page.communication.networkMode)}
          meta={[
            { key: 'mode', label: t(K.page.communication.currentMode), value: networkMode },
            {
              key: 'connections',
              label: t(K.page.communication.activeConnections),
              value: String(activeConnections),
            },
          ]}
        />
        <Box sx={{ mt: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} sx={{ mb: 1 }}>
            {t(K.page.communication.communicationMode)}
          </Typography>
          <ToggleButtonGroup
            value={networkMode}
            exclusive
            onChange={(_event: React.MouseEvent<HTMLElement>, newMode: string | null) => {
              if (newMode) {
                handleModeChange(newMode as 'OFF' | 'READONLY' | 'ON')
              }
            }}
            size={SIZE_SMALL}
            disabled={modeChanging}
          >
            <ToggleButton value={MODE_OFF}>
              <PowerOffIcon sx={{ mr: 0.5, fontSize: 18 }} />
              {t(K.page.communication.modeOff)}
            </ToggleButton>
            <ToggleButton value={MODE_READONLY}>
              <VisibilityIcon sx={{ mr: 0.5, fontSize: 18 }} />
              {t(K.page.communication.modeReadonly)}
            </ToggleButton>
            <ToggleButton value={MODE_ON}>
              <PowerIcon sx={{ mr: 0.5, fontSize: 18 }} />
              {t(K.page.communication.modeOn)}
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* Service Status Section */}
      {serviceStatus && (
        <Box>
          <StatusCard
            title={t(K.page.communication.serviceStatus)}
            status={serviceStatus.status || 'unknown'}
            statusLabel={t(K.page.communication.status)}
            meta={[
              { key: 'network_mode', label: t(K.page.communication.networkMode), value: serviceStatus.network_mode || 'N/A' },
              { key: 'timestamp', label: t(K.page.communication.lastUpdated), value: serviceStatus.timestamp ? new Date(serviceStatus.timestamp).toLocaleString() : 'N/A' },
            ]}
          />
          {serviceStatus.connectors && Object.keys(serviceStatus.connectors).length > 0 && (
            <Box sx={{ mt: 2, p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} sx={{ mb: 1 }}>
                {t(K.page.communication.registeredConnectors)}
              </Typography>
              {Object.entries(serviceStatus.connectors).map(([type, info]: [string, any]) => (
                <Box key={type} sx={{ mb: 1, p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
                  <Typography variant="body2" fontWeight="bold">{type}</Typography>
                  <Typography variant="caption" color={COLOR_TEXT_SECONDARY}>
                    {info.enabled ? t('common.enabled') : t('common.disabled')} • {t('common.rateLimit')}: {info.rate_limit}/min
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </Box>
      )}

      {/* Policy Configuration Section */}
      {policyConfig && Object.keys(policyConfig).length > 0 && (
        <Box>
          <Typography variant={VARIANT_H6} sx={{ mb: 1 }}>
            {t(K.page.communication.policyConfiguration)}
          </Typography>
          <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} sx={{ mb: 2 }}>
            {t(K.page.communication.policyDescription)}
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 2 }}>
            {Object.entries(policyConfig).map(([type, policy]: [string, any]) => {
              // Defensive check: ensure policy is an object with expected properties
              if (!policy || typeof policy !== 'object') return null

              return (
                <Box key={type} sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="subtitle2">{policy.name || type}</Typography>
                    <Typography variant="caption" color={policy.enabled ? 'success.main' : 'text.disabled'}>
                      {policy.enabled ? t('common.enabled') : t('common.disabled')}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color={COLOR_TEXT_SECONDARY}>
                    {t('common.rateLimit')}: {policy.rate_limit_per_minute}/min • {t('common.timeout')}: {policy.timeout_seconds}s
                  </Typography>
                </Box>
              )
            })}
          </Box>
        </Box>
      )}

      {/* Recent Audit Logs Section */}
      <Box>
        <Typography variant={VARIANT_H6} sx={{ mb: 1 }}>
          {t(K.page.communication.recentAuditLogs)}
        </Typography>
        <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY} sx={{ mb: 2 }}>
          {t(K.page.communication.auditLogDescription)}
        </Typography>
        <TableShell
          loading={auditsLoading}
          rows={translatedAuditLogs}
          columns={columns}
        />
      </Box>
    </Box>
  )
}
