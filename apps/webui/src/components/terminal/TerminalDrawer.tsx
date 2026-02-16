import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  IconButton,
  TextField,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material'
import { CloseIcon, RefreshIcon } from '@/ui/icons'
import { K, useTextTranslation } from '@/ui/text'
import { useTerminalSession } from './useTerminalSession'
import { post } from '@/platform/http'

export interface TerminalDrawerProps {
  open: boolean
  onClose: () => void
}

export function TerminalDrawer(props: TerminalDrawerProps) {
  const { open, onClose } = props
  const { t } = useTextTranslation()
  const { sessionId, connecting, error, events, exec, pullEvents, close } = useTerminalSession(open)

  const [command, setCommand] = useState('')
  const outputRef = useRef<HTMLPreElement | null>(null)
  const [viewMode, setViewMode] = useState<'raw' | 'optimized'>('raw')
  const [opt, setOpt] = useState<{
    summary_text?: string
    reduction_percent?: number
    raw_tokens?: number
    optimized_tokens?: number
    v2?: {
      raw_tokens: number
      base_pack_tokens: number
      expansion_tokens: number
      total_injected: number
      budget_total: number
      saved_tokens: number
      saved_percent: number
      ruleset_version: string
      signatures_learned: number
      top_dropped: Array<{ id: string; signature: string; drop_reason: string }>
      dropped_summary: any
      dropped_items: Array<{ id: string; reason: string; estimated_tokens: number; value_score: number; signature: string }>
    }
  } | null>(null)
  const [optLoading, setOptLoading] = useState(false)
  const [droppedOpen, setDroppedOpen] = useState(false)

  const renderedOutput = useMemo(() => {
    const lines: string[] = []
    for (const ev of events) {
      const data = ev.data || {}
      if (ev.type === 'stdout' || ev.type === 'stderr') {
        const text = typeof (data as any).text === 'string' ? (data as any).text : JSON.stringify(data)
        lines.push(text)
      } else {
        const text = typeof (data as any).message === 'string' ? (data as any).message : JSON.stringify(data)
        lines.push(`[${ev.type}] ${text}`)
      }
    }
    return lines.join('')
  }, [events])

  const refreshOptimized = useCallback(async () => {
    const raw = renderedOutput || ''
    if (!raw.trim()) {
      setOpt(null)
      return
    }
    setOptLoading(true)
    try {
      const [v1, v2] = await Promise.all([
        post<any>('/api/context_optimizer/cli', { text: raw, model: 'gpt-4o' }),
        post<any>('/api/context_optimizer/v2/cli_pack', {
          text: raw,
          model: 'gpt-4o',
          token_budget_total: 4000,
          reserve_ratio: 0.2,
          fixed_overhead: 1200,
        }),
      ])
      const s = v2?.summary || {}
      const dropped = Array.isArray(v2?.selection?.dropped_items) ? v2.selection.dropped_items : []
      const droppedCompact = Array.isArray(v2?.selection?.dropped_items_compact) ? v2.selection.dropped_items_compact : []
      setOpt({
        summary_text: String(v1?.summary_text || ''),
        reduction_percent: Number(v1?.reduction_percent || 0),
        raw_tokens: Number(v1?.raw_tokens || 0),
        optimized_tokens: Number(v1?.optimized_tokens || 0),
        v2: {
          raw_tokens: Number(s['Raw Context'] || 0),
          base_pack_tokens: Number(s['Base Pack Used'] || 0),
          expansion_tokens: Number(s['Expansion Used'] || 0),
          total_injected: Number(s['Total Injected'] || 0),
          budget_total: Number(s['Budget Total'] || 4000),
          saved_tokens: Number(s['Saved Tokens'] || 0),
          saved_percent: Number(s['Saved Percent'] || 0),
          ruleset_version: String(s['Ruleset Version'] || 'v2.0'),
          signatures_learned: Number(s['Signatures Learned'] || 0),
          top_dropped: dropped.slice(0, 3).map((it: any) => ({
            id: String(it?.id || ''),
            signature: String(it?.signature || ''),
            drop_reason: String(it?.drop_reason || ''),
          })),
          dropped_summary: s['Dropped Summary'] || null,
          dropped_items: droppedCompact.map((it: any) => ({
            id: String(it?.id || ''),
            reason: String(it?.reason || ''),
            estimated_tokens: Number(it?.estimated_tokens || 0),
            value_score: Number(it?.value_score || 0),
            signature: String(it?.signature || ''),
          })),
        },
      })
    } finally {
      setOptLoading(false)
    }
  }, [renderedOutput])

  useEffect(() => {
    if (!open) return
    // Auto-scroll to bottom on new output.
    const el = outputRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [open, renderedOutput])

  useEffect(() => {
    if (!open) return
    if (viewMode !== 'optimized') return
    void refreshOptimized()
  }, [open, viewMode, refreshOptimized])

  const handleRun = async () => {
    const cmd = command.trim()
    if (!cmd) return
    setCommand('')
    await exec(cmd)
  }

  const handleCloseSession = async () => {
    await close()
    onClose()
  }

  return (
    <Drawer
      anchor="bottom"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          height: { xs: '75vh', md: '60vh' },
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
        },
      }}
      >
      <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
            {t(K.appBar.localTerminalTitle)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {sessionId ? `session_id: ${sessionId}` : connecting ? t(K.common.loading) : ''}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <ToggleButtonGroup
            size="small"
            value={viewMode}
            exclusive
            onChange={(_, next) => {
              if (!next) return
              setViewMode(next)
            }}
          >
            <ToggleButton value="raw">Raw</ToggleButton>
            <ToggleButton value="optimized">Optimized</ToggleButton>
          </ToggleButtonGroup>
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon fontSize="small" />}
            onClick={() => {
              pullEvents()
              if (viewMode === 'optimized') void refreshOptimized()
            }}
          >
            {t(K.common.refresh)}
          </Button>
          <Button size="small" variant="outlined" color="error" onClick={handleCloseSession}>
            {t(K.common.close)}
          </Button>
          <IconButton onClick={onClose} aria-label={t(K.common.close)}>
            <CloseIcon />
          </IconButton>
        </Box>
      </Box>

      <Divider />

      <Box sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', gap: 1 }}>
        <TextField
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleRun()
            }
          }}
          placeholder="pwd && ls"
          size="small"
          fullWidth
          inputProps={{ 'data-testid': 'local-terminal-input' }}
        />

        {error && (
          <Typography variant="caption" color="error">
            {String(error)}
          </Typography>
        )}

        {viewMode === 'optimized' && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
            {opt?.v2 ? (
              <>
                <Typography variant="caption" color="text.secondary">
                  Token Optimization Summary
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Raw Context: {opt.v2.raw_tokens}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Base Pack Used: {opt.v2.base_pack_tokens}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Expansion Used: {opt.v2.expansion_tokens}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Total Injected: {opt.v2.total_injected} / {opt.v2.budget_total}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Saved: {opt.v2.saved_tokens} tokens ({Number(opt.v2.saved_percent).toFixed(1)}%)
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Ruleset Version: {opt.v2.ruleset_version}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Signatures Learned: +{opt.v2.signatures_learned} (pending review)
                </Typography>
                {opt.v2.dropped_summary && (
                  <Typography variant="caption" color="text.secondary">
                    Dropped: {Number(opt.v2.dropped_summary.lines_removed || 0).toLocaleString()} lines removed, {Number(opt.v2.dropped_summary.duplicate_lines_removed || 0).toLocaleString()} duplicate lines removed, {Number(opt.v2.dropped_summary.dropped_facts_over_budget || 0).toLocaleString()} facts over budget
                  </Typography>
                )}
                {opt.v2.top_dropped.length > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    Top Dropped (over budget): {opt.v2.top_dropped.map((x) => x.signature || x.id).join(' | ')}
                  </Typography>
                )}
                <Button size="small" variant="outlined" onClick={() => setDroppedOpen(true)}>
                  Show Dropped Items
                </Button>
              </>
            ) : (
              <>
                <Typography variant="caption" color="text.secondary">
                  Token Optimization: {opt ? `${Number(opt.reduction_percent || 0).toFixed(1)}%` : optLoading ? '...' : '-'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Raw: {opt ? opt.raw_tokens : '-'} tokens
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Optimized: {opt ? opt.optimized_tokens : '-'} tokens
                </Typography>
              </>
            )}
            <Button size="small" variant="outlined" onClick={() => void refreshOptimized()} disabled={optLoading}>
              Recompute
            </Button>
          </Box>
        )}

        <Box
          sx={{
            flex: 1,
            bgcolor: 'rgba(0,0,0,0.06)',
            borderRadius: 2,
            p: 1.5,
            overflow: 'auto',
          }}
        >
          <pre
            ref={outputRef}
            data-testid="local-terminal-output"
            style={{
              margin: 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            {viewMode === 'optimized' ? (opt?.summary_text || (optLoading ? 'Optimizing...\n' : ' ')) : (renderedOutput || ' ')}
          </pre>
        </Box>
      </Box>

      <Dialog open={droppedOpen} onClose={() => setDroppedOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Dropped Items</DialogTitle>
        <DialogContent>
          <Box component="pre" sx={{ m: 0, fontSize: 12, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>
            {opt?.v2 ? JSON.stringify({ dropped_summary: opt.v2.dropped_summary, dropped_items: opt.v2.dropped_items }, null, 2) : 'No v2 data.'}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDroppedOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Drawer>
  )
}
