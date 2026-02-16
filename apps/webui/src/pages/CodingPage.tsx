import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { get, post } from '@/platform/http'
import { usePageHeader } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'

type DemoStage = 'discussion' | 'planning' | 'worker' | 'test' | 'complete'

type SessionItem = {
  session_id: string
  title: string
}

type PlanTask = {
  id: string
  variant: string
  title: string
  owner: string
  acceptance: string[]
}

type PlanState = {
  plan_id?: string
  run_id?: string
  roles?: Array<{ id: string; label: string }>
  tasks?: PlanTask[]
  acceptance?: string[]
}

type RequirementsState = {
  goal: string
  variants: string[]
  framework?: string
  provider?: string
  contract_id?: string
  page_type?: string
  delivery_variant?: string
  constraints: string[]
  acceptance: string[]
}

type DemoState = {
  session_id: string
  stage: DemoStage
  requirements: RequirementsState
  plan: PlanState
  spec_frozen: boolean
  plan_id?: string | null
  run_id?: string | null
  last_test_status?: string | null
}

type StreamEnvelope = {
  run_id: string
  task_id?: string | null
  role?: string | null
  demo_stage?: string | null
  plan_id?: string | null
  session_id: string
  seq: number
  ts: string
  type: string
  payload: Record<string, any>
}

type ChecklistItem = {
  id: string
  label: string
  status: 'pending' | 'done'
}

type AskReply = {
  summary: string
  blockers: string[]
  next_steps: string[]
  recent_files: Array<string | { path: string; role?: string; task_id?: string; op?: string }>
  percent_by_role: Record<string, number>
  task_status: Record<string, string>
}

type PersistedCursor = {
  run_id: string
  last_seq: number
}

const CURSOR_KEY = 'coding.stream.cursor.v2'
const SANDBOX_MODE_KEY = 'coding.preview.sandbox.mode.v1'
const STAGES: DemoStage[] = ['discussion', 'planning', 'worker', 'test', 'complete']
type SandboxMode = 'demo' | 'strict'

function loadCursorMap(): Record<string, PersistedCursor> {
  try {
    const raw = localStorage.getItem(CURSOR_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function saveCursorMap(map: Record<string, PersistedCursor>): void {
  localStorage.setItem(CURSOR_KEY, JSON.stringify(map))
}

function loadSandboxMode(): SandboxMode {
  try {
    const raw = localStorage.getItem(SANDBOX_MODE_KEY)
    return raw === 'strict' ? 'strict' : 'demo'
  } catch {
    return 'demo'
  }
}

function defaultRequirements(prompt: string): RequirementsState {
  return {
    goal: prompt,
    variants: ['apple_iphone17pro'],
    framework: 'react',
    provider: 'mui',
    contract_id: 'brand_soft',
    page_type: 'landing',
    delivery_variant: 'deliver_page_spec',
    constraints: ['no_chat_or_work_page_modifications'],
    acceptance: ['preview reload works', 'replay survives refresh', 'test must pass before complete'],
  }
}

function formatEventLine(event: StreamEnvelope): string {
  if (event.type === 'log.append') return `${String(event.payload?.text || '')}\n`
  if (event.type === 'message.delta') return String(event.payload?.delta || '')
  if (event.type === 'message.error') return `${String(event.payload?.message || 'error')}\n`
  if (event.type === 'message.end') return `${String(event.payload?.content || '')}\n`
  return `${event.type}\n`
}

export default function CodingPage() {
  const { t } = useTextTranslation()

  usePageHeader({
    title: t(K.page.coding.title),
    subtitle: t(K.page.coding.subtitle),
  })

  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [sessionId, setSessionId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [longMode, setLongMode] = useState(false)
  const [forceTestFail, setForceTestFail] = useState(false)
  const [selectedVariant, setSelectedVariant] = useState('apple_iphone17pro')
  const [connected, setConnected] = useState(false)
  const [currentRunId, setCurrentRunId] = useState('')
  const [currentTaskId, setCurrentTaskId] = useState('')
  const [currentStep, setCurrentStep] = useState('idle')
  const [progress, setProgress] = useState(0)
  const [progressLabel, setProgressLabel] = useState('')
  const [checklist, setChecklist] = useState<ChecklistItem[]>([])
  const [timeline, setTimeline] = useState<StreamEnvelope[]>([])
  const [logs, setLogs] = useState<string[]>([])
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewId, setPreviewId] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [askScope, setAskScope] = useState<'all' | 'role' | 'task' | 'file'>('all')
  const [askKey, setAskKey] = useState('')
  const [askReplies, setAskReplies] = useState<AskReply[]>([])
  const [requirements, setRequirements] = useState<RequirementsState>(defaultRequirements(''))
  const [plan, setPlan] = useState<PlanState>({})
  const [specFrozen, setSpecFrozen] = useState(false)
  const [demoStage, setDemoStage] = useState<DemoStage>('discussion')
  const [completeReady, setCompleteReady] = useState(false)
  const [fullscreenOn, setFullscreenOn] = useState(false)
  const [wsStatus, setWsStatus] = useState<'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error'>('idle')
  const [wsRetryCount, setWsRetryCount] = useState(0)
  const [wsLastClose, setWsLastClose] = useState('')
  const [sandboxMode, setSandboxMode] = useState<SandboxMode>(() => loadSandboxMode())

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reloadTimerRef = useRef<number | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const connectTokenRef = useRef(0)
  const intentionalCloseRef = useRef(false)
  const sessionIdRef = useRef('')
  const previewUrlRef = useRef('')
  const tRef = useRef(t)
  const timelineRef = useRef<StreamEnvelope[]>([])
  const previewPaneRef = useRef<HTMLDivElement | null>(null)

  const lastSeq = useMemo(() => timeline[timeline.length - 1]?.seq || 0, [timeline])

  useEffect(() => {
    timelineRef.current = timeline
  }, [timeline])

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  useEffect(() => {
    previewUrlRef.current = previewUrl
  }, [previewUrl])

  useEffect(() => {
    tRef.current = t
  }, [t])

  const persistCursor = useCallback((targetSessionId: string, nextRunId: string, nextSeq: number) => {
    if (!targetSessionId || !nextRunId) return
    const map = loadCursorMap()
    map[targetSessionId] = { run_id: nextRunId, last_seq: Math.max(0, nextSeq) }
    saveCursorMap(map)
  }, [])

  const throttlePreviewReload = useCallback((nextUrl?: string) => {
    if (reloadTimerRef.current) {
      window.clearTimeout(reloadTimerRef.current)
    }
    reloadTimerRef.current = window.setTimeout(() => {
      const base = nextUrl || previewUrlRef.current
      if (!base) return
      const separator = base.includes('?') ? '&' : '?'
      setPreviewUrl(`${base}${separator}reload=${Date.now()}`)
    }, 500)
  }, [])

  const applyDemoState = useCallback((state: Partial<DemoState>) => {
    const stage = String(state.stage || 'discussion') as DemoStage
    setDemoStage(stage)
    setSpecFrozen(Boolean(state.spec_frozen))
    if (state.requirements && typeof state.requirements === 'object') {
      setRequirements({
        goal: String(state.requirements.goal || ''),
        variants: Array.isArray(state.requirements.variants) ? state.requirements.variants.map((v) => String(v)) : [],
        framework: String((state.requirements as any).framework || 'react'),
        provider: String((state.requirements as any).provider || 'mui'),
        contract_id: String((state.requirements as any).contract_id || 'brand_soft'),
        page_type: String((state.requirements as any).page_type || 'landing'),
        delivery_variant: String((state.requirements as any).delivery_variant || 'deliver_page_spec'),
        constraints: Array.isArray(state.requirements.constraints) ? state.requirements.constraints.map((v) => String(v)) : [],
        acceptance: Array.isArray(state.requirements.acceptance) ? state.requirements.acceptance.map((v) => String(v)) : [],
      })
    }
    if (state.plan && typeof state.plan === 'object') {
      setPlan(state.plan as PlanState)
    }
    if (Array.isArray(state.requirements?.variants) && state.requirements.variants.length > 0) {
      setSelectedVariant(String(state.requirements.variants[0]))
    }
    if (state.run_id) {
      setCurrentRunId(String(state.run_id))
    }
    setCompleteReady(stage === 'complete' && state.last_test_status === 'passed')
  }, [])

  const consumeEvent = useCallback((event: StreamEnvelope) => {
    if (!event || typeof event !== 'object') return

    if (event.type === 'demo.state') {
      applyDemoState(event.payload as Partial<DemoState>)
      return
    }

    if (event.seq > 0) {
      setTimeline((prev) => {
        if (prev.some((item) => item.seq === event.seq && item.run_id === event.run_id)) return prev
        return [...prev, event].sort((a, b) => a.seq - b.seq)
      })
    }

    if (event.run_id) {
      setCurrentRunId(event.run_id)
      if (event.seq > 0) {
        persistCursor(event.session_id || sessionIdRef.current, event.run_id, event.seq)
      }
    }
    if (event.task_id) setCurrentTaskId(String(event.task_id))
    if (event.demo_stage) setDemoStage(String(event.demo_stage) as DemoStage)

    switch (event.type) {
      case 'run.started':
        setIsRunning(true)
        setCurrentStep('started')
        setCompleteReady(false)
        break
      case 'progress':
        setProgress(Number(event.payload?.percent || 0))
        setProgressLabel(String(event.payload?.label || ''))
        break
      case 'step.changed':
        setCurrentStep(String(event.payload?.step || ''))
        break
      case 'checklist.upsert':
        if (Array.isArray(event.payload?.items)) {
          setChecklist(event.payload.items.map((item: any) => ({
            id: String(item.id),
            label: String(item.label),
            status: item.status === 'done' ? 'done' : 'pending',
          })))
        }
        break
      case 'checklist.checked':
        setChecklist((prev) => prev.map((item) => (
          item.id === String(event.payload?.id) ? { ...item, status: 'done' } : item
        )))
        break
      case 'plan.created':
        if (event.payload?.plan) setPlan(event.payload.plan)
        break
      case 'plan.frozen':
        setSpecFrozen(true)
        break
      case 'discussion.updated':
        if (event.payload?.requirements) {
          applyDemoState({ requirements: event.payload.requirements, stage: 'discussion', spec_frozen: false })
        }
        break
      case 'ask.reply':
        setAskReplies((prev) => [event.payload as AskReply, ...prev].slice(0, 8))
        break
      case 'log.append':
      case 'message.delta':
        setLogs((prev) => [...prev, formatEventLine(event)])
        break
      case 'preview.ready':
      case 'preview.reload':
        setPreviewId(String(event.payload?.preview_id || ''))
        if (event.payload?.url) {
          const url = new URL(String(event.payload.url), window.location.origin).toString()
          if (event.type === 'preview.ready') {
            setPreviewUrl(url)
          } else {
            throttlePreviewReload(url)
          }
        }
        break
      case 'fs.changed':
        throttlePreviewReload()
        break
      case 'test.failed':
        setIsRunning(false)
        setCompleteReady(false)
        break
      case 'test.passed':
        setDemoStage('complete')
        break
      case 'complete.ready':
        setCompleteReady(true)
        break
      case 'message.cancelled':
        setIsRunning(false)
        setCurrentStep('cancelled')
        break
      case 'run.completed':
      case 'message.end':
      case 'message.error':
        setLogs((prev) => [...prev, formatEventLine(event)])
        setIsRunning(false)
        break
      default:
        break
    }
  }, [applyDemoState, persistCursor, throttlePreviewReload])

  const replayFromCursor = useCallback(async (targetSessionId: string, targetRunId: string, afterSeq: number) => {
    if (!targetSessionId || !targetRunId) return
    try {
      const resp = await get<{ events: StreamEnvelope[] }>(`/api/streams/${targetSessionId}/${targetRunId}`, {
        params: { after_seq: afterSeq },
      })
      const events = Array.isArray(resp.events) ? resp.events : []
      events.forEach((event) => consumeEvent(event))
    } catch (error) {
      console.error('[CodingPage] replay failed', error)
    }
  }, [consumeEvent])

  const restoreLatestRun = useCallback(async (targetSessionId: string) => {
    if (!targetSessionId) return

    const cursorMap = loadCursorMap()
    const localCursor = cursorMap[targetSessionId]

    try {
      const latest = await get<{ active_run?: any; latest_run?: any; demo_state?: DemoState }>(`/api/streams/${targetSessionId}/latest-run`)
      if (latest.demo_state) {
        applyDemoState(latest.demo_state)
      }

      const serverRun = latest.active_run?.run_id || latest.latest_run?.run_id || latest.demo_state?.run_id || localCursor?.run_id || ''
      const serverSeq = Number(latest.latest_run?.last_seq || 0)
      const cursorSeq = Number(localCursor?.last_seq || 0)
      const hasRenderedTimeline = timelineRef.current.length > 0
      const afterSeq = hasRenderedTimeline ? Math.max(0, Math.min(cursorSeq, serverSeq)) : 0

      if (serverRun) {
        setCurrentRunId(serverRun)
        await replayFromCursor(targetSessionId, serverRun, afterSeq)
      }
    } catch (error) {
      console.error('[CodingPage] restore latest run failed', error)
      if (localCursor?.run_id) {
        const afterSeq = timelineRef.current.length > 0 ? localCursor.last_seq : 0
        await replayFromCursor(targetSessionId, localCursor.run_id, afterSeq)
      }
    }
  }, [applyDemoState, replayFromCursor])

  const connectWs = useCallback((targetSessionId: string) => {
    if (!targetSessionId) return
    const connectToken = Date.now()
    connectTokenRef.current = connectToken
    setWsStatus((prev) => (prev === 'connected' ? 'reconnecting' : 'connecting'))
    if (reconnectTimerRef.current) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }

    if (wsRef.current) {
      intentionalCloseRef.current = true
      wsRef.current.close()
      wsRef.current = null
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/coding/${targetSessionId}`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = async () => {
      if (connectTokenRef.current !== connectToken) return
      setConnected(true)
      setWsStatus('connected')
      setWsLastClose('')
      reconnectAttemptsRef.current = 0
      setWsRetryCount(0)
      ws.send(JSON.stringify({ type: 'demo.state.get' }))
      await restoreLatestRun(targetSessionId)
    }

    ws.onmessage = (raw) => {
      try {
        const event = JSON.parse(raw.data) as StreamEnvelope
        consumeEvent(event)
      } catch (error) {
        console.error('[CodingPage] invalid ws payload', error)
      }
    }

    ws.onclose = () => {
      if (connectTokenRef.current !== connectToken) return
      setConnected(false)
      if (intentionalCloseRef.current) {
        intentionalCloseRef.current = false
        return
      }
      setWsStatus('reconnecting')
      setWsLastClose('closed_before_ready')
      if (reconnectAttemptsRef.current >= 8) {
        setWsStatus('error')
        toast.error(tRef.current(K.page.coding.toastWsReconnectFailed))
        return
      }
      reconnectAttemptsRef.current += 1
      setWsRetryCount(reconnectAttemptsRef.current)
      const delayMs = Math.min(8000, 800 * (2 ** (reconnectAttemptsRef.current - 1)))
      reconnectTimerRef.current = window.setTimeout(() => {
        connectWs(targetSessionId)
      }, delayMs)
    }

    ws.onerror = () => {
      if (connectTokenRef.current !== connectToken) return
      setConnected(false)
      setWsStatus('error')
      setWsLastClose('ws_error')
    }
  }, [consumeEvent, restoreLatestRun])

  const loadSessions = useCallback(async () => {
    try {
      const resp = await get<Array<any>>('/api/sessions')
      const rows = Array.isArray(resp) ? resp : []
      const nextSessions: SessionItem[] = rows.map((item: any) => ({
        session_id: String(item.session_id || item.id || ''),
        title: String(item.title || t(K.page.coding.defaultSessionName)),
      })).filter((item) => item.session_id)

      if (nextSessions.length === 0) {
        const created = await post<any>('/api/sessions', { title: t(K.page.coding.defaultSessionName) })
        const createdSession = {
          session_id: String(created.session_id || created.id),
          title: String(created.title || t(K.page.coding.defaultSessionName)),
        }
        setSessions([createdSession])
        setSessionId(createdSession.session_id)
        return
      }

      setSessions(nextSessions)
      setSessionId((prev) => prev || nextSessions[0].session_id)
    } catch (error) {
      toast.error(t(K.page.coding.toastLoadSessionsFailed))
      console.error('[CodingPage] load sessions failed', error)
    }
  }, [t])

  useEffect(() => {
    void loadSessions()
  }, [loadSessions])

  useEffect(() => {
    if (!prompt) {
      const nextPrompt = t(K.page.coding.defaultPrompt)
      setPrompt(nextPrompt)
      setRequirements(defaultRequirements(nextPrompt))
    }
  }, [prompt, t])

  useEffect(() => {
    if (!sessionId) return
    setTimeline([])
    setLogs([])
    setChecklist([])
    setProgress(0)
    setProgressLabel('')
    setCurrentStep('idle')
    setCurrentTaskId('')
    setPreviewId('')
    setPreviewUrl('')
    setAskReplies([])
    setCompleteReady(false)
    connectWs(sessionId)
    void restoreLatestRun(sessionId)
  }, [sessionId, connectWs, restoreLatestRun])

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        intentionalCloseRef.current = true
        wsRef.current.close()
      }
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
      if (reloadTimerRef.current) window.clearTimeout(reloadTimerRef.current)
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(SANDBOX_MODE_KEY, sandboxMode)
    } catch {
      // no-op
    }
  }, [sandboxMode])

  const sendWs = useCallback((data: Record<string, any>) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      toast.warning(t(K.page.coding.toastWsDisconnected))
      return false
    }
    wsRef.current.send(JSON.stringify(data))
    return true
  }, [t])

  const handleSaveDiscussion = useCallback(() => {
    const payload = {
      ...requirements,
      goal: requirements.goal || prompt,
      variants: selectedVariant ? [selectedVariant] : requirements.variants.length > 0 ? requirements.variants : ['apple_iphone17pro'],
      framework: requirements.framework || 'react',
      provider: requirements.provider || 'mui',
      contract_id: requirements.contract_id || 'brand_soft',
      page_type: requirements.page_type || 'landing',
      delivery_variant: requirements.delivery_variant || 'deliver_page_spec',
    }
    if (!sendWs({ type: 'discussion.update', requirements: payload })) return
    toast.success(t(K.page.coding.toastDiscussionSaved))
  }, [requirements, prompt, sendWs, t])

  const handleGeneratePlan = useCallback(() => {
    if (!sendWs({ type: 'plan.generate' })) return
  }, [sendWs])

  const handleFreezePlan = useCallback(() => {
    if (!sendWs({ type: 'plan.freeze' })) return
  }, [sendWs])

  const handleStart = useCallback(() => {
    if (demoStage === 'discussion' || !specFrozen) {
      toast.warning(t(K.page.coding.toastFreezePlanRequired))
      return
    }
    if (!sendWs({
      type: 'run.start',
      prompt,
      metadata: {
        long_mode: longMode,
        force_test_fail: forceTestFail,
        variant: selectedVariant,
        delivery_variant: requirements.delivery_variant || 'deliver_page_spec',
        framework: requirements.framework || 'react',
        provider: requirements.provider || 'mui',
        contract_id: requirements.contract_id || 'brand_soft',
        page_type: requirements.page_type || 'landing',
      },
    })) return
    setIsRunning(true)
  }, [demoStage, specFrozen, sendWs, prompt, longMode, forceTestFail, selectedVariant, requirements, t])

  const handleStop = useCallback(() => {
    if (!currentRunId) return
    sendWs({
      type: 'control.stop',
      run_id: currentRunId,
      command_id: `cmd_${Date.now()}`,
      reason: 'user_clicked_stop',
    })
  }, [currentRunId, sendWs])

  const handleAsk = useCallback(() => {
    if (!currentRunId) {
      toast.info(t(K.page.coding.toastRunRequired))
      return
    }
    sendWs({
      type: 'ask.query',
      run_id: currentRunId,
      payload: {
        scope: askScope,
        key: askKey,
      },
    })
  }, [askKey, askScope, currentRunId, sendWs, t])

  const handleCreatePreview = useCallback(async () => {
    if (!sessionId || !currentRunId) {
      toast.info(t(K.page.coding.toastRunRequired))
      return
    }
    try {
      const html = `<!doctype html><html><body><h1>${t(K.page.coding.manualPreviewTitle)}</h1><p>${t(K.page.coding.manualPreviewBody)}</p></body></html>`
      const created = await post<any>('/api/preview', {
        preset: 'html-basic',
        html,
        session_id: sessionId,
        run_id: currentRunId,
      })
      const url = new URL(String(created.url), window.location.origin).toString()
      setPreviewId(String(created.preview_id || ''))
      setPreviewUrl(url)
      toast.success(t(K.page.coding.toastPreviewCreated))
    } catch (error) {
      toast.error(t(K.page.coding.toastPreviewCreateFailed))
      console.error('[CodingPage] create preview failed', error)
    }
  }, [sessionId, currentRunId, t])

  const handleReloadPreview = useCallback(async () => {
    if (!previewId) {
      toast.info(t(K.page.coding.toastPreviewMissing))
      return
    }
    try {
      const updated = await post<any>(`/api/preview/${previewId}/reload`, {
        session_id: sessionId,
        run_id: currentRunId,
      })
      if (updated.url) {
        const url = new URL(String(updated.url), window.location.origin).toString()
        throttlePreviewReload(url)
      }
      toast.success(t(K.page.coding.toastPreviewReloaded))
    } catch (error) {
      toast.error(t(K.page.coding.toastPreviewReloadFailed))
      console.error('[CodingPage] reload preview failed', error)
    }
  }, [previewId, sessionId, currentRunId, throttlePreviewReload, t])

  const handleToggleFullscreen = useCallback(async () => {
    const root = previewPaneRef.current
    if (!root) return
    try {
      if (!document.fullscreenElement) {
        await root.requestFullscreen()
        setFullscreenOn(true)
      } else {
        await document.exitFullscreen()
        setFullscreenOn(false)
      }
    } catch {
      if (previewUrl) window.open(previewUrl, '_blank', 'noopener,noreferrer')
    }
  }, [previewUrl])

  useEffect(() => {
    const onFs = () => setFullscreenOn(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const stageLabel = useCallback((stage: DemoStage) => {
    switch (stage) {
      case 'discussion': return t(K.page.coding.stageDiscussion)
      case 'planning': return t(K.page.coding.stagePlanning)
      case 'worker': return t(K.page.coding.stageWorker)
      case 'test': return t(K.page.coding.stageTest)
      case 'complete': return t(K.page.coding.stageComplete)
      default: return stage
    }
  }, [t])

  return (
    <Paper sx={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, borderRadius: 2, boxShadow: 2, overflow: 'hidden', bgcolor: 'background.paper' }}>
      <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          <Chip size="small" color={connected ? 'success' : 'warning'} label={connected ? t(K.page.coding.connected) : t(K.page.coding.disconnected)} />
          <Chip size="small" variant="outlined" label={isRunning ? t(K.page.coding.running) : t(K.page.coding.idle)} />
          <Chip size="small" color={completeReady ? 'success' : 'default'} label={`${t(K.page.coding.stage)}: ${stageLabel(demoStage)}`} />
          <Chip size="small" variant="outlined" label={`${t(K.page.coding.wsStatusLabel)}: ${wsStatus}`} />
          {wsRetryCount > 0 && <Chip size="small" color="warning" label={`${t(K.page.coding.wsRetrying)} ${wsRetryCount}`} />}
          <Typography variant="caption" color="text.secondary">{t(K.page.coding.runLabel)}: {currentRunId || '-'}</Typography>
          <Typography variant="caption" color="text.secondary">{t(K.page.coding.taskLabel)}: {currentTaskId || '-'}</Typography>
          <Typography variant="caption" color="text.secondary">{t(K.page.coding.seqLabel)}: {lastSeq}</Typography>
          {wsLastClose && <Typography variant="caption" color="warning.main">{t(K.page.coding.wsLastClose)}: {wsLastClose}</Typography>}
        </Stack>

        <Grid container spacing={1} alignItems="center" sx={{ width: { xs: '100%', md: 'auto' } }}>
          <Grid item xs={12} md>
            <Select size="small" value={sessionId} onChange={(event) => setSessionId(String(event.target.value))} fullWidth>
              {sessions.map((session) => (
                <MenuItem key={session.session_id} value={session.session_id}>{session.title}</MenuItem>
              ))}
            </Select>
          </Grid>
          <Grid item xs={12} md="auto">
            <Button variant="outlined" onClick={() => void loadSessions()} sx={{ minWidth: 140, whiteSpace: 'nowrap' }}>
              {t(K.common.refresh)}
            </Button>
          </Grid>
        </Grid>
      </Box>

      <Divider />

      <Box sx={{ px: 2, py: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {STAGES.map((stage) => (
          <Chip
            key={stage}
            label={`${STAGES.indexOf(stage) + 1}. ${stageLabel(stage)}`}
            color={demoStage === stage ? 'primary' : completeReady && stage === 'complete' ? 'success' : 'default'}
            variant={demoStage === stage ? 'filled' : 'outlined'}
            size="small"
            sx={(theme) => ({
              color: demoStage === stage
                ? theme.palette.getContrastText(theme.palette.primary.main)
                : theme.palette.text.primary,
            })}
          />
        ))}
      </Box>

      <Divider />

      <Box sx={{ px: 2, py: 1.5, display: 'grid', gap: 1.5, gridTemplateColumns: '1fr 1fr', alignItems: 'start' }}>
        <Paper variant="outlined" sx={{ p: 1.25 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.discussionTitle)}</Typography>
          <Stack spacing={1.5}>
            <TextField size="small" label={t(K.page.coding.promptLabel)} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <TextField size="small" label={t(K.page.coding.goalLabel)} value={requirements.goal} onChange={(event) => setRequirements((prev) => ({ ...prev, goal: event.target.value }))} />
            <TextField size="small" label={t(K.page.coding.variantsLabel)} value={requirements.variants.join(', ')} onChange={(event) => setRequirements((prev) => ({ ...prev, variants: event.target.value.split(',').map((v) => v.trim()).filter(Boolean) }))} />
            <Select
              size="small"
              value={selectedVariant}
              onChange={(event) => setSelectedVariant(String(event.target.value))}
            >
              <MenuItem value="apple_iphone17pro">apple_iphone17pro</MenuItem>
              <MenuItem value="landing_saas">landing_saas</MenuItem>
              <MenuItem value="skeleton">skeleton</MenuItem>
              <MenuItem value="scroll">scroll</MenuItem>
              <MenuItem value="carousel">carousel</MenuItem>
              <MenuItem value="three">three</MenuItem>
            </Select>
            <Select
              size="small"
              value={requirements.framework || 'react'}
              onChange={(event) => setRequirements((prev) => ({ ...prev, framework: String(event.target.value) }))}
            >
              <MenuItem value="react">{t('page.coding.optionFrameworkReact')}</MenuItem>
              <MenuItem value="vue">{t('page.coding.optionFrameworkVue')}</MenuItem>
            </Select>
            <Select
              size="small"
              value={requirements.provider || 'mui'}
              onChange={(event) => setRequirements((prev) => ({ ...prev, provider: String(event.target.value) }))}
            >
              <MenuItem value="mui">{t('page.coding.optionProviderMui')}</MenuItem>
              <MenuItem value="antd">{t('page.coding.optionProviderAntd')}</MenuItem>
              <MenuItem value="vuetify">{t('page.coding.optionProviderVuetify')}</MenuItem>
              <MenuItem value="tailwind">{t('page.coding.optionProviderTailwind')}</MenuItem>
            </Select>
            <TextField
              size="small"
              label={t('page.coding.contractId')}
              value={requirements.contract_id || 'brand_soft'}
              onChange={(event) => setRequirements((prev) => ({ ...prev, contract_id: String(event.target.value) }))}
            />
            <Select
              size="small"
              value={requirements.page_type || 'landing'}
              onChange={(event) => setRequirements((prev) => ({ ...prev, page_type: String(event.target.value) }))}
            >
              <MenuItem value="landing">{t('page.coding.optionPageTypeLanding')}</MenuItem>
              <MenuItem value="product">{t('page.coding.optionPageTypeProduct')}</MenuItem>
              <MenuItem value="editorial">{t('page.coding.optionPageTypeEditorial')}</MenuItem>
            </Select>
            <Button variant="outlined" onClick={handleSaveDiscussion}>{t(K.page.coding.saveDiscussion)}</Button>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 1.25 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.planningTitle)}</Typography>
          <Grid container spacing={1} sx={{ mb: 1 }} alignItems="center">
            <Grid item xs={12} md="auto">
              <Button variant="outlined" onClick={handleGeneratePlan} sx={{ minWidth: 140, whiteSpace: 'nowrap' }}>
                {t(K.page.coding.generatePlan)}
              </Button>
            </Grid>
            <Grid item xs={12} md="auto">
              <Button variant="contained" onClick={handleFreezePlan} sx={{ minWidth: 140, whiteSpace: 'nowrap' }}>
                {t(K.page.coding.freezePlan)}
              </Button>
            </Grid>
            <Grid item xs={12} md>
              <Box sx={{ display: 'flex', justifyContent: { xs: 'flex-start', md: 'flex-end' } }}>
                <Chip size="small" color={specFrozen ? 'success' : 'default'} label={specFrozen ? t(K.page.coding.frozen) : t(K.page.coding.notFrozen)} />
              </Box>
            </Grid>
          </Grid>
          <List dense sx={{ maxHeight: 140, overflow: 'auto' }}>
            {(plan.tasks || []).map((task) => (
              <ListItem key={task.id} divider>
                <ListItemText primary={`${task.id} · ${task.title}`} secondary={`${task.owner} · ${task.variant}`} />
              </ListItem>
            ))}
            {(plan.tasks || []).length === 0 && (
              <ListItem><ListItemText primary={t(K.page.coding.emptyPlan)} /></ListItem>
            )}
          </List>
        </Paper>
      </Box>

      <Divider />

      <Box sx={{ px: 2, py: 1.5, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button variant={longMode ? 'contained' : 'outlined'} onClick={() => setLongMode((prev) => !prev)}>{t(K.page.coding.longRun)}</Button>
        <Button variant={forceTestFail ? 'contained' : 'outlined'} color="warning" onClick={() => setForceTestFail((prev) => !prev)}>{t(K.page.coding.failTestMode)}</Button>
        <Button variant="contained" onClick={handleStart} disabled={!connected || isRunning || !specFrozen}>{t(K.page.coding.startRun)}</Button>
        <Button variant="outlined" color="warning" onClick={handleStop} disabled={!isRunning || !currentRunId}>{t(K.common.stop)}</Button>
        <Button variant="outlined" onClick={() => void handleCreatePreview()}>{t(K.page.coding.createPreview)}</Button>
        <Button variant="outlined" onClick={() => void handleReloadPreview()}>{t(K.page.coding.reloadPreview)}</Button>
      </Box>

      <Divider />

      <Box sx={{ px: 2, py: 1.25 }}>
        <Typography variant="body2" color="text.secondary">{t(K.page.coding.currentStep)}: {currentStep || '-'}</Typography>
        <Typography variant="caption" color="text.secondary">{progressLabel || t(K.page.coding.waiting)}</Typography>
        <LinearProgress variant="determinate" value={progress} sx={{ mt: 0.75, height: 6, borderRadius: 999 }} />
      </Box>

      <Divider />

      <Box sx={{ px: 2, py: 1.5 }}>
        <Grid container spacing={1.5} alignItems="center">
          <Grid item xs={12} md={3}>
            <Select size="small" value={askScope} onChange={(event) => setAskScope(event.target.value as any)} fullWidth>
              <MenuItem value="all">all</MenuItem>
              <MenuItem value="role">role</MenuItem>
              <MenuItem value="task">task</MenuItem>
              <MenuItem value="file">file</MenuItem>
            </Select>
          </Grid>
          <Grid item xs={12} md>
            <TextField size="small" label={t(K.page.coding.askKeyLabel)} value={askKey} onChange={(event) => setAskKey(event.target.value)} fullWidth />
          </Grid>
          <Grid item xs={12} md="auto">
            <Button variant="outlined" onClick={handleAsk} disabled={!currentRunId} sx={{ minWidth: 120, whiteSpace: 'nowrap' }}>
              {t(K.page.coding.askButton)}
            </Button>
          </Grid>
        </Grid>
      </Box>

      <Divider />

      <Box sx={{ display: 'grid', gridTemplateColumns: '1.25fr 1fr', gap: 1.5, p: 1.5, flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Box sx={{ minHeight: 0, display: 'grid', gridTemplateRows: '1fr 1fr', gap: 1.5 }}>
          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.25 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.logs)}</Typography>
            <Box component="pre" sx={{ m: 0, fontSize: 12, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{logs.join('')}</Box>
          </Paper>

          <Paper variant="outlined" sx={{ minHeight: 0, overflow: 'auto', p: 1.25 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.timeline)}</Typography>
            <List dense>
              {timeline.map((event) => (
                <ListItem key={`${event.run_id}-${event.seq}`} divider>
                  <ListItemText
                    primary={`${event.seq}. ${event.type}`}
                    secondary={`${event.ts} | ${event.role || '-'} | ${event.task_id || '-'} | ${JSON.stringify(event.payload)}`}
                  />
                </ListItem>
              ))}
              {timeline.length === 0 && (
                <ListItem><ListItemText primary={t(K.page.coding.emptyTimeline)} /></ListItem>
              )}
            </List>
          </Paper>
        </Box>

        <Box sx={{ minHeight: 0, display: 'grid', gridTemplateRows: 'auto auto 1fr', gap: 1.5 }}>
          <Paper variant="outlined" sx={{ p: 1.25 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.checklist)}</Typography>
            <List dense>
              {checklist.map((item) => (
                <ListItem key={item.id}><ListItemText primary={item.label} secondary={item.status === 'done' ? t(K.page.coding.done) : t(K.page.coding.pending)} /></ListItem>
              ))}
              {checklist.length === 0 && <ListItem><ListItemText primary={t(K.page.coding.emptyChecklist)} /></ListItem>}
            </List>
          </Paper>

          <Paper variant="outlined" sx={{ p: 1.25, minHeight: 100, maxHeight: 180, overflow: 'auto' }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t(K.page.coding.askReplies)}</Typography>
            {askReplies.length === 0 && <Typography variant="body2" color="text.secondary">{t(K.page.coding.askRepliesEmpty)}</Typography>}
            {askReplies.map((reply, idx) => (
              <Box key={`${reply.summary}-${idx}`} sx={{ mb: 1, pb: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="body2">{reply.summary}</Typography>
                <Typography variant="caption" color="text.secondary">blockers: {(reply.blockers || []).join(', ') || '-'}</Typography>
                <Typography variant="caption" display="block" color="text.secondary">
                  next: {(reply.next_steps || []).join(' | ') || '-'}
                </Typography>
                <Typography variant="caption" display="block" color="text.secondary">
                  files: {(reply.recent_files || []).map((entry) => {
                    if (typeof entry === 'string') return entry
                    return `${entry.path} (${entry.role || '-'}:${entry.task_id || '-'})`
                  }).join(' ; ') || '-'}
                </Typography>
              </Box>
            ))}
          </Paper>

          <Paper ref={previewPaneRef} variant="outlined" sx={{ minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <Box sx={{ px: 1.25, py: 1, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="subtitle2">{t(K.page.coding.preview)}</Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="caption" color="text.secondary">{previewId || '-'}</Typography>
                <Button
                  size="small"
                  variant={sandboxMode === 'strict' ? 'contained' : 'outlined'}
                  onClick={() => setSandboxMode((prev) => (prev === 'demo' ? 'strict' : 'demo'))}
                >
                  {sandboxMode === 'strict' ? t(K.page.coding.sandboxStrict) : t(K.page.coding.sandboxDemo)}
                </Button>
                {completeReady && (
                  <Button size="small" variant="outlined" onClick={() => void handleToggleFullscreen()}>
                    {fullscreenOn ? t(K.common.exitFullscreen) : t(K.common.fullscreen)}
                  </Button>
                )}
              </Stack>
            </Box>
            {previewUrl ? (
              <>
                <Box sx={{ px: 1.25, py: 0.5, borderBottom: '1px solid', borderColor: 'divider' }}>
                  <Typography variant="caption" color="text.secondary">
                    {sandboxMode === 'strict' ? t(K.page.coding.sandboxStrictHelp) : t(K.page.coding.sandboxDemoHelp)}
                  </Typography>
                </Box>
                <iframe
                  title={t(K.page.coding.preview)}
                  src={previewUrl}
                  style={{ border: 0, width: '100%', height: '100%' }}
                  sandbox={sandboxMode === 'strict' ? 'allow-scripts allow-forms' : 'allow-scripts allow-same-origin allow-forms'}
                />
              </>
            ) : (
              <Box sx={{ p: 2 }}><Typography variant="body2" color="text.secondary">{t(K.page.coding.previewPlaceholder)}</Typography></Box>
            )}
          </Paper>
        </Box>
      </Box>
    </Paper>
  )
}
