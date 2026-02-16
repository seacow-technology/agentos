import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Stack, TextField, Typography } from '@mui/material'
import { usePageHeader, usePageActions, EmptyState } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { useEffect, useState } from 'react'
import { get, post } from '@/platform/http'
import { toast } from '@/ui/feedback'
import { useHighRiskConfirm } from '@/components/ssh/useHighRiskConfirm'
import { TrustGateBanner } from '@/components/ssh/TrustGateBanner'
import { parseTrustGateState, type TrustGateState } from '@/components/ssh/trustGateError'
import { useNavigate } from 'react-router-dom'
import { parseGateError } from '@/platform/gates/parseGateError'

export default function SshSftpPage() {
  const { t } = useTextTranslation()
  const navigate = useNavigate()
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>('')
  const [sessionId, setSessionId] = useState<string>('')
  const [path, setPath] = useState<string>('.')
  const [items, setItems] = useState<any[]>([])
  const [transfers, setTransfers] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedPath, setSelectedPath] = useState<string | null>(null)

  const [trustGate, setTrustGate] = useState<TrustGateState | null>(null)

  const [pendingRemovePath, setPendingRemovePath] = useState<string | null>(null)
  const removeConfirm = useHighRiskConfirm({ minReasonLen: 10 })

  usePageHeader({
    title: t(K.page.sshSftp.title),
    subtitle: t(K.page.sshSftp.subtitle),
  })

  const loadConnections = async () => {
    const resp = await get<any[]>('/api/connections')
    const running = (resp || []).filter((c: any) => String(c.status) === 'RUNNING')
    if (!selectedConnectionId && running[0]?.connection_id) {
      setSelectedConnectionId(String(running[0].connection_id))
    }
  }

  const loadTransfers = async (sid: string) => {
    const tResp: any = await get(`/api/sftp/transfers?session_id=${encodeURIComponent(sid)}&limit=50&offset=0`)
    setTransfers(Array.isArray(tResp?.items) ? tResp.items : [])
  }

  const openSession = async () => {
    setError(null)
    if (!selectedConnectionId) {
      setError(t(K.page.sshSftp.noRunningConnection))
      return
    }
    const resp: any = await post('/api/sftp/sessions/open', { connection_id: selectedConnectionId })
    setSessionId(String(resp.session_id || resp.sessionId || resp.session_id || resp.session_id))
    setItems([])
    setTransfers([])
    setSelectedPath(null)
    setTrustGate(null)
  }

  const list = async () => {
    if (!sessionId) return
    setError(null)
    try {
      const resp: any = await get(
        `/api/sftp/sessions/${encodeURIComponent(sessionId)}/list?path=${encodeURIComponent(path)}`,
      )
      setTrustGate(null)
      const next = Array.isArray(resp?.items) ? resp.items : []
      setItems(next)
      if (next.length > 0) {
        const defaultSel = (() => {
          const readme = next.find((x: any) => String(x?.name) === 'README.txt')
          if (readme) return joinRemotePath(path, String(readme.name))
          return joinRemotePath(path, String(next[0]?.name || ''))
        })()
        setSelectedPath(defaultSel || null)
      } else {
        setSelectedPath(null)
      }
      await loadTransfers(sessionId)
    } catch (e: any) {
      const g = parseGateError(e)
      if (g?.gate === 'trust' && (g.errorCode === 'NEEDS_TRUST' || g.errorCode === 'FINGERPRINT_MISMATCH')) {
        setItems([])
        setSelectedPath(null)
        setTrustGate(parseTrustGateState(g.raw))
        setError(String(g.message || t(K.page.sshSftp.hostNotTrusted)))
        await loadTransfers(sessionId)
        return
      }
      throw e
    }
  }

  const probeDownload = async () => {
    if (!sessionId) return
    await post(`/api/sftp/sessions/${encodeURIComponent(sessionId)}/download`, { path: `${path}/README.txt` })
    await list()
  }

  const trustNow = async () => {
    if (!trustGate) return
    try {
      await post('/api/known_hosts', {
        host: trustGate.host,
        port: trustGate.port,
        fingerprint: trustGate.fingerprint,
        algo: trustGate.algo,
      })
      toast.success(t(K.page.sshSftp.trustedHost))
      setTrustGate(null)
      await list()
    } catch (e: any) {
      toast.error(String(e?.message || t(K.page.sshSftp.trustFailed)))
    }
  }

  const startRemoveHighRisk = async () => {
    if (!sessionId || !selectedPath) return
    removeConfirm.setError(null)
    setError(null)
    try {
      const res = await removeConfirm.requestConfirm(async () => {
        await post(`/api/sftp/sessions/${encodeURIComponent(sessionId)}/remove`, { path: selectedPath })
      })
      if (!res.needsConfirm) {
        toast.success(t(K.page.sshSftp.removed))
        await list()
        return
      }
      setPendingRemovePath(selectedPath)
      await loadTransfers(sessionId)
      return
    } catch (e: any) {
      const g = parseGateError(e)
      if (g?.gate === 'trust' && (g.errorCode === 'NEEDS_TRUST' || g.errorCode === 'FINGERPRINT_MISMATCH')) {
        const merged = { error_code: g.errorCode, ...(g.context || {}) }
        setTrustGate(parseTrustGateState(merged))
        setError(t(K.page.sshSftp.hostNotTrustedDestructive))
        return
      }
      removeConfirm.setError(String(g?.message || e?.message || t(K.page.sshSftp.removeFailed)))
    }
  }

  const confirmRemoveHighRisk = async () => {
    if (!sessionId || !pendingRemovePath) return
    await removeConfirm.confirm(async (token, reason) => {
      await post(`/api/sftp/sessions/${encodeURIComponent(sessionId)}/remove`, {
        path: pendingRemovePath,
        confirm: true,
        confirm_token: token,
        reason,
      })
      toast.success(t(K.page.sshSftp.removed))
      setPendingRemovePath(null)
      await list()
    })
  }

  useEffect(() => {
    void loadConnections()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  return (
    <Box>
      {error && (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        <Button variant="outlined" onClick={() => void loadConnections()}>
          {t(K.page.sshSftp.loadConnections)}
        </Button>
        <Button variant="contained" onClick={() => void openSession()}>
          {t(K.page.sshSftp.openSession)}
        </Button>
        <Typography variant="caption" color="text.secondary" sx={{ alignSelf: 'center' }}>
          {sessionId ? `${t(K.page.sshSftp.sessionIdLabel)}: ${sessionId}` : ''}
        </Typography>
      </Stack>

      <TrustGateBanner
        state={trustGate}
        onTrustNow={trustNow}
        onViewKnownHosts={() => navigate('/ssh/known-hosts')}
      />

      {sessionId ? (
        <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
          <TextField value={path} onChange={(e) => setPath(e.target.value)} size="small" fullWidth />
          <Button variant="outlined" onClick={() => void list()}>
            {t(K.page.sshSftp.list)}
          </Button>
          <Button variant="outlined" onClick={() => void probeDownload()}>
            {t(K.page.sshSftp.downloadProbe)}
          </Button>
        </Stack>
      ) : null}

      {sessionId && items.length === 0 ? (
        <EmptyState title={t(K.page.sshSftp.emptyTitle)} description={t(K.page.sshSftp.emptyDesc)} />
      ) : sessionId ? (
        <Box
          sx={{
            bgcolor: 'rgba(0,0,0,0.06)',
            borderRadius: 2,
            p: 1.5,
            overflow: 'auto',
            maxHeight: 640,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            {t(K.page.sshSftp.listingPrefix)}: {path}
          </Typography>
          {items.length > 0 ? (
            <Stack direction="row" spacing={1} sx={{ mb: 1, alignItems: 'center', flexWrap: 'wrap' }}>
              <Typography variant="caption" color="text.secondary">
                {t(K.page.sshSftp.selectedLabel)}:
              </Typography>
              <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                {selectedPath || t(K.page.sshSftp.none)}
              </Typography>
              <Button
                data-testid="sftp-remove-high-risk"
                size="small"
                color="error"
                variant="outlined"
                disabled={!selectedPath}
                onClick={() => void startRemoveHighRisk()}
              >
                {t(K.page.sshSftp.removeHighRisk)}
              </Button>
            </Stack>
          ) : null}
          <pre data-testid="sftp-items" style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(items, null, 2)}
          </pre>
          {items.length > 0 ? (
            <Stack spacing={0.5} sx={{ mt: 1 }}>
              {items.map((it: any) => {
                const name = String(it?.name || '')
                const full = joinRemotePath(path, name)
                const active = selectedPath === full
                return (
                  <Button
                    key={name}
                    size="small"
                    variant={active ? 'contained' : 'outlined'}
                    onClick={() => setSelectedPath(full)}
                    sx={{ justifyContent: 'space-between' }}
                  >
                    <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{name}</span>
                    <span style={{ fontFamily: 'monospace', fontSize: 12 }}>
                      {String(it?.type || t(K.page.sshSftp.fileTypeFallback))}
                    </span>
                  </Button>
                )
              })}
            </Stack>
          ) : null}
          <Divider sx={{ my: 1.5 }} />
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            {t(K.page.sshSftp.transfers)}
          </Typography>
          <pre data-testid="sftp-transfers" style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(transfers, null, 2)}
          </pre>
        </Box>
      ) : (
        <EmptyState title={t(K.page.sshSftp.title)} description={t(K.page.sshSftp.subtitle)} />
      )}

      <Dialog
        open={removeConfirm.open}
        onClose={() => removeConfirm.cancel()}
        maxWidth="sm"
        fullWidth
        data-testid="sftp-remove-confirm-dialog"
      >
        <DialogTitle>{t(K.page.sshSftp.dialogTitle)}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {t(K.page.sshSftp.dialogBody)}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            {t(K.page.sshSftp.dialogMustProvideReason)}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1, fontFamily: 'monospace' }}>
            {t(K.page.sshSftp.dialogPathLabel)}: {pendingRemovePath}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1, fontFamily: 'monospace' }}>
            {t(K.page.sshSftp.dialogCapabilityLabel)}
          </Typography>
          <TextField
            label={t(K.page.sshSftp.reasonRequired)}
            value={removeConfirm.reason}
            onChange={(e) => removeConfirm.setReason(e.target.value)}
            fullWidth
            multiline
            minRows={3}
            sx={{ mt: 1 }}
            inputProps={{ 'data-testid': 'sftp-remove-reason' }}
          />
          {removeConfirm.error ? (
            <Typography variant="body2" color="error" sx={{ mt: 1 }}>
              {removeConfirm.error}
            </Typography>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button data-testid="sftp-remove-cancel" onClick={() => removeConfirm.cancel()}>
            {t(K.common.cancel)}
          </Button>
          <Button
            data-testid="sftp-remove-confirm"
            variant="contained"
            color="error"
            onClick={() => void confirmRemoveHighRisk()}
          >
            {t(K.page.sshSftp.confirmRemove)}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

function joinRemotePath(dir: string, name: string): string {
  const d = String(dir || '.').trim() || '.'
  const n = String(name || '').trim()
  if (!n) return d
  if (d === '.' || d === './') return `./${n}`
  if (d.endsWith('/')) return `${d}${n}`
  return `${d}/${n}`
}
