import { useCallback, useEffect, useMemo, useState } from 'react'
import { usePageActions, usePageHeader } from '@/ui/layout'
import { Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Grid, Stack, TextField, Typography } from '@/ui'
import { teamsApi, type TeamsOrgConnection, type TeamsDeployResult } from '@/api/teams'
import { useSnackbar } from 'notistack'
import { K, useTextTranslation } from '@/ui/text'

function fmtTs(ms?: number): string {
  if (!ms) return '-'
  try {
    return new Date(ms).toLocaleString()
  } catch {
    return String(ms)
  }
}

const statusColor: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
  Disconnected: 'default',
  Authorized: 'info',
  AppUploaded: 'info',
  Installed: 'warning',
  InstalledButUnverified: 'warning',
  Verified: 'success',
  Blocked: 'error',
  PartiallyConnected: 'warning',
}

export default function ChannelsTeamsPage() {
  const { enqueueSnackbar } = useSnackbar()
  const { t } = useTextTranslation()
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState<TeamsOrgConnection[]>([])
  const [reconciling, setReconciling] = useState<string>('')
  const [connecting, setConnecting] = useState(false)
  const [tenantHint, setTenantHint] = useState('')
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [evidenceText, setEvidenceText] = useState('')
  const [evidenceTitle, setEvidenceTitle] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await teamsApi.listOrgs()
      setRows(Array.isArray(res.items) ? res.items : [])
    } catch (err: any) {
      enqueueSnackbar(err?.response?.data?.detail || err?.message || t(K.page.channelsTeams.errLoadFailed), { variant: 'error' })
    } finally {
      setLoading(false)
    }
  }, [enqueueSnackbar, t])

  useEffect(() => {
    load()
  }, [load])

  usePageHeader({
    title: t(K.page.channelsTeams.title),
    subtitle: t(K.page.channelsTeams.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.page.channelsTeams.actionRefresh),
      variant: 'outlined',
      onClick: () => void load(),
    },
  ])

  const openConnect = useCallback(async () => {
    setConnecting(true)
    try {
      const res = await teamsApi.startOAuth(tenantHint.trim() || undefined)
      if (!res?.auth_url) {
        throw new Error('Missing auth url')
      }
      window.location.href = res.auth_url
    } catch (err: any) {
      enqueueSnackbar(err?.response?.data?.detail || err?.message || t(K.page.channelsTeams.errStartOAuthFailed), { variant: 'error' })
      setConnecting(false)
    }
  }, [enqueueSnackbar, t, tenantHint])

  const doReconcile = useCallback(
    async (tenantId: string) => {
      setReconciling(tenantId)
      try {
        const res = await teamsApi.reconcile(tenantId)
        const result = res.result as TeamsDeployResult
        enqueueSnackbar(
          result?.ok ? t(K.page.channelsTeams.toastReconcileOk, { tenantId }) : t(K.page.channelsTeams.toastReconcileWarn, { tenantId }),
          {
          variant: result?.ok ? 'success' : 'warning',
        }
        )
      } catch (err: any) {
        enqueueSnackbar(err?.response?.data?.detail || err?.message || t(K.page.channelsTeams.errReconcileFailed), { variant: 'error' })
      } finally {
        setReconciling('')
        void load()
      }
    },
    [enqueueSnackbar, load, t]
  )

  const doDisconnect = useCallback(
    async (tenantId: string) => {
      try {
        await teamsApi.disconnect(tenantId)
        enqueueSnackbar(t(K.page.channelsTeams.toastDisconnected, { tenantId }), { variant: 'success' })
        void load()
      } catch (err: any) {
        enqueueSnackbar(err?.response?.data?.detail || err?.message || t(K.page.channelsTeams.errDisconnectFailed), { variant: 'error' })
      }
    },
    [enqueueSnackbar, load, t]
  )

  const openEvidence = useCallback(
    async (tenantId: string) => {
      try {
        const res = await teamsApi.getEvidence(tenantId)
        const md = String(res?.evidence?.md || '')
        setEvidenceTitle(t(K.page.channelsTeams.evidenceTitle, { tenantId }))
        setEvidenceText(md || t(K.page.channelsTeams.evidenceEmpty))
        setEvidenceOpen(true)
      } catch (err: any) {
        enqueueSnackbar(err?.response?.data?.detail || err?.message || t(K.page.channelsTeams.errEvidenceFailed), { variant: 'error' })
      }
    },
    [enqueueSnackbar, t]
  )

  const hasRows = useMemo(() => rows.length > 0, [rows])

  return (
    <Box sx={{ p: 2, display: 'grid', gap: 2 }}>
      <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
        <Grid container spacing={1.5} alignItems="center">
          <Grid item xs={12} md>
            <TextField
              label={t(K.page.channelsTeams.fieldTenantHint)}
              placeholder={t(K.page.channelsTeams.fieldTenantHintPlaceholder)}
              value={tenantHint}
              onChange={(e) => setTenantHint(e.target.value)}
              size="small"
              fullWidth
            />
          </Grid>
          <Grid item xs={12} md="auto">
            <Button
              variant="contained"
              onClick={() => void openConnect()}
              disabled={connecting}
              sx={{ minWidth: 160, whiteSpace: 'nowrap' }}
            >
              {connecting ? t(K.page.channelsTeams.actionRedirecting) : t(K.page.channelsTeams.actionConnectOrg)}
            </Button>
          </Grid>
        </Grid>
      </Box>

      <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
        {loading ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <CircularProgress size={18} />
            <Typography variant="body2">{t(K.page.channelsTeams.loadingOrgs)}</Typography>
          </Stack>
        ) : !hasRows ? (
          <Typography variant="body2" color="text.secondary">{t(K.page.channelsTeams.emptyOrgs)}</Typography>
        ) : (
          <Stack spacing={1.5}>
            {rows.map((row) => (
              <Box key={row.tenant_id} sx={{ p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1.5 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
                  <Box>
                    <Typography variant="subtitle2">{row.display_name || row.tenant_id}</Typography>
                    <Typography variant="caption" color="text.secondary">{t(K.page.channelsTeams.metaTenant)}: {row.tenant_id}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                      {t(K.page.channelsTeams.metaApp)}: {row.teams_app_id || '-'} | {t(K.page.channelsTeams.metaStrategy)}: {row.deployment_strategy} | {t(K.page.channelsTeams.metaUpdated)}: {fmtTs(row.updated_at_ms)}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Chip size="small" color={statusColor[row.status] || 'default'} label={row.status} />
                    <Button size="small" variant="outlined" disabled={reconciling === row.tenant_id} onClick={() => void doReconcile(row.tenant_id)}>
                      {reconciling === row.tenant_id ? t(K.page.channelsTeams.actionReconciling) : t(K.page.channelsTeams.actionReconcile)}
                    </Button>
                    <Button size="small" variant="outlined" onClick={() => void openEvidence(row.tenant_id)}>
                      {t(K.page.channelsTeams.actionViewEvidence)}
                    </Button>
                    <Button size="small" color="error" variant="text" onClick={() => void doDisconnect(row.tenant_id)}>
                      {t(K.page.channelsTeams.actionDisconnect)}
                    </Button>
                  </Stack>
                </Stack>
              </Box>
            ))}
          </Stack>
        )}
      </Box>

      <Dialog open={evidenceOpen} onClose={() => setEvidenceOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>{evidenceTitle}</DialogTitle>
        <DialogContent dividers>
          <TextField fullWidth multiline minRows={20} value={evidenceText} InputProps={{ readOnly: true }} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEvidenceOpen(false)}>{t(K.page.channelsTeams.close)}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
