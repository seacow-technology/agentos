import { useEffect, useMemo, useState } from 'react'
import { Box, Button, Divider, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { useTextTranslation } from '@/ui/text'
// Force TS source import: there's also a legacy CJS build output next to it (`communicationos.service.js`),
// which breaks ESM named exports resolution in Vite/Rollup if picked up accidentally.
import { communicationosService } from '@/services/communicationos.service.ts'
import { post } from '@/platform/http'
import { toast } from '@/ui/feedback'

type ProfilesResp = {
  ok?: boolean
  profiles?: string[]
  default_profile?: string
  reason?: string
  source?: string
}

export default function AwsOpsPage() {
  const { t } = useTextTranslation()
  const navigate = useNavigate()

  const [loading, setLoading] = useState(false)
  const [awsProfilesOk, setAwsProfilesOk] = useState<boolean | null>(null)
  const [profiles, setProfiles] = useState<string[]>([])
  const [defaultProfile, setDefaultProfile] = useState('default')
  const [selectedProfile, setSelectedProfile] = useState('default')
  const [region, setRegion] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [detail, setDetail] = useState<{ reason?: string; source?: string } | null>(null)

  const regionTrim = useMemo(() => region.trim(), [region])
  const actionsDisabledReason = useMemo(() => {
    if (loading) return t('common.loading')
    if (awsProfilesOk === false) return status || t('page.awsOps.awsUnavailable')
    if (!regionTrim) return t('page.awsOps.regionRequired')
    return null
  }, [awsProfilesOk, loading, regionTrim, status, t])
  const actionsDisabled = Boolean(actionsDisabledReason)

  const refreshProfiles = async () => {
    setLoading(true)
    setStatus(null)
    try {
      const res = (await communicationosService.listLocalAwsProfiles()) as ProfilesResp
      setAwsProfilesOk(res?.ok !== false)
      const nextProfiles = Array.isArray(res?.profiles) ? res.profiles : []
      const dp = String(res?.default_profile || 'default')
      setProfiles(nextProfiles)
      setDefaultProfile(dp)
      setSelectedProfile((prev) => {
        if (prev && nextProfiles.includes(prev)) return prev
        return nextProfiles.includes(dp) ? dp : (nextProfiles[0] || dp)
      })
      setDetail({ reason: res?.reason, source: res?.source })
      if (res?.ok === false) {
        setStatus(res?.reason ? String(res.reason) : 'AWS profiles not available')
      }
    } catch (e: any) {
      setAwsProfilesOk(false)
      setStatus(String(e?.message || e))
      setProfiles([])
      setDetail(null)
    } finally {
      setLoading(false)
    }
  }

  const createChatWithPrompt = async (prompt: string) => {
    if (awsProfilesOk === false) {
      toast.error(status || t('page.awsOps.awsUnavailable'))
      return
    }
    if (!regionTrim) {
      toast.error(t('page.awsOps.regionRequired'))
      return
    }
    const p = (selectedProfile || defaultProfile || 'default').trim() || 'default'
    const fullPrompt = [
      `AWS ops context: profile=${p}, region=${regionTrim}.`,
      'Be explicit about what you will do. Prefer read-only inspection first.',
      prompt.trim(),
    ].filter(Boolean).join('\n')

    try {
      const sess: any = await post('/api/sessions', {
        title: `AWS Ops (${p}/${regionTrim})`,
        metadata: { preset_id: 'free', tags: ['aws_ops'], aws: { profile: p, region: regionTrim } },
      })
      const sessionId = String(sess?.session_id || sess?.id || '')
      if (!sessionId) throw new Error('session_id missing')

      await post(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
        role: 'user',
        content: fullPrompt,
      })

      navigate('/chat', { state: { sessionId } })
    } catch (e: any) {
      toast.error(String(e?.message || e))
    }
  }

  usePageHeader({
    title: t('page.awsOps.title'),
    subtitle: t('page.awsOps.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => void refreshProfiles(),
    },
    {
      key: 'openChat',
      label: t('page.awsOps.openChat'),
      variant: 'outlined',
      onClick: () => navigate('/chat'),
    },
  ])

  useEffect(() => {
    void refreshProfiles()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Box>
      <Stack spacing={2}>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
            {t('page.awsOps.contextTitle')}
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} alignItems="stretch">
            <TextField
              select
              label={t('page.awsOps.profile')}
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(String(e.target.value || 'default'))}
              size="small"
              sx={{ minWidth: { xs: '100%', md: 360 } }}
              helperText={detail?.source ? `${t('page.awsOps.source')}: ${detail.source}` : ' '}
              disabled={loading}
            >
              {(profiles.length ? profiles : [defaultProfile || 'default']).map((p) => (
                <MenuItem key={p} value={p}>
                  {p}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label={t('page.awsOps.region')}
              value={region}
              onChange={(e) => setRegion(String(e.target.value || ''))}
              size="small"
              placeholder="us-east-1"
              helperText={t('page.awsOps.regionHelp')}
              disabled={loading}
            />
          </Stack>
          {status ? (
            <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
              {status}
            </Typography>
          ) : null}
        </Box>

        <Divider />

        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
            {t('page.awsOps.quickActions')}
          </Typography>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} flexWrap="wrap">
            <Button
              variant="contained"
              disabled={actionsDisabled}
              onClick={() => void createChatWithPrompt('List EC2 instances (id, name tag, state).')}
            >
              {t('page.awsOps.action.ec2List')}
            </Button>
            <Button
              variant="outlined"
              disabled={actionsDisabled}
              onClick={() => void createChatWithPrompt('List S3 buckets and note which are public-facing risks.')}
            >
              {t('page.awsOps.action.s3List')}
            </Button>
            <Button
              variant="outlined"
              disabled={actionsDisabled}
              onClick={() => void createChatWithPrompt('Summarize top cost drivers for the last 7 days. Include CloudWatch/Cost Explorer commands.')}
            >
              {t('page.awsOps.action.cost7d')}
            </Button>
            <Button
              variant="outlined"
              disabled={actionsDisabled}
              onClick={() => void createChatWithPrompt('Explain my AWS bill like I am an engineer: top services, what to check, and immediate safe savings.')}
            >
              {t('page.awsOps.action.billExplain')}
            </Button>
          </Stack>
          {actionsDisabledReason ? (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {actionsDisabledReason}
            </Typography>
          ) : null}
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
            {t('page.awsOps.note')}
          </Typography>
        </Box>
      </Stack>
    </Box>
  )
}
