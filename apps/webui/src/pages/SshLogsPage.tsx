import { Box, Button, Grid, TextField, Typography } from '@mui/material'
import { usePageHeader, usePageActions, EmptyState } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { useEffect, useState } from 'react'
import { get } from '@/platform/http'

export default function SshLogsPage() {
  const { t } = useTextTranslation()
  const [q, setQ] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)

  usePageHeader({
    title: t(K.page.sshLogs.title),
    subtitle: t(K.page.sshLogs.subtitle),
  })

  const load = async () => {
    setError(null)
    try {
      const resp: any = await get(
        `/api/logs?types=shell,ssh,sftp&limit=100&offset=0${
          q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''
        }`,
      )
      setItems(Array.isArray(resp?.items) ? resp.items : [])
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const exportJson = async () => {
    setError(null)
    try {
      const resp: any = await get(
        `/api/logs/export?types=shell,ssh,sftp${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''}`,
      )
      const url = String(resp?.download_url || '')
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer')
      } else {
        setError(t(K.page.sshLogs.exportMissingUrl))
      }
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
        void load()
      },
    },
    {
      key: 'export',
      label: t(K.page.sshLogs.exportJson),
      variant: 'outlined',
      onClick: () => {
        void exportJson()
      },
    },
  ])

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <Box>
      <Grid container spacing={1} sx={{ mb: 2 }} alignItems="center">
        <Grid item xs={12} md>
          <TextField
            value={q}
            onChange={(e) => setQ(e.target.value)}
            size="small"
            fullWidth
            placeholder={t(K.page.sshLogs.filterPlaceholder)}
          />
        </Grid>
        <Grid item xs={12} md="auto">
          <Button variant="outlined" onClick={() => void load()} sx={{ minWidth: 140, whiteSpace: 'nowrap' }}>
            {t(K.common.refresh)}
          </Button>
        </Grid>
        <Grid item xs={12} md="auto">
          <Button data-testid="logs-export-button" variant="outlined" onClick={() => void exportJson()} sx={{ minWidth: 160, whiteSpace: 'nowrap' }}>
            {t(K.page.sshLogs.exportJson)}
          </Button>
        </Grid>
      </Grid>

      {error && (
        <Typography variant="body2" color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      {items.length === 0 ? (
        <EmptyState title={t(K.page.sshLogs.title)} description={t(K.page.sshLogs.subtitle)} />
      ) : (
        <Box
          sx={{
            bgcolor: 'rgba(0,0,0,0.06)',
            borderRadius: 2,
            p: 1.5,
            overflow: 'auto',
            maxHeight: 640,
          }}
        >
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {items
              .map((it) => `${it.ts} ${it.type} ${it.capability_id} ${it.summary}\n`)
              .join('')}
          </pre>
        </Box>
      )}
    </Box>
  )
}
