import { useEffect, useMemo, useState } from 'react'
import {
  Box,
  Button,
  Grid,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  TextField,
  Typography,
} from '@mui/material'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { get } from '@platform/http/httpClient'
import { usePageHeader } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'

type SourceRef = {
  name: string
  type: string
  url?: string
  retrieved_at: string
}

type EvidenceItem = {
  evidence_id: string
  kind: string
  query: string
  type: string
  source: SourceRef
  captured_at: string
  content_snippet: string
  raw_ref?: string
}

type ExtractionRecord = {
  extraction_id: string
  evidence_id: string
  kind: string
  schema_version: string
  status: string
  extracted: Record<string, unknown>
  missing_fields: string[]
  notes: string
  created_at: string
}

type VerificationRecord = {
  verification_id: string
  evidence_id: string
  kind: string
  status: string
  confidence: string
  confidence_reason: string
  checks: Record<string, unknown>
  created_at: string
}

type CompatResponse<T> = {
  ok: boolean
  data: T
}

export default function ExternalFactsReplayPage() {
  const { t } = useTextTranslation()
  usePageHeader({
    title: t(K.page.externalFactsReplay.title),
    subtitle: t(K.page.externalFactsReplay.subtitle),
  })

  const [params, setParams] = useSearchParams()
  const initialEvidenceId = params.get('evidence_id') || ''
  const [evidenceIdInput, setEvidenceIdInput] = useState(initialEvidenceId)
  const [evidence, setEvidence] = useState<EvidenceItem | null>(null)
  const [extractions, setExtractions] = useState<ExtractionRecord[]>([])
  const [verifications, setVerifications] = useState<VerificationRecord[]>([])
  const [recentEvidence, setRecentEvidence] = useState<EvidenceItem[]>([])
  const [error, setError] = useState('')

  const evidenceId = useMemo(() => params.get('evidence_id') || '', [params])

  useEffect(() => {
    void loadRecent()
  }, [])

  useEffect(() => {
    if (!evidenceId) return
    void loadReplay(evidenceId)
  }, [evidenceId])

  async function loadRecent() {
    try {
      const recent = await get<CompatResponse<EvidenceItem[]>>('/api/compat/external-facts/recent', {
        params: { limit: 20 },
      })
      setRecentEvidence(recent.data || [])
    } catch {
      setRecentEvidence([])
    }
  }

  async function loadReplay(targetEvidenceId: string) {
    setError('')
    try {
      const [eRes, xRes, vRes] = await Promise.all([
        get<CompatResponse<EvidenceItem>>(`/api/compat/external-facts/evidence/${encodeURIComponent(targetEvidenceId)}`),
        get<CompatResponse<ExtractionRecord[]>>(`/api/compat/external-facts/evidence/${encodeURIComponent(targetEvidenceId)}/extractions`),
        get<CompatResponse<VerificationRecord[]>>(`/api/compat/external-facts/evidence/${encodeURIComponent(targetEvidenceId)}/verifications`),
      ])
      setEvidence(eRes.data)
      setExtractions(xRes.data || [])
      setVerifications(vRes.data || [])
    } catch (err: unknown) {
      setEvidence(null)
      setExtractions([])
      setVerifications([])
      setError(err instanceof Error ? err.message : t(K.page.externalFactsReplay.errorLoad))
    }
  }

  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={1.5} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} md>
          <TextField
            label={t(K.page.externalFactsReplay.evidenceId)}
            value={evidenceIdInput}
            onChange={(e) => setEvidenceIdInput(e.target.value)}
            fullWidth
            size="small"
          />
        </Grid>
        <Grid item xs={12} md="auto">
          <Button
            variant="contained"
            onClick={() => setParams({ evidence_id: evidenceIdInput.trim() })}
            disabled={!evidenceIdInput.trim()}
            sx={{ minWidth: 140, whiteSpace: 'nowrap' }}
          >
            {t(K.page.externalFactsReplay.load)}
          </Button>
        </Grid>

        <Grid item xs={12}>
          <Grid container spacing={1.5} alignItems="center">
            <Grid item xs={12} md="auto">
              <Button variant="outlined" component={RouterLink} to="/external-facts/policy" sx={{ minWidth: 180, whiteSpace: 'nowrap' }}>
                {t(K.nav.externalFactsPolicy)}
              </Button>
            </Grid>
            <Grid item xs={12} md="auto">
              <Button variant="outlined" component={RouterLink} to="/facts/schema" sx={{ minWidth: 180, whiteSpace: 'nowrap' }}>
                {t(K.nav.factsSchema)}
              </Button>
            </Grid>
            <Grid item xs={12} md="auto">
              <Button variant="outlined" component={RouterLink} to="/external-facts/providers" sx={{ minWidth: 200, whiteSpace: 'nowrap' }}>
                {t(K.nav.externalFactsProviders)}
              </Button>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      {error && (
        <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>
      )}

      <Paper sx={{ p: 2, mb: 2 }} data-testid="replay-recent-list">
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t(K.page.externalFactsReplay.sectionRecent)}
        </Typography>
        {recentEvidence.length === 0 && (
          <Typography variant="body2">{t(K.page.externalFactsReplay.noRecent)}</Typography>
        )}
        {recentEvidence.length > 0 && (
          <List dense disablePadding>
            {recentEvidence.map((item) => (
              <ListItemButton
                key={item.evidence_id}
                onClick={() => {
                  setEvidenceIdInput(item.evidence_id)
                  setParams({ evidence_id: item.evidence_id })
                }}
              >
                <ListItemText
                  primary={`${item.kind.toUpperCase()} · ${item.source?.name || 'unknown'}`}
                  secondary={`${item.captured_at} · ${item.query}`}
                />
              </ListItemButton>
            ))}
          </List>
        )}
      </Paper>

      {evidence && (
        <Paper sx={{ p: 2, mb: 2 }} data-testid="replay-evidence-card">
          <Typography variant="h6">{t(K.page.externalFactsReplay.sectionEvidence)}</Typography>
          <Typography variant="body2">
            {t(K.page.externalFactsReplay.source)}: {evidence.source?.name} ({evidence.source?.type})
          </Typography>
          <Typography variant="body2">
            {t(K.page.externalFactsReplay.capturedAt)}: {evidence.captured_at}
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>{evidence.content_snippet}</Typography>
        </Paper>
      )}

      <Paper sx={{ p: 2, mb: 2 }} data-testid="replay-extractions">
        <Typography variant="h6" sx={{ mb: 1 }}>{t(K.page.externalFactsReplay.sectionExtractions)}</Typography>
        {extractions.length === 0 && (
          <Typography variant="body2">{t(K.page.externalFactsReplay.noExtractions)}</Typography>
        )}
        {extractions.map((record) => (
          <Box key={record.extraction_id} sx={{ mb: 1.5 }}>
            <Typography variant="body2">[{record.status}] {record.created_at}</Typography>
            <Typography variant="caption">
              {t(K.page.externalFactsReplay.missingFields)}: {record.missing_fields.join(', ') || t(K.common.unknown)}
            </Typography>
            <pre style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.extracted, null, 2)}</pre>
          </Box>
        ))}
      </Paper>

      <Paper sx={{ p: 2 }} data-testid="replay-verifications">
        <Typography variant="h6" sx={{ mb: 1 }}>{t(K.page.externalFactsReplay.sectionVerifications)}</Typography>
        {verifications.length === 0 && (
          <Typography variant="body2">{t(K.page.externalFactsReplay.noVerifications)}</Typography>
        )}
        {verifications.map((record) => (
          <Box key={record.verification_id} sx={{ mb: 1.5 }}>
            <Typography variant="body2">
              [{record.status}] {t(K.page.externalFactsReplay.confidence)}={record.confidence}
            </Typography>
            <Typography variant="caption">{record.confidence_reason}</Typography>
            <pre style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap' }}>{JSON.stringify(record.checks, null, 2)}</pre>
          </Box>
        ))}
      </Paper>
    </Box>
  )
}
