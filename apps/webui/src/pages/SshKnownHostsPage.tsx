import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material'
import { usePageHeader, usePageActions, EmptyState } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { useEffect, useMemo, useState } from 'react'
import { del, get, post } from '@/platform/http'
import { toast } from '@/ui/feedback'
import { useHighRiskConfirm } from '@/components/ssh/useHighRiskConfirm'

type KnownHostItem = {
  known_host_id: string
  host: string
  port: number
  fingerprint: string
  algo?: string | null
  created_at: string
}

export default function SshKnownHostsPage() {
  const { t } = useTextTranslation()
  const [items, setItems] = useState<KnownHostItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<KnownHostItem | null>(null)
  const replaceConfirm = useHighRiskConfirm({ minReasonLen: 10 })

  usePageHeader({
    title: t(K.page.sshKnownHosts.title),
    subtitle: t(K.page.sshKnownHosts.subtitle),
  })

  const load = async () => {
    setLoading(true)
    try {
      const resp = await get<any[]>('/api/known_hosts')
      setItems(
        (resp || []).map((x: any) => ({
          known_host_id: String(x.known_host_id),
          host: String(x.host || ''),
          port: Number(x.port || 22),
          fingerprint: String(x.fingerprint || ''),
          algo: x.algo ? String(x.algo) : null,
          created_at: String(x.created_at || ''),
        })),
      )
    } catch (e: any) {
      toast.error(String(e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await del(`/api/known_hosts/${encodeURIComponent(id)}`)
      toast.success(t(K.page.sshKnownHosts.removed))
      await load()
    } catch (e: any) {
      toast.error(String(e?.message || e))
    }
  }

  const startReplace = async (it: KnownHostItem) => {
    setSelected(it)
    replaceConfirm.setError(null)
    const res = await replaceConfirm.requestConfirm(async () => {
      await post('/api/known_hosts/replace', { host: it.host, port: it.port, fingerprint: it.fingerprint, algo: it.algo })
    })
    if (!res.needsConfirm) {
      toast.success(t(K.page.sshKnownHosts.replaced))
      await load()
    }
  }

  const confirmReplace = async () => {
    const it = selected
    if (!it) return
    await replaceConfirm.confirm(async (token, reason) => {
      await post('/api/known_hosts/replace', {
        host: it.host,
        port: it.port,
        fingerprint: it.fingerprint,
        algo: it.algo,
        confirm: true,
        confirm_token: token,
        reason,
      })
      toast.success(t(K.page.sshKnownHosts.replaced))
      setSelected(null)
      await load()
    })
  }

  const groups = useMemo(() => {
    const map = new Map<string, KnownHostItem[]>()
    for (const it of items) {
      const k = `${it.host}:${it.port}`
      const arr = map.get(k) || []
      arr.push(it)
      map.set(k, arr)
    }
    return Array.from(map.entries()).map(([key, list]) => {
      const uniq = new Set(list.map((x) => x.fingerprint))
      return { key, list, conflict: uniq.size > 1 }
    })
  }, [items])

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => {
        void load()
      },
    },
  ])

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Box>
      {loading ? (
        <Typography variant="body2">{t(K.common.loading)}</Typography>
      ) : items.length === 0 ? (
        <EmptyState title={t(K.page.sshKnownHosts.title)} description={t(K.page.sshKnownHosts.subtitle)} />
      ) : (
        <Stack spacing={2}>
          {groups.map((g) => (
            <Box
              key={g.key}
              sx={{
                border: '1px solid rgba(0,0,0,0.12)',
                borderRadius: 2,
                p: 1.25,
                bgcolor: g.conflict ? 'rgba(255,0,0,0.03)' : 'transparent',
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                  {g.key}
                </Typography>
                {g.conflict ? (
                  <Typography variant="caption" color="error" sx={{ fontWeight: 800 }}>
                    {t(K.page.sshKnownHosts.conflict)}
                  </Typography>
                ) : null}
              </Stack>

              <Stack spacing={1}>
                {g.list.map((it) => (
                  <Box
                    key={it.known_host_id}
                    data-testid="known-hosts-row"
                    sx={{
                      border: '1px solid rgba(0,0,0,0.10)',
                      borderRadius: 2,
                      p: 1,
                      bgcolor: 'rgba(0,0,0,0.02)',
                    }}
                  >
                    <Typography data-testid="known-hosts-fingerprint" variant="caption" sx={{ display: 'block', fontFamily: 'monospace' }}>
                      {it.fingerprint} {it.algo ? `(${it.algo})` : ''}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {it.created_at}
                    </Typography>
                    <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
                      <Button
                        size="small"
                        variant="outlined"
                        color="error"
                        onClick={() => void remove(it.known_host_id)}
                      >
                        {t(K.common.delete)}
                      </Button>
                      <Button
                        data-testid="known-hosts-replace-high-risk"
                        size="small"
                        variant="outlined"
                        color="warning"
                        onClick={() => void startReplace(it)}
                      >
                        {t(K.page.sshKnownHosts.replaceHighRisk)}
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          void navigator.clipboard?.writeText(it.fingerprint)
                          toast.info(t(K.page.sshKnownHosts.copiedFingerprint))
                        }}
                      >
                        {t(K.page.sshKnownHosts.copyFingerprint)}
                      </Button>
                    </Stack>
                  </Box>
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      )}

      <Dialog
        open={replaceConfirm.open}
        onClose={() => {
          replaceConfirm.cancel()
          setSelected(null)
        }}
        maxWidth="sm"
        fullWidth
        data-testid="known-hosts-replace-confirm-dialog"
      >
        <DialogTitle>{t(K.page.sshKnownHosts.dialogTitle)}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {t(K.page.sshKnownHosts.dialogBody)}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            {t(K.page.sshKnownHosts.dialogMustProvideReason)}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1, fontFamily: 'monospace' }}>
            {selected ? `${selected.host}:${selected.port}` : ''}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1, fontFamily: 'monospace' }}>
            {t(K.page.sshKnownHosts.dialogFingerprintLabel)}: {selected ? selected.fingerprint : ''}
          </Typography>
          <Typography variant="caption" sx={{ display: 'block', mb: 1, fontFamily: 'monospace' }}>
            {t(K.page.sshKnownHosts.dialogCapabilityLabel)}
          </Typography>
          <Box sx={{ mt: 1 }}>
            <textarea
              data-testid="known-hosts-replace-reason"
              value={replaceConfirm.reason}
              onChange={(e) => replaceConfirm.setReason(e.target.value)}
              rows={3}
              style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid rgba(0,0,0,0.2)' }}
            />
          </Box>
          {replaceConfirm.error ? (
            <Typography variant="body2" color="error" sx={{ mt: 1 }}>
              {replaceConfirm.error}
            </Typography>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button
            data-testid="known-hosts-replace-cancel"
            onClick={() => {
              replaceConfirm.cancel()
              setSelected(null)
            }}
          >
            {t(K.common.cancel)}
          </Button>
          <Button
            data-testid="known-hosts-replace-confirm"
            variant="contained"
            color="error"
            onClick={() => void confirmReplace()}
          >
            {t(K.page.sshKnownHosts.dialogConfirmReplace)}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
