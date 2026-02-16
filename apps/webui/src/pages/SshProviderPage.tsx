import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  FormControl,
  FormControlLabel,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePageActions, usePageHeader } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { get, post } from '@/platform/http'
import { parseGateError } from '@/platform/gates/parseGateError'
import { useHighRiskConfirm } from '@/components/ssh/useHighRiskConfirm'

type Effective = {
  provider: 'probe' | 'system' | 'mcp'
  source: 'builtin' | 'file' | 'db' | 'env'
  allow_real: boolean
  mcp_profile: string | null
  effective_at: number
  requires_restart: boolean
}

export default function SshProviderPage() {
  const { t } = useTextTranslation()
  const navigate = useNavigate()

  const [effective, setEffective] = useState<Effective | null>(null)
  const [sources, setSources] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const [provider, setProvider] = useState<'probe' | 'system' | 'mcp'>('probe')
  const [allowReal, setAllowReal] = useState(false)
  const [mcpProfile, setMcpProfile] = useState('')

  const [exportSha, setExportSha] = useState<string | null>(null)
  const [exportGeneratedAt, setExportGeneratedAt] = useState<string | null>(null)

  const [dbNotAvailable, setDbNotAvailable] = useState(false)

  const applyConfirm = useHighRiskConfirm({ minReasonLen: 10 })
  const dbInitConfirm = useHighRiskConfirm({ minReasonLen: 10 })

  usePageHeader({
    title: t(K.page.sshProvider.title),
    subtitle: t(K.page.sshProvider.subtitle),
  })

  const load = async () => {
    setError(null)
    try {
      const eff = await get<Effective>('/api/providers/ssh')
      setEffective(eff)
      setProvider(eff.provider)
      setAllowReal(Boolean(eff.allow_real))
      setMcpProfile(eff.mcp_profile || '')
    } catch (e: any) {
      setError(String(e?.message || e))
    }
    try {
      const src = await get<any>('/api/providers/ssh/sources')
      setSources(src?.sources ?? null)
    } catch {
      setSources(null)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => void load(),
    },
  ])

  const desiredPayload = useMemo(() => {
    const p: any = { provider }
    if (provider !== 'probe') p.allow_real = Boolean(allowReal)
    if (provider === 'mcp') p.mcp_profile = mcpProfile.trim() || null
    return p
  }, [allowReal, mcpProfile, provider])

  const exportEvidence = async () => {
    setError(null)
    setExportSha(null)
    setExportGeneratedAt(null)
    try {
      const resp: any = await get('/api/providers/ssh/export')
      const sha = String(resp?.sha256 || '')
      const gen = String(resp?.generated_at || '')
      const url = String(resp?.download_url || '')
      if (sha) setExportSha(sha)
      if (gen) setExportGeneratedAt(gen)
      if (url) window.open(url, '_blank', 'noopener,noreferrer')
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const startApply = async () => {
    applyConfirm.setError(null)
    setError(null)
    setDbNotAvailable(false)
    try {
      await applyConfirm.requestConfirm(async () => {
        await post('/api/providers/ssh', desiredPayload)
      })
    } catch (e: any) {
      const g = parseGateError(e)
      setError(String(g?.message || e?.message || t(K.page.sshProvider.applyFailed)))
    }
  }

  const confirmApply = async () => {
    await applyConfirm.confirm(async (token, reason) => {
      try {
        await post('/api/providers/ssh', {
          ...desiredPayload,
          confirm: true,
          confirm_token: token,
          reason,
        })
        await load()
      } catch (e: any) {
        const g = parseGateError(e)
        if (g?.gate === 'policy' && g.errorCode === 'SSH_PROVIDER_DB_NOT_AVAILABLE') {
          setDbNotAvailable(true)
        }
        throw e
      }
    })
  }

  const startDbInit = async () => {
    dbInitConfirm.setError(null)
    setError(null)
    try {
      await dbInitConfirm.requestConfirm(async () => {
        await post('/api/providers/ssh/db/init', {})
      })
    } catch (e: any) {
      const g = parseGateError(e)
      setError(String(g?.message || e?.message || t(K.page.sshProvider.dbInitFailed)))
    }
  }

  const confirmDbInit = async () => {
    await dbInitConfirm.confirm(async (token, reason) => {
      await post('/api/providers/ssh/db/init', { confirm: true, confirm_token: token, reason })
      setDbNotAvailable(false)
      await load()
    })
  }

  const whyNotReal = useMemo(() => {
    if (!effective) return null
    if (effective.provider === 'probe') return t(K.page.sshProvider.whyNotRealProbe)
    if (!effective.allow_real) return t(K.page.sshProvider.whyNotRealPolicy)
    return null
  }, [effective, t])

  return (
    <Box>
      {error ? (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      ) : null}

      <Card data-testid="ssh-provider-effective-card" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t(K.page.sshProvider.effectiveTitle)}
          </Typography>
          {effective ? (
            <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t(K.page.sshProvider.providerLabel)}
                </Typography>
                <Typography data-testid="ssh-provider-effective-provider" sx={{ fontFamily: 'monospace' }}>
                  {effective.provider}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t(K.page.sshProvider.sourceLabel)}
                </Typography>
                <Typography data-testid="ssh-provider-effective-source" sx={{ fontFamily: 'monospace' }}>
                  {effective.source}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  {t(K.page.sshProvider.allowRealFieldLabel)}
                </Typography>
                <Typography sx={{ fontFamily: 'monospace' }}>{String(Boolean(effective.allow_real))}</Typography>
              </Box>
              {effective.mcp_profile ? (
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    {t(K.page.sshProvider.mcpProfileFieldLabel)}
                  </Typography>
                  <Typography sx={{ fontFamily: 'monospace' }}>{effective.mcp_profile}</Typography>
                </Box>
              ) : null}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t(K.common.loading)}
            </Typography>
          )}
          {whyNotReal ? (
            <Alert severity="info" sx={{ mt: 2 }}>
              {whyNotReal}
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t(K.page.sshProvider.changeTitle)}
          </Typography>

          <Stack spacing={2}>
            <FormControl fullWidth size="small">
              <InputLabel id="ssh-provider-select-label">{t(K.page.sshProvider.providerLabel)}</InputLabel>
              <Select
                labelId="ssh-provider-select-label"
                data-testid="ssh-provider-select"
                value={provider}
                label={t(K.page.sshProvider.providerLabel)}
                onChange={(e) => setProvider(e.target.value as any)}
              >
                <MenuItem value="probe">{t(K.page.sshProvider.optionProbe)}</MenuItem>
                <MenuItem value="system">{t(K.page.sshProvider.optionSystem)}</MenuItem>
                <MenuItem value="mcp">{t(K.page.sshProvider.optionMcp)}</MenuItem>
              </Select>
            </FormControl>

            {provider !== 'probe' ? (
              <FormControlLabel
                control={
                  <Switch
                    data-testid="ssh-provider-allow-real"
                    checked={allowReal}
                    onChange={(e) => setAllowReal(e.target.checked)}
                  />
                }
                label={t(K.page.sshProvider.allowReal)}
              />
            ) : null}

            {provider === 'mcp' ? (
              <TextField
                data-testid="ssh-provider-mcp-profile"
                size="small"
                label={t(K.page.sshProvider.mcpProfile)}
                value={mcpProfile}
                onChange={(e) => setMcpProfile(e.target.value)}
              />
            ) : null}

            <Stack direction="row" spacing={1}>
              <Button data-testid="ssh-provider-apply" variant="contained" color="error" onClick={() => void startApply()}>
                {t(K.page.sshProvider.applyHighRisk)}
              </Button>
              <Button variant="outlined" onClick={() => navigate('/ssh/logs')}>
                {t(K.page.sshProvider.viewLogs)}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {/* Confirm dialog: reuse hook state but render stable testids */}
      {applyConfirm.open ? (
        <Card data-testid="ssh-provider-confirm-dialog" sx={{ mb: 2, border: '1px solid rgba(255,0,0,0.25)' }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.confirmTitle)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.confirmBody)}
            </Typography>
            <TextField
              data-testid="ssh-provider-confirm-reason-field"
              size="small"
              fullWidth
              label={t(K.page.sshProvider.reason)}
              value={applyConfirm.reason}
              onChange={(e) => applyConfirm.setReason(e.target.value)}
              inputProps={{ 'data-testid': 'ssh-provider-confirm-reason' }}
              sx={{ mb: 1 }}
            />
            {applyConfirm.error ? (
              <Typography variant="body2" color="error" sx={{ mb: 1 }}>
                {applyConfirm.error}
              </Typography>
            ) : null}
            <Stack direction="row" spacing={1}>
              <Button data-testid="ssh-provider-confirm" variant="contained" color="error" onClick={() => void confirmApply()}>
                {t(K.page.sshProvider.confirmApply)}
              </Button>
              <Button data-testid="ssh-provider-cancel" variant="outlined" onClick={() => applyConfirm.cancel()}>
                {t(K.common.cancel)}
              </Button>
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t(K.page.sshProvider.evidenceTitle)}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
            <Button data-testid="ssh-provider-export-button" variant="outlined" onClick={() => void exportEvidence()}>
              {t(K.page.sshProvider.exportJson)}
            </Button>
            {exportSha ? (
              <Typography data-testid="ssh-provider-export-sha256" variant="caption" sx={{ fontFamily: 'monospace' }}>
                {t(K.page.sshProvider.shaPrefix)} {exportSha.slice(0, 16)}...
              </Typography>
            ) : null}
            {exportGeneratedAt ? (
              <Typography data-testid="ssh-provider-export-generated-at" variant="caption" sx={{ fontFamily: 'monospace' }}>
                {t(K.page.sshProvider.atPrefix)} {exportGeneratedAt}
              </Typography>
            ) : null}
          </Stack>
        </CardContent>
      </Card>

      {dbNotAvailable ? (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.advancedTitle)}
            </Typography>
            <Alert severity="warning" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.dbNotAvailable)}
            </Alert>
            <Button data-testid="ssh-provider-db-init" variant="contained" color="error" onClick={() => void startDbInit()}>
              {t(K.page.sshProvider.initDbHighRisk)}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {dbInitConfirm.open ? (
        <Card data-testid="ssh-provider-db-init-confirm-dialog" sx={{ mb: 2, border: '1px solid rgba(255,0,0,0.25)' }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.initDbTitle)}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t(K.page.sshProvider.initDbBody)}
            </Typography>
            <TextField
              data-testid="ssh-provider-db-init-reason"
              size="small"
              fullWidth
              label={t(K.page.sshProvider.reason)}
              value={dbInitConfirm.reason}
              onChange={(e) => dbInitConfirm.setReason(e.target.value)}
              sx={{ mb: 1 }}
            />
            {dbInitConfirm.error ? (
              <Typography variant="body2" color="error" sx={{ mb: 1 }}>
                {dbInitConfirm.error}
              </Typography>
            ) : null}
            <Stack direction="row" spacing={1}>
              <Button
                data-testid="ssh-provider-db-init-confirm"
                variant="contained"
                color="error"
                onClick={() => void confirmDbInit()}
              >
                {t(K.page.sshProvider.confirmInitDb)}
              </Button>
              <Button variant="outlined" onClick={() => dbInitConfirm.cancel()}>
                {t(K.common.cancel)}
              </Button>
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      <Divider sx={{ my: 2 }} />

      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t(K.page.sshProvider.sourcesTitle)}
          </Typography>
          <Box
            data-testid="ssh-provider-sources"
            sx={{
              bgcolor: 'rgba(0,0,0,0.06)',
              borderRadius: 2,
              p: 1.5,
              overflow: 'auto',
              maxHeight: 480,
            }}
          >
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {sources ? JSON.stringify(sources, null, 2) : t(K.page.sshProvider.sourcesUnavailable)}
            </pre>
          </Box>
        </CardContent>
      </Card>
    </Box>
  )
}
