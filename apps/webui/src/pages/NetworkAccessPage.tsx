import { useCallback, useEffect, useMemo, useState } from 'react'
import { Box, Button, Divider, Grid, MenuItem, TextField, Typography } from '@mui/material'
import { usePageHeader } from '@/ui/layout'
import { CardCollectionWrap, ItemCard, type ItemCardAction, type ItemCardMeta } from '@/ui'
import { DialogForm } from '@/ui/interaction'
import { K, useTextTranslation } from '@/ui/text'
import { HelpOutlineIcon } from '@/ui/icons'
import { httpClient } from '@platform/http'
import { getToken } from '@/platform/auth/adminToken'
import { useSnackbar } from 'notistack'

type CapabilityRequest = {
  id: string
  capability: string
  params: Record<string, any>
  decision: string
  status: string
  updated_at: number
}

type ResolvedItem = { key: string; value: any; source: string }

type DaemonStatus = {
  state: string
  installed: boolean
  service_installed: boolean
  autostart_enabled: boolean
  credentials_present: boolean
  cloudflared_path?: string | null
  cloudflared_version?: string | null
  pid?: number | null
  last_error?: string | null
  logs_tail?: string | null
  platform?: string | null
  service_type?: string | null
  tunnel_name?: string | null
}

type TunnelCandidate = {
  id?: string | null
  name: string
  created_at?: string | null
  credential_file_exists?: boolean
}

function pickLatest(requests: CapabilityRequest[]): CapabilityRequest | null {
  if (!Array.isArray(requests) || requests.length === 0) return null
  return [...requests].sort((a, b) => Number(b.updated_at || 0) - Number(a.updated_at || 0))[0]
}

function isCloudflareAccountId(value: string): boolean {
  return /^[a-f0-9]{32}$/i.test(String(value || '').trim())
}

export default function NetworkAccessPage() {
  const { t } = useTextTranslation()
  const { enqueueSnackbar } = useSnackbar()
  usePageHeader({
    title: t(K.nav.networkAccess),
    subtitle: t(K.page.networkAccess.subtitle),
  })

  const [loading, setLoading] = useState(false)
  const [requests, setRequests] = useState<CapabilityRequest[]>([])
  const [enableDialogOpen, setEnableDialogOpen] = useState(false)
  const latest = useMemo(() => pickLatest(requests), [requests])

  const [cfg, setCfg] = useState<Record<string, ResolvedItem>>({})
  const [hostname, setHostname] = useState('')
  const [accountId, setAccountId] = useState('')
  const [enforceAccess, setEnforceAccess] = useState('true')
  const [healthPath, setHealthPath] = useState('/api/health')
  const [tunnelName, setTunnelName] = useState('octopusos')
  const [error, setError] = useState('')
  const [daemon, setDaemon] = useState<DaemonStatus | null>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [approvingDaemon, setApprovingDaemon] = useState(false)
  const [installingCli, setInstallingCli] = useState(false)
  const [fetchingMcp, setFetchingMcp] = useState(false)
  const [creatingTunnel, setCreatingTunnel] = useState(false)
  const [refreshingLogs, setRefreshingLogs] = useState(false)
  const [clearingLogs, setClearingLogs] = useState(false)
  const [createTunnelName, setCreateTunnelName] = useState('')
  const [tunnelCandidates, setTunnelCandidates] = useState<TunnelCandidate[]>([])
  const [mcpHostnameDialogOpen, setMcpHostnameDialogOpen] = useState(false)
  const [mcpHostnameOptions, setMcpHostnameOptions] = useState<string[]>([])
  const [mcpHostnameSelected, setMcpHostnameSelected] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await httpClient.get('/api/network/capabilities/status')
      const items = Array.isArray(resp.data?.requests) ? resp.data.requests : []
      setRequests(items)
      const cfgResp = await httpClient.get('/api/network/config')
      const items2 = (cfgResp.data?.items || {}) as Record<string, ResolvedItem>
      setCfg(items2)
      setHostname(String(items2['network.cloudflare.hostname']?.value || ''))
      setAccountId(String(items2['network.cloudflare.account_id']?.value || ''))
      setHealthPath(String(items2['network.cloudflare.health_path']?.value || '/api/health'))
      setEnforceAccess(String(items2['network.cloudflare.enforce_access']?.value ?? true))
      setTunnelName(String(items2['network.cloudflare.tunnel_name']?.value || 'octopusos'))

      // Daemon status is read-only; logs tail is only returned in debug mode (admin-gated).
      const token = getToken()
      const dResp = await httpClient.get('/api/network/cloudflare/daemon/status', {
        params: token ? { debug: 1 } : undefined,
        headers: token ? { 'X-Admin-Token': token } : undefined,
      })
      setDaemon((dResp.data?.status || null) as DaemonStatus | null)
      if (token) {
        try {
          const tResp = await httpClient.get('/api/network/cloudflare/tunnels', {
            headers: { 'X-Admin-Token': token },
          })
          const items = Array.isArray(tResp.data?.items) ? tResp.data.items : []
          setTunnelCandidates(
            items
              .map((it: any) => ({
                id: String(it?.id || '') || null,
                name: String(it?.name || '').trim(),
                created_at: String(it?.created_at || '') || null,
                credential_file_exists: Boolean(it?.credential_file_exists),
              }))
              .filter((it: TunnelCandidate) => Boolean(it.name))
          )
        } catch {
          setTunnelCandidates([])
        }
      } else {
        setTunnelCandidates([])
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const requestEnable = async () => {
    const token = getToken()
    if (!token) throw new Error('Admin token required')
    await httpClient.post(
      '/api/network/capabilities/request',
      {
        capability: 'network.tunnel.enable',
        params: {
          scope: '/personal/',
          duration: '2h',
          // execution params (minimal)
          tunnel_name: tunnelName.trim() || 'octopusos',
          local_target: 'http://127.0.0.1:8080',
          tunnel_token_ref: 'secret://networkos/cloudflare/tunnel_token',
          access_client_id_ref: 'secret://networkos/cloudflare/access_client_id',
          access_client_secret_ref: 'secret://networkos/cloudflare/access_client_secret',
        },
      },
      { headers: { 'X-Admin-Token': token } }
    )
    setEnableDialogOpen(false)
    await refresh()
  }

  const saveSettings = async () => {
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      return
    }
    setError('')
    await httpClient.post(
      '/api/network/config',
      {
        items: {
          'network.cloudflare.hostname': hostname.trim(),
          'network.cloudflare.account_id': accountId.trim(),
          'network.cloudflare.enforce_access': String(enforceAccess).trim(),
          'network.cloudflare.health_path': healthPath.trim() || '/api/health',
          'network.cloudflare.tunnel_name': tunnelName.trim() || 'octopusos',
        },
      },
      { headers: { 'X-Admin-Token': token } }
    )
    await refresh()
  }

  const provisionAccess = async () => {
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      return
    }
    setError('')
    await httpClient.post(
      '/api/network/cloudflare/access/provision',
      { params: { scope: '/personal/', hostname: hostname.trim(), account_id: accountId.trim(), probe_path: healthPath.trim() || '/api/health' } },
      { headers: { 'X-Admin-Token': token } }
    )
    await refresh()
  }

  const revokeAccess = async () => {
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      return
    }
    setError('')
    await httpClient.post(
      '/api/network/cloudflare/access/revoke',
      { params: { scope: '/personal/', hostname: hostname.trim(), account_id: accountId.trim() } },
      { headers: { 'X-Admin-Token': token } }
    )
    await refresh()
  }

  const approve = async () => {
    if (!latest?.id) return
    const token = getToken()
    if (!token) throw new Error('Admin token required')
    await httpClient.post(`/api/network/capabilities/${latest.id}/approve`, {}, { headers: { 'X-Admin-Token': token } })
    await refresh()
  }

  const approveDaemon = async (requestId: string) => {
    if (approvingDaemon) return
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    setApprovingDaemon(true)
    setError('')
    enqueueSnackbar(t(K.page.networkAccess.daemonApproveInProgress), { variant: 'info' })
    try {
      await httpClient.post(`/api/network/capabilities/${requestId}/approve`, {}, { headers: { 'X-Admin-Token': token } })
      await refresh()
    } catch (e: any) {
      const detail = String(e?.response?.data?.detail || e?.message || 'approve_failed')
      if (detail === 'not_approvable') {
        enqueueSnackbar(t(K.page.networkAccess.daemonApproveStateChanged), { variant: 'warning' })
        await refresh()
      } else {
        setError(t(K.page.networkAccess.daemonRequestFailed, { message: detail }))
        enqueueSnackbar(t(K.page.networkAccess.daemonRequestFailed, { message: detail }), { variant: 'error' })
      }
    } finally {
      setApprovingDaemon(false)
    }
  }

  const revoke = async () => {
    if (!latest?.id) return
    const token = getToken()
    if (!token) throw new Error('Admin token required')
    await httpClient.post(`/api/network/capabilities/${latest.id}/revoke`, {}, { headers: { 'X-Admin-Token': token } })
    await refresh()
  }

  const daemonAction = async (path: string) => {
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    setError('')
    try {
      const resp = await httpClient.post(path, { params: {} }, { headers: { 'X-Admin-Token': token } })
      const request = resp?.data?.request
      if (request?.id) {
        console.info('[NetworkAccess] daemon request created', {
          path,
          request_id: request.id,
          capability: request.capability,
          status: request.status,
          decision: request.decision,
        })
        enqueueSnackbar(
          t(K.page.networkAccess.daemonRequestQueued, {
            capability: String(request.capability || '-'),
            id: String(request.id || '-'),
            status: String(request.status || '-'),
          }),
          { variant: 'info' }
        )
        if (String(request.decision || '') === 'explain_confirm' && String(request.status || '') === 'pending') {
          enqueueSnackbar(t(K.page.networkAccess.daemonRequestNeedsApproval), { variant: 'warning' })
        }
      } else {
        console.info('[NetworkAccess] daemon action response', { path, data: resp?.data })
      }
      await refresh()
    } catch (e: any) {
      const message = String(e?.response?.data?.detail || e?.message || 'unknown_error')
      console.error('[NetworkAccess] daemon action failed', { path, message, error: e })
      setError(t(K.page.networkAccess.daemonRequestFailed, { message }))
      enqueueSnackbar(t(K.page.networkAccess.daemonRequestFailed, { message }), { variant: 'error' })
    }
  }

  const installCli = async () => {
    if (installingCli) return
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    setInstallingCli(true)
    setError('')
    try {
      await httpClient.post('/api/network/cloudflare/cli/install', { params: {} }, { headers: { 'X-Admin-Token': token } })
      enqueueSnackbar(t(K.page.networkAccess.setupCliInstallSuccess), { variant: 'success' })
      await refresh()
    } catch (e: any) {
      const message = String(e?.response?.data?.detail || e?.message || 'cli_install_failed')
      setError(t(K.page.networkAccess.setupCliInstallFailed, { message }))
      enqueueSnackbar(t(K.page.networkAccess.setupCliInstallFailed, { message }), { variant: 'error' })
    } finally {
      setInstallingCli(false)
    }
  }

  const fetchFromMcp = async () => {
    if (fetchingMcp) return
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    setFetchingMcp(true)
    setError('')
    try {
      const accountQuery = accountId.trim() ? { account_id: accountId.trim() } : undefined
      const resp = await httpClient.get('/api/network/cloudflare/mcp/discover', {
        params: accountQuery,
        headers: { 'X-Admin-Token': token },
      })
      const result = resp?.data?.result || {}
      const nextAccount = String(result?.account_id || '').trim()
      const hostnames = (Array.isArray(result?.hostnames) ? result.hostnames : [])
        .map((item: any) => String(item || '').trim())
        .filter(Boolean)
      let applied = false
      if (isCloudflareAccountId(nextAccount)) {
        setAccountId(nextAccount)
        applied = true
      }
      if (hostnames.length === 1) {
        setHostname(hostnames[0])
        applied = true
      } else if (hostnames.length > 1) {
        setMcpHostnameOptions(hostnames)
        setMcpHostnameSelected(hostnames[0])
        setMcpHostnameDialogOpen(true)
        applied = true
      }
      if (!applied) {
        enqueueSnackbar(t(K.page.networkAccess.setupFetchFromMcpNoUsableData), { variant: 'warning' })
        return
      }
      enqueueSnackbar(t(K.page.networkAccess.setupFetchFromMcpSuccess), { variant: 'success' })
    } catch (e: any) {
      const message = String(e?.response?.data?.detail || e?.message || 'mcp_discovery_failed')
      setError(t(K.page.networkAccess.setupFetchFromMcpFailed, { message }))
      enqueueSnackbar(t(K.page.networkAccess.setupFetchFromMcpFailed, { message }), { variant: 'error' })
    } finally {
      setFetchingMcp(false)
    }
  }

  const createTunnel = async () => {
    if (creatingTunnel) return
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    const name = createTunnelName.trim()
    if (!name) {
      setError(t(K.page.networkAccess.tunnelCreateFailed, { message: 'name_required' }))
      enqueueSnackbar(t(K.page.networkAccess.tunnelCreateFailed, { message: 'name_required' }), { variant: 'error' })
      return
    }
    setCreatingTunnel(true)
    setError('')
    try {
      const resp = await httpClient.post(
        '/api/network/cloudflare/tunnels/create',
        { params: { name } },
        { headers: { 'X-Admin-Token': token } }
      )
      const createdName = String(resp?.data?.tunnel?.name || name)
      await refresh()
      setTunnelName(createdName)
      setCreateTunnelName('')
      enqueueSnackbar(t(K.page.networkAccess.tunnelCreateSuccess, { name: createdName }), { variant: 'success' })
    } catch (e: any) {
      const message = String(e?.response?.data?.detail || e?.message || 'create_tunnel_failed')
      setError(t(K.page.networkAccess.tunnelCreateFailed, { message }))
      enqueueSnackbar(t(K.page.networkAccess.tunnelCreateFailed, { message }), { variant: 'error' })
    } finally {
      setCreatingTunnel(false)
    }
  }

  const refreshDaemonLogs = async () => {
    if (refreshingLogs) return
    setRefreshingLogs(true)
    try {
      await refresh()
    } finally {
      setRefreshingLogs(false)
    }
  }

  const clearDaemonLogs = async () => {
    if (clearingLogs) return
    const token = getToken()
    if (!token) {
      setError(t(K.page.networkAccess.adminTokenRequired))
      enqueueSnackbar(t(K.page.networkAccess.adminTokenRequired), { variant: 'error' })
      return
    }
    setClearingLogs(true)
    setError('')
    try {
      await httpClient.post('/api/network/cloudflare/daemon/logs/clear', {}, { headers: { 'X-Admin-Token': token } })
      enqueueSnackbar(t(K.page.networkAccess.daemonLogsCleared), { variant: 'success' })
      await refresh()
    } catch (e: any) {
      const message = String(e?.response?.data?.detail || e?.message || 'clear_logs_failed')
      setError(t(K.page.networkAccess.daemonLogsClearFailed, { message }))
      enqueueSnackbar(t(K.page.networkAccess.daemonLogsClearFailed, { message }), { variant: 'error' })
    } finally {
      setClearingLogs(false)
    }
  }

  const meta: ItemCardMeta[] = [
    { key: 'status', label: t(K.page.networkAccess.metaStatus), value: latest ? String(latest.status) : t(K.common.inactive) },
    { key: 'decision', label: t(K.page.networkAccess.metaGate), value: latest ? String(latest.decision) : '-' },
    { key: 'scope', label: t(K.page.networkAccess.metaScope), value: latest?.params?.scope ? String(latest.params.scope) : '/personal/' },
  ]

  const actions: ItemCardAction[] = [
    { key: 'refresh', label: t('common.refresh'), onClick: () => void refresh(), variant: 'outlined', tooltip: t(K.page.networkAccess.tipRefresh) },
    {
      key: 'enable',
      label: t(K.page.networkAccess.enableDialogTitle),
      onClick: () => setEnableDialogOpen(true),
      variant: 'contained',
      tooltip: t(K.page.networkAccess.tipEnableRequest),
    },
    ...(latest?.decision === 'explain_confirm' && latest?.status === 'pending'
      ? [{ key: 'approve', label: t(K.common.approve), onClick: () => void approve(), variant: 'contained', tooltip: t(K.page.networkAccess.tipApproveRequest) } as ItemCardAction]
      : []),
    ...(latest && latest.status !== 'revoked'
      ? [{ key: 'revoke', label: t(K.common.revoke), onClick: () => void revoke(), variant: 'outlined', tooltip: t(K.page.networkAccess.tipRevokeRequest) } as ItemCardAction]
      : []),
  ]

  const daemonLatest = useMemo(() => {
    const daemonReqs = requests.filter((r) => String(r.capability || '').startsWith('network.cloudflare.daemon.'))
    return pickLatest(daemonReqs)
  }, [requests])

  const daemonMeta: ItemCardMeta[] = [
    { key: 'daemon_state', label: t(K.page.networkAccess.daemonMetaState), value: daemon ? String(daemon.state || '-') : '-' },
    { key: 'daemon_installed', label: t(K.page.networkAccess.daemonMetaInstalled), value: daemon ? String(Boolean(daemon.installed)) : '-' },
    { key: 'daemon_service', label: t(K.page.networkAccess.daemonMetaServiceInstalled), value: daemon ? String(Boolean(daemon.service_installed)) : '-' },
    { key: 'daemon_autostart', label: t(K.page.networkAccess.daemonMetaAutostart), value: daemon ? String(Boolean(daemon.autostart_enabled)) : '-' },
    { key: 'daemon_creds', label: t(K.page.networkAccess.daemonMetaCredentials), value: daemon ? String(Boolean(daemon.credentials_present)) : '-' },
    { key: 'daemon_tunnel', label: t(K.page.networkAccess.daemonMetaTunnel), value: daemon?.tunnel_name ? String(daemon.tunnel_name) : '-' },
    { key: 'daemon_path', label: t(K.page.networkAccess.daemonMetaCloudflaredPath), value: daemon?.cloudflared_path ? String(daemon.cloudflared_path) : '-' },
    { key: 'daemon_version', label: t(K.page.networkAccess.daemonMetaCloudflaredVersion), value: daemon?.cloudflared_version ? String(daemon.cloudflared_version) : '-' },
    { key: 'daemon_req_status', label: t(K.page.networkAccess.daemonMetaRequestStatus), value: daemonLatest ? String(daemonLatest.status) : '-' },
    { key: 'daemon_gate', label: t(K.page.networkAccess.daemonMetaGate), value: daemonLatest ? String(daemonLatest.decision) : '-' },
    ...(daemonLatest?.decision === 'explain_confirm' && daemonLatest?.status === 'pending'
      ? [{ key: 'daemon_pending_hint', label: t(K.common.info), value: t(K.page.networkAccess.daemonPendingApprovalHint) } as ItemCardMeta]
      : []),
    { key: 'daemon_err', label: t(K.page.networkAccess.daemonMetaLastError), value: daemon?.last_error ? String(daemon.last_error) : '-' },
  ]

  const daemonPendingApproval = daemonLatest?.decision === 'explain_confirm' && daemonLatest?.status === 'pending'
  const tunnelNameExists = useMemo(() => {
    const cur = tunnelName.trim().toLowerCase()
    if (!cur) return false
    return tunnelCandidates.some((it) => String(it.name || '').trim().toLowerCase() === cur)
  }, [tunnelCandidates, tunnelName])

  const daemonPrereqReady = Boolean(
    daemon?.installed &&
      daemon?.credentials_present &&
      hostname.trim() &&
      accountId.trim() &&
      tunnelName.trim() &&
      tunnelNameExists
  )

  const daemonActions: ItemCardAction[] = [
    { key: 'daemon_refresh', label: t(K.common.refresh), onClick: () => void refresh(), variant: 'outlined', tooltip: t(K.page.networkAccess.tipRefresh) },
    ...(daemonPendingApproval
      ? [
          {
            key: 'daemon_approve',
            label: t(K.page.networkAccess.daemonApproveInstallAction),
            onClick: () => void approveDaemon(daemonLatest.id),
            variant: 'contained',
            disabled: approvingDaemon,
            tooltip: t(K.page.networkAccess.tipDaemonApprove),
          } as ItemCardAction,
        ]
      : []),
    ...(!daemonPendingApproval && daemonPrereqReady
      ? [
    ...(daemon?.service_installed
      ? [
          {
            key: 'daemon_uninstall',
            label: t(K.page.networkAccess.daemonActionUninstallService),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/uninstall'),
            variant: 'outlined',
            tooltip: t(K.page.networkAccess.tipDaemonUninstall),
          } as ItemCardAction,
        ]
      : [
          {
            key: 'daemon_install',
            label: t(K.page.networkAccess.daemonActionInstallService),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/install'),
            variant: 'outlined',
            disabled: daemon ? !daemon.installed : false,
            tooltip: daemon && !daemon.installed ? `${t(K.page.networkAccess.tipDaemonInstall)} ${t(K.common.buttonTooltipDisabledNote)}` : t(K.page.networkAccess.tipDaemonInstall),
          } as ItemCardAction,
        ]),
    ...(daemon?.state === 'running'
      ? [
          {
            key: 'daemon_stop',
            label: t(K.common.stop),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/stop'),
            variant: 'outlined',
            tooltip: t(K.page.networkAccess.tipDaemonStop),
          } as ItemCardAction,
        ]
      : [
          {
            key: 'daemon_start',
            label: t(K.common.start),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/start'),
            variant: 'contained',
            tooltip: t(K.page.networkAccess.tipDaemonStart),
          } as ItemCardAction,
        ]),
    ...(daemon?.service_installed
      ? [
          {
            key: 'daemon_restart',
            label: t(K.common.restart),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/restart'),
            variant: 'outlined',
            tooltip: t(K.page.networkAccess.tipDaemonRestart),
          } as ItemCardAction,
        ]
      : []),
    ...(daemon?.autostart_enabled
      ? [
          {
            key: 'daemon_autostart_off',
            label: t(K.common.disabled),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/autostart/disable'),
            variant: 'outlined',
            tooltip: t(K.page.networkAccess.tipDaemonAutostartOff),
          } as ItemCardAction,
        ]
      : [
          {
            key: 'daemon_autostart_on',
            label: t(K.common.enabled),
            onClick: () => void daemonAction('/api/network/cloudflare/daemon/autostart/enable'),
            variant: 'outlined',
            tooltip: t(K.page.networkAccess.tipDaemonAutostartOn),
          } as ItemCardAction,
        ]),
      ]
      : []),
  ]

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {t(K.page.networkAccess.detailsHidden)}
        </Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<HelpOutlineIcon fontSize="small" />}
          onClick={() => setHelpOpen(true)}
        >
          {t(K.page.networkAccess.helpAction)}
        </Button>
      </Box>
      <CardCollectionWrap loading={loading} singleFullWidth>
        <ItemCard title={t(K.page.networkAccess.cardTitle)} description={t(K.page.networkAccess.cardDesc)} icon="cloud" meta={meta} actions={actions} />
      </CardCollectionWrap>

      <CardCollectionWrap loading={loading} singleFullWidth>
        <ItemCard
          title={t(K.page.networkAccess.daemonCardTitle)}
          description={t(K.page.networkAccess.daemonCardDesc)}
          icon="cloud"
          meta={daemonMeta}
          actions={daemonActions}
        />
      </CardCollectionWrap>

      <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, p: 1.5, backgroundColor: 'background.paper' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="subtitle2">
            {t(K.page.networkAccess.daemonLogsTitle)}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              size="small"
              variant="outlined"
              onClick={() => void refreshDaemonLogs()}
              disabled={refreshingLogs}
              title={t(K.page.networkAccess.tipDaemonLogsRefresh)}
            >
              {t(K.page.networkAccess.daemonLogsRefreshAction)}
            </Button>
            <Button
              size="small"
              variant="outlined"
              color="warning"
              onClick={() => void clearDaemonLogs()}
              disabled={clearingLogs}
              title={t(K.page.networkAccess.tipDaemonLogsClear)}
            >
              {t(K.page.networkAccess.daemonLogsClearAction)}
            </Button>
          </Box>
        </Box>
        <Typography
          variant="body2"
          component="pre"
          sx={{
            m: 0,
            whiteSpace: 'pre-wrap',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            maxHeight: 320,
            overflowY: 'auto',
            overflowX: 'hidden',
            pr: 1,
          }}
        >
          {daemon?.logs_tail || t(K.page.networkAccess.daemonLogsEmpty)}
        </Typography>
      </Box>

      {error ? (
        <Typography variant="body2" color="error">
          {error}
        </Typography>
      ) : null}
      {!daemonPendingApproval && !daemonPrereqReady ? (
        <Typography variant="body2" color="warning.main">
          {t(K.page.networkAccess.setupBlockedHint)}
        </Typography>
      ) : null}

      <Divider />

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <Typography variant="h6">{t(K.page.networkAccess.settingsTitle)}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t(K.page.networkAccess.settingsHint)}
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 2 }}>
          <TextField label={t(K.page.networkAccess.hostname)} value={hostname} onChange={(e) => setHostname(e.target.value)} size="small" />
          <TextField label={t(K.page.networkAccess.accountId)} value={accountId} onChange={(e) => setAccountId(e.target.value)} size="small" />
          <TextField label={t(K.page.networkAccess.enforceAccess)} value={enforceAccess} onChange={(e) => setEnforceAccess(e.target.value)} size="small" />
          <TextField label={t(K.page.networkAccess.healthPath)} value={healthPath} onChange={(e) => setHealthPath(e.target.value)} size="small" />
          <TextField label={t(K.page.networkAccess.daemonMetaTunnel)} value={tunnelName} onChange={(e) => setTunnelName(e.target.value)} size="small" />
        </Box>
        {tunnelCandidates.length > 0 ? (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {tunnelCandidates.map((it) => (
              <Button
                key={`${it.id || it.name}`}
                variant={tunnelName.trim() === it.name ? 'contained' : 'outlined'}
                size="small"
                onClick={() => setTunnelName(it.name)}
                disabled={!it.credential_file_exists}
              >
                {it.name}
                {!it.credential_file_exists ? ` (${t(K.page.networkAccess.tunnelCandidateNoCredential)})` : ''}
              </Button>
            ))}
          </Box>
        ) : null}
        {tunnelName.trim() && !tunnelNameExists ? (
          <Typography variant="caption" color="warning.main">
            {t(K.page.networkAccess.tunnelNameInvalidHint)}
          </Typography>
        ) : null}
        <Grid container spacing={1} alignItems="center">
          <Grid item xs={12} md>
            <TextField
              size="small"
              label={t(K.page.networkAccess.tunnelCreateNameLabel)}
              value={createTunnelName}
              onChange={(e) => setCreateTunnelName(e.target.value)}
              fullWidth
            />
          </Grid>
          <Grid item xs={12} md="auto">
            <Button
              variant="outlined"
              onClick={() => void createTunnel()}
              disabled={creatingTunnel || !daemon?.installed || !daemon?.credentials_present}
              title={t(K.page.networkAccess.tipTunnelCreate)}
              sx={{ minWidth: 160, whiteSpace: 'nowrap' }}
            >
              {t(K.page.networkAccess.tunnelCreateAction)}
            </Button>
          </Grid>
        </Grid>
        <Typography variant="caption" color="text.secondary">
          {t(K.page.networkAccess.tunnelCreateHint)}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Button variant="outlined" onClick={() => void installCli()} disabled={installingCli || Boolean(daemon?.installed)}>
            {t(K.page.networkAccess.setupInstallCliAction)}
          </Button>
          <Button
            variant="outlined"
            onClick={() => {
              void navigator.clipboard?.writeText('cloudflared tunnel login')
              enqueueSnackbar(t(K.page.networkAccess.setupRunLoginCmd), { variant: 'info' })
            }}
            disabled={Boolean(daemon?.credentials_present)}
          >
            {t(K.page.networkAccess.setupRunLoginAction)}
          </Button>
          <Button
            variant="outlined"
            onClick={() => void fetchFromMcp()}
            disabled={fetchingMcp}
          >
            {t(K.page.networkAccess.setupFetchFromMcpAction)}
          </Button>
          <Button variant="outlined" onClick={() => void saveSettings()}>
            {t(K.common.save)}
          </Button>
          <Button variant="contained" onClick={() => void provisionAccess()}>
            {t(K.page.networkAccess.provisionAccess)}
          </Button>
          <Button variant="outlined" onClick={() => void revokeAccess()}>
            {t(K.page.networkAccess.revokeAccess)}
          </Button>
        </Box>

        <Typography variant="caption" color="text.secondary">
          {t(K.page.networkAccess.setupMcpHint)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t(K.page.networkAccess.valueSources)}{' '}
          {Object.keys(cfg)
            .filter((k) => k.startsWith('network.cloudflare.'))
            .map((k) => `${k}=${cfg[k]?.source || 'missing'}`)
            .join(' | ')}
        </Typography>
      </Box>

      <DialogForm
        open={enableDialogOpen}
        onClose={() => setEnableDialogOpen(false)}
        title={t(K.page.networkAccess.enableDialogTitle)}
        submitText={t(K.page.networkAccess.enableDialogSubmit)}
        cancelText={t('common.cancel')}
        onSubmit={requestEnable}
      >
        <Typography variant="body2" color="text.secondary">
          {t(K.page.networkAccess.enableDialogHint)}
        </Typography>
      </DialogForm>

      <DialogForm
        open={mcpHostnameDialogOpen}
        onClose={() => setMcpHostnameDialogOpen(false)}
        title={t(K.page.networkAccess.setupMcpChooseHostnameTitle)}
        submitText={t(K.page.networkAccess.setupMcpChooseHostnameConfirm)}
        cancelText={t('common.cancel')}
        onSubmit={() => {
          if (mcpHostnameSelected.trim()) {
            setHostname(mcpHostnameSelected.trim())
          }
          setMcpHostnameDialogOpen(false)
        }}
      >
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t(K.page.networkAccess.setupMcpChooseHostnameHint)}
        </Typography>
        <TextField
          fullWidth
          select
          size="small"
          label={t(K.page.networkAccess.setupMcpChooseHostnameLabel)}
          value={mcpHostnameSelected}
          onChange={(e) => setMcpHostnameSelected(String(e.target.value || ''))}
        >
          {mcpHostnameOptions.map((item) => (
            <MenuItem key={item} value={item}>
              {item}
            </MenuItem>
          ))}
        </TextField>
      </DialogForm>

      <DialogForm
        open={helpOpen}
        onClose={() => setHelpOpen(false)}
        title={t(K.page.networkAccess.helpTitle)}
        submitText={t('common.ok')}
        cancelText={t('common.cancel')}
        onSubmit={() => setHelpOpen(false)}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Typography variant="subtitle2">{t(K.page.networkAccess.helpTutorialTitle)}</Typography>
          <Typography variant="body2">1. {t(K.page.networkAccess.helpTutorialStep1)}</Typography>
          <Typography variant="body2">2. {t(K.page.networkAccess.helpTutorialStep2)}</Typography>
          <Typography variant="body2">3. {t(K.page.networkAccess.helpTutorialStep3)}</Typography>
          <Typography variant="body2">4. {t(K.page.networkAccess.helpTutorialStep4)}</Typography>
          <Typography variant="body2">5. {t(K.page.networkAccess.helpTutorialStep5)}</Typography>
          <Divider />
          <Typography variant="subtitle2">{t(K.page.networkAccess.helpOpsTitle)}</Typography>
          <Typography variant="body2">{t(K.page.networkAccess.helpOpsSummary)}</Typography>
          <Typography variant="body2">• {t(K.page.networkAccess.helpOpsLine1)}</Typography>
          <Typography variant="body2">• {t(K.page.networkAccess.helpOpsLine2)}</Typography>
          <Typography variant="body2">• {t(K.page.networkAccess.helpOpsLine3)}</Typography>
          <Divider />
          <Typography variant="subtitle2" color="error">
            {t(K.page.networkAccess.helpRiskTitle)}
          </Typography>
          <Typography variant="body2" color="error">
            • {t(K.page.networkAccess.helpRiskLine1)}
          </Typography>
          <Typography variant="body2" color="error">
            • {t(K.page.networkAccess.helpRiskLine2)}
          </Typography>
          <Typography variant="body2" color="error">
            • {t(K.page.networkAccess.helpRiskLine3)}
          </Typography>
          <Typography variant="body2" color="error">
            • {t(K.page.networkAccess.helpRiskLine4)}
          </Typography>
        </Box>
      </DialogForm>
    </Box>
  )
}
