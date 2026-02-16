import { Box, Button, Divider, Stack, TextField, Typography } from '@mui/material'
import { usePageHeader, usePageActions, EmptyState } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { useEffect, useMemo, useState } from 'react'
import { get, post } from '@/platform/http'
import { useNavigate } from 'react-router-dom'
import { TrustGateBanner } from '@/components/ssh/TrustGateBanner'
import { type TrustGateState, parseTrustGateState } from '@/components/ssh/trustGateError'
import { toast } from '@/ui/feedback'
import { parseGateError } from '@/platform/gates/parseGateError'

type ConnectionStatus = 'OPENING' | 'RUNNING' | 'DETACHED' | 'CLOSED' | 'FAILED'

interface Host {
  host_id: string
  label?: string | null
  hostname: string
  port: number
}

interface Connection {
  connection_id: string
  host_id: string
  status: ConnectionStatus
  label?: string | null
  probe_only: boolean
  created_at: string
  updated_at: string
}

interface ConnectionEvent {
  connection_id: string
  seq: number
  ts: string
  type: string
  data: Record<string, unknown>
}

export default function SshConnectionsPage() {
  const { t } = useTextTranslation()
  const navigate = useNavigate()
  const [hosts, setHosts] = useState<Host[]>([])
  const [connections, setConnections] = useState<Connection[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [cmd, setCmd] = useState('')
  const [events, setEvents] = useState<ConnectionEvent[]>([])
  const [lastSeq, setLastSeq] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [trustGate, setTrustGate] = useState<TrustGateState | null>(null)
  const [retryCmd, setRetryCmd] = useState<string | null>(null)
  const selected = useMemo(
    () => connections.find((c) => c.connection_id === selectedId) || null,
    [connections, selectedId],
  )

  usePageHeader({
    title: t(K.page.sshConnections.title),
    subtitle: t(K.page.sshConnections.subtitle),
  })

  const loadHosts = async () => {
    const resp = await get<any[]>('/api/hosts')
    setHosts(
      (resp || []).map((h: any) => ({
        host_id: String(h.host_id),
        label: h.label ?? null,
        hostname: String(h.hostname || ''),
        port: Number(h.port || 22),
      })),
    )
  }

  const loadConnections = async () => {
    const resp = await get<any[]>('/api/connections')
    setConnections(
      (resp || []).map((c: any) => ({
        connection_id: String(c.connection_id),
        host_id: String(c.host_id),
        status: String(c.status) as ConnectionStatus,
        label: c.label ?? null,
        probe_only: Boolean(c.probe_only),
        created_at: String(c.created_at || ''),
        updated_at: String(c.updated_at || ''),
      })),
    )
  }

  const loadEvents = async (connectionId: string, from: number) => {
    const resp = await get<any>(`/api/connections/${encodeURIComponent(connectionId)}/events?from_seq=${from}&limit=200`)
    const items: ConnectionEvent[] = Array.isArray(resp?.items) ? resp.items : []
    if (items.length > 0) {
      setEvents((prev) => [...prev, ...items])
    }
    if (typeof resp?.next_seq === 'number') {
      setLastSeq(resp.next_seq)
    }
  }

  const openProbeConnection = async () => {
    setError(null)
    const hostList: Host[] = (() => {
      // Use freshest data to avoid stale state issues in tests.
      return hosts
    })()
    let h = hostList[0]
    if (!h) {
      const resp = await get<any[]>('/api/hosts')
      const parsed = (resp || []).map((x: any) => ({
        host_id: String(x.host_id),
        label: x.label ?? null,
        hostname: String(x.hostname || ''),
        port: Number(x.port || 22),
      }))
      setHosts(parsed)
      h = parsed[0]
    }
    if (!h) {
      setError(t(K.page.sshConnections.noHostsError))
      return
    }
    const resp: any = await post('/api/connections/open', { host_id: h.host_id, mode: 'ssh', probe_only: true })
    await loadConnections()
    setSelectedId(resp.connection_id)
    setEvents([])
    setLastSeq(0)
    setTrustGate(null)
    setRetryCmd(null)
    await loadEvents(resp.connection_id, 0)
  }

  const detach = async () => {
    if (!selected) return
    await post(`/api/connections/${encodeURIComponent(selected.connection_id)}/detach`, {})
    await loadConnections()
  }

  const attach = async () => {
    if (!selected) return
    await post(`/api/connections/${encodeURIComponent(selected.connection_id)}/attach`, {})
    await loadConnections()
  }

  const close = async () => {
    if (!selected) return
    await post(`/api/connections/${encodeURIComponent(selected.connection_id)}/close`, {})
    await loadConnections()
  }

  const exec = async () => {
    if (!selected) return
    const command = cmd.trim()
    if (!command) return
    setCmd('')
    try {
      await post(`/api/connections/${encodeURIComponent(selected.connection_id)}/exec`, { command })
      setTrustGate(null)
      setRetryCmd(null)
      await loadEvents(selected.connection_id, lastSeq || 0)
    } catch (e: any) {
      const g = parseGateError(e)
      if (g?.gate === 'trust' && (g.errorCode === 'NEEDS_TRUST' || g.errorCode === 'FINGERPRINT_MISMATCH')) {
        const st = parseTrustGateState(g.raw)
        setTrustGate(st)
        setRetryCmd(command)
        return
      }
      throw e
    }
  }

  const trustHost = async () => {
    if (!trustGate) return
    if (!selected) return
    setError(null)
    try {
      await post('/api/known_hosts', {
        host: trustGate.host,
        port: trustGate.port,
        fingerprint: trustGate.fingerprint,
        algo: trustGate.algo,
      })
      toast.success(t(K.page.sshConnections.trustedHost))
      setTrustGate(null)
      const cmdToRetry = retryCmd
      setRetryCmd(null)
      if (cmdToRetry) {
        await post(`/api/connections/${encodeURIComponent(selected.connection_id)}/exec`, { command: cmdToRetry })
      }
      await loadEvents(selected.connection_id, lastSeq || 0)
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {
        void loadConnections()
      },
    },
  ])

  useEffect(() => {
    let alive = true
    const boot = async () => {
      try {
        await loadHosts()
        await loadConnections()
      } catch (e: any) {
        if (alive) setError(String(e?.message || e))
      }
    }
    void boot()
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setEvents([])
    setLastSeq(0)
    void loadEvents(selectedId, 0)
    const id = window.setInterval(() => void loadEvents(selectedId, lastSeq || 0), 1500)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  return (
    <Box>
      {error && (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="stretch">
        <Box sx={{ width: { xs: '100%', md: 420 } }}>
          <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
            <Button variant="contained" onClick={() => void openProbeConnection()}>
              {t(K.page.sshConnections.openProbe)}
            </Button>
            <Button variant="outlined" onClick={() => void loadConnections()}>
              {t(K.common.refresh)}
            </Button>
          </Stack>

          {connections.length === 0 ? (
            <EmptyState title={t(K.page.sshConnections.title)} description={t(K.page.sshConnections.subtitle)} />
          ) : (
            <Stack spacing={1}>
              {connections.map((c) => (
                <Button
                  key={c.connection_id}
                  variant={c.connection_id === selectedId ? 'contained' : 'outlined'}
                  onClick={() => setSelectedId(c.connection_id)}
                  sx={{ justifyContent: 'space-between' }}
                >
                  <span>{c.label?.trim() ? c.label : c.connection_id.slice(0, 8)}</span>
                  <span>{c.status}</span>
                </Button>
              ))}
            </Stack>
          )}
        </Box>

        <Box sx={{ flex: 1 }}>
          {!selected ? (
            <EmptyState title={t(K.page.sshConnections.selectTitle)} description={t(K.page.sshConnections.selectDesc)} />
          ) : (
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                  {selected.connection_id}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {selected.status} {selected.probe_only ? t(K.page.sshConnections.probeBadge) : ''}
                </Typography>
              </Stack>

              <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                <Button size="small" variant="outlined" onClick={() => void detach()}>
                  {t(K.page.sshConnections.detach)}
                </Button>
                <Button size="small" variant="outlined" onClick={() => void attach()}>
                  {t(K.page.sshConnections.attach)}
                </Button>
                <Button size="small" variant="outlined" color="error" onClick={() => void close()}>
                  {t(K.page.sshConnections.close)}
                </Button>
              </Stack>

              <Divider sx={{ mb: 1 }} />

              <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                <TextField
                  value={cmd}
                  onChange={(e) => setCmd(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void exec()
                    }
                  }}
                  size="small"
                  fullWidth
                  placeholder={t(K.page.sshConnections.cmdPlaceholder)}
                  inputProps={{ 'data-testid': 'ssh-connection-exec-input' }}
                />
                <Button variant="contained" onClick={() => void exec()}>
                  {t(K.page.sshConnections.exec)}
                </Button>
              </Stack>
              <TrustGateBanner
                state={trustGate}
                onTrustNow={trustHost}
                onViewKnownHosts={() => navigate('/ssh/known-hosts')}
              />

              <Box
                sx={{
                  bgcolor: 'rgba(0,0,0,0.06)',
                  borderRadius: 2,
                  p: 1.5,
                  minHeight: 240,
                  maxHeight: 520,
                  overflow: 'auto',
                }}
              >
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                  {events
                    .map((e) => {
                      const d: any = e.data || {}
                      if (typeof d.text === 'string') return d.text
                      if (typeof d.message === 'string') return `[${e.type}] ${d.message}\n`
                      return `[${e.type}] ${JSON.stringify(d)}\n`
                    })
                    .join('') || ' '}
                </pre>
              </Box>
            </Box>
          )}
        </Box>
      </Stack>
    </Box>
  )
}
