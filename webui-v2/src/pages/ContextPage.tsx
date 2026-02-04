/**
 * ContextPage - Session Context Management
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.context.xxx)
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ Phase 6: Real API Integration (NO MOCK DATA)
 * - ✅ v1 Alignment: Single-session detail view with 4 tabs
 *
 * v1 Architecture:
 * - Session selector (input + recent sessions picker)
 * - 4-tab layout: Status, Budget, Operations, Raw
 * - Operations: Refresh, Attach, Detach context
 * - Real-time status updates with toast notifications
 */

import { useState, useCallback } from 'react'
import {
  Box,
  Stack,
  TextField,
  Button,
  Typography,
  Chip,
  Tabs,
  Tab,
  Grid,
  CircularProgress,
  Alert,
} from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { LoadingState, ErrorState } from '@/components'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { brainosService } from '@/services'
import { ConfirmDialog } from '@/ui/interaction/ConfirmDialog'
import {
  RefreshIcon,
  AttachmentIcon,
  CutIcon,
  HistoryIcon,
  InfoIcon,
  AccountBalanceIcon,
  SettingsIcon,
  CodeIcon,
} from '@/ui/icons'

/**
 * Context Status 接口（对齐 v1 API）
 */
interface ContextStatus {
  session_id: string
  state: 'EMPTY' | 'ATTACHED' | 'BUILDING' | 'STALE' | 'ERROR'
  updated_at: string
  tokens: {
    prompt: number
    completion: number
    context_window: number
    used: number
    available: number
  }
  budget?: {
    system_tokens: number
    window_tokens: number
    rag_tokens: number
    memory_tokens: number
    auto_derived: boolean
  }
  usage?: {
    tokens_system: number
    tokens_window: number
    tokens_rag: number
    tokens_memory: number
    trimming_log?: Array<{
      timestamp: string
      items_removed: number
      component: string
      tokens_saved: number
    }>
  }
  rag: Record<string, unknown>
  memory: Record<string, unknown>
}

/**
 * Tab 类型
 */
type TabType = 'status' | 'budget' | 'operations' | 'raw'

/**
 * ContextPage 组件
 */
export default function ContextPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [contextStatus, setContextStatus] = useState<ContextStatus | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [currentTab, setCurrentTab] = useState<TabType>('status')
  const [operationLoading, setOperationLoading] = useState(false)
  const [operationMessage, setOperationMessage] = useState('')
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false)
  const [detachLoading, setDetachLoading] = useState(false)

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.context.title),
    subtitle: t(K.page.context.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'contained',
      onClick: () => {
        if (sessionId) {
          void loadContextStatus()
        } else {
          toast.error(t(K.page.context.pleaseEnterSessionId))
        }
      },
      disabled: !sessionId,
    },
  ])

  // ===================================
  // API Integration
  // ===================================
  const loadContextStatus = useCallback(async () => {
    if (!sessionId) {
      toast.error(t(K.page.context.pleaseEnterSessionId))
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await brainosService.getContextManager(sessionId)

      // Map API response to ContextStatus
      setContextStatus({
        session_id: response.session_id,
        state: response.state as ContextStatus['state'],
        updated_at: response.updated_at,
        tokens: response.tokens,
        rag: response.rag,
        memory: response.memory,
      })

      toast.success(t(K.page.context.contextStatusLoaded))
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      console.error('Failed to load context status:', err)
      toast.error('Error: ' + errorMessage)
      setContextStatus(null)
    } finally {
      setLoading(false)
    }
  }, [sessionId, t])

  const loadRecentSessions = async () => {
    try {
      const sessions = await brainosService.listSessions(10)

      if (sessions.length === 0) {
        toast.info(t(K.page.context.noSessionsFound))
        return
      }

      // Simple selection - use the first session
      const firstSession = sessions[0]
      setSessionId(firstSession.id)
      toast.success(t(K.page.context.loadedSession).replace('{sessionId}', firstSession.id))

      void loadContextStatus()
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to load sessions:', err)
      toast.error(t(K.page.context.errorLoadingSessions).replace('{error}', errorMessage))
    }
  }

  const refreshContext = async () => {
    if (!sessionId) {
      toast.error(t(K.page.context.noSessionSelected))
      return
    }

    setOperationLoading(true)
    setOperationMessage(t(K.page.context.refreshingContext))

    try {
      const response = await brainosService.refreshContext(sessionId)

      if (response.ok) {
        toast.success(t(K.page.context.contextRefreshedSuccess))
        setOperationMessage(t(K.page.context.contextRefreshedState).replace('{state}', response.state || 'N/A'))

        void loadContextStatus()
      } else {
        throw new Error(response.message || t(K.page.context.failedToRefreshContext))
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to refresh context:', err)
      setOperationMessage('Error: ' + errorMessage)
      toast.error('Error: ' + errorMessage)
    } finally {
      setOperationLoading(false)
    }
  }

  const attachContext = async () => {
    if (!sessionId) {
      toast.error(t(K.page.context.noSessionSelected))
      return
    }

    setOperationLoading(true)
    setOperationMessage(t(K.page.context.attachingContext))

    try {
      const response = await brainosService.attachContext(sessionId, {
        memory: { enabled: true, namespace: 'default' },
        rag: { enabled: true },
      })

      if (response.ok) {
        toast.success(t(K.page.context.contextAttachedSuccess))
        setOperationMessage(t(K.page.context.contextAttachedMemoryRag))

        void loadContextStatus()
      } else {
        throw new Error(response.message || t(K.page.context.failedToAttachContext))
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to attach context:', err)
      setOperationMessage('Error: ' + errorMessage)
      toast.error('Error: ' + errorMessage)
    } finally {
      setOperationLoading(false)
    }
  }

  const detachContext = async () => {
    if (!sessionId) {
      toast.error(t(K.page.context.noSessionSelected))
      return
    }

    setDetachLoading(true)

    try {
      const response = await brainosService.clearContext(sessionId)

      if (response.ok) {
        toast.success(t(K.page.context.contextDetachedSuccess))
        setOperationMessage(t(K.page.context.contextDetached))
        setConfirmDialogOpen(false)

        void loadContextStatus()
      } else {
        throw new Error(response.message || t(K.page.context.failedToDetachContext))
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to detach context:', err)
      setOperationMessage('Error: ' + errorMessage)
      toast.error('Error: ' + errorMessage)
    } finally {
      setDetachLoading(false)
    }
  }

  // ===================================
  // State Badge Helpers
  // ===================================
  const getStateBadgeColor = (state: string): 'info' | 'success' | 'warning' | 'error' | 'default' => {
    switch (state) {
      case 'EMPTY':
        return 'info'
      case 'ATTACHED':
        return 'success'
      case 'BUILDING':
      case 'STALE':
        return 'warning'
      case 'ERROR':
        return 'error'
      default:
        return 'default'
    }
  }

  // ===================================
  // Tab Rendering
  // ===================================
  const renderStatusTab = () => {
    if (!contextStatus) return null

    const hasRAG = contextStatus.rag && Object.keys(contextStatus.rag).length > 0
    const hasMemory = contextStatus.memory && Object.keys(contextStatus.memory).length > 0

    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.context.contextStatus)}
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {t(K.page.context.sessionId)}
              </Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                {contextStatus.session_id}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {t(K.page.context.state)}
              </Typography>
              <Chip
                label={contextStatus.state}
                color={getStateBadgeColor(contextStatus.state)}
                size="small"
                sx={{ mt: 0.5 }}
              />
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="body2" color="text.secondary">
                {t(K.page.context.updatedAt)}
              </Typography>
              <Typography variant="body1" sx={{ fontSize: '0.875rem' }}>
                {new Date(contextStatus.updated_at).toLocaleString()}
              </Typography>
            </Box>
          </Grid>
          {contextStatus.tokens && (
            <Grid item xs={12} md={6}>
              <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  {t(K.page.context.tokens)}
                </Typography>
                <Typography variant="body1" sx={{ fontSize: '0.875rem' }}>
                  {contextStatus.tokens.prompt || 0} {t(K.page.context.prompt)} / {contextStatus.tokens.completion || 0} {t(K.page.context.completion)}
                  <br />
                  ({t(K.page.context.window)}: {contextStatus.tokens.context_window || 'N/A'})
                </Typography>
              </Box>
            </Grid>
          )}
          {(hasRAG || hasMemory) && (
            <Grid item xs={12}>
              <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  {t(K.page.context.components)}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                  {hasRAG && <Chip label={t(K.page.context.rag)} color="info" size="small" />}
                  {hasMemory && <Chip label={t(K.page.context.memory)} color="info" size="small" />}
                </Stack>
              </Box>
            </Grid>
          )}
        </Grid>
      </Box>
    )
  }

  const renderBudgetTab = () => {
    if (!contextStatus) return null

    const budget = contextStatus.budget || {
      system_tokens: 1000,
      window_tokens: 4000,
      rag_tokens: 2000,
      memory_tokens: 1000,
      auto_derived: true,
    }

    const usage = contextStatus.usage || {
      tokens_system: 0,
      tokens_window: 0,
      tokens_rag: 0,
      tokens_memory: 0,
    }

    const configSource = budget.auto_derived ? t(K.page.context.autoDerived) : t(K.page.context.configured)

    const renderBudgetRow = (component: string, budgetValue: number, usedValue: number) => {
      const percent = budgetValue > 0 ? ((usedValue / budgetValue) * 100).toFixed(1) : '0.0'
      return (
        <tr key={component}>
          <td style={{ padding: '8px', borderBottom: '1px solid #e0e0e0' }}>{component}</td>
          <td style={{ padding: '8px', borderBottom: '1px solid #e0e0e0' }}>{budgetValue.toLocaleString()}</td>
          <td style={{ padding: '8px', borderBottom: '1px solid #e0e0e0' }}>{usedValue.toLocaleString()}</td>
          <td style={{ padding: '8px', borderBottom: '1px solid #e0e0e0' }}>{percent}%</td>
        </tr>
      )
    }

    const trimmingLog = usage.trimming_log || []

    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.context.budgetAllocation)}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {t(K.page.context.configurationSource)}: {configSource}
        </Typography>
        <Box sx={{ overflowX: 'auto', mt: 2 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ backgroundColor: '#f5f5f5' }}>
                <th style={{ padding: '12px 8px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>{t(K.page.context.component)}</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>{t(K.page.context.budget)}</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>{t(K.page.context.used)}</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', borderBottom: '2px solid #e0e0e0' }}>{t(K.page.context.percentUsed)}</th>
              </tr>
            </thead>
            <tbody>
              {renderBudgetRow(t(K.page.context.system), budget.system_tokens, usage.tokens_system)}
              {renderBudgetRow(t(K.page.context.window), budget.window_tokens, usage.tokens_window)}
              {renderBudgetRow(t(K.page.context.rag), budget.rag_tokens, usage.tokens_rag)}
              {renderBudgetRow(t(K.page.context.memory), budget.memory_tokens, usage.tokens_memory)}
            </tbody>
          </table>
        </Box>

        <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
          {t(K.page.context.trimmingHistory)}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {t(K.page.context.lastOperations)}
        </Typography>
        {trimmingLog.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            {t(K.page.context.noTrimmingYet)}
          </Typography>
        ) : (
          <Box component="ul" sx={{ pl: 2, mt: 2 }}>
            {trimmingLog.slice(-5).map((entry, index) => (
              <li key={index}>
                {new Date(entry.timestamp).toLocaleString()} - Trimmed {entry.items_removed} {entry.component} items
                ({(entry.tokens_saved / 1000).toFixed(1)}k tokens)
              </li>
            ))}
          </Box>
        )}
      </Box>
    )
  }

  const renderOperationsTab = () => {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.context.operations)}
        </Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap" sx={{ mb: 3 }}>
          <Button
            variant="contained"
            color="primary"
            startIcon={<RefreshIcon />}
            onClick={refreshContext}
            disabled={!sessionId || operationLoading}
          >
            {t(K.page.context.refreshContext)}
          </Button>
          <Button
            variant="outlined"
            color="primary"
            startIcon={<AttachmentIcon />}
            onClick={attachContext}
            disabled={!sessionId || operationLoading}
          >
            {t(K.page.context.attachContext)}
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CutIcon />}
            onClick={() => setConfirmDialogOpen(true)}
            disabled={!sessionId || operationLoading}
          >
            {t(K.page.context.detachContext)}
          </Button>
        </Stack>

        {operationLoading && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'primary.main' }}>
            <CircularProgress size={16} />
            <Typography variant="body2">{operationMessage}</Typography>
          </Box>
        )}

        {!operationLoading && operationMessage && (
          <Alert severity={operationMessage.startsWith('Error') ? 'error' : 'success'}>
            {operationMessage}
          </Alert>
        )}
      </Box>
    )
  }

  const renderRawTab = () => {
    if (!contextStatus) return null

    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.context.fullContextData)}
        </Typography>
        <Box
          sx={{
            p: 2,
            backgroundColor: '#f5f5f5',
            borderRadius: 1,
            overflow: 'auto',
            maxHeight: '500px',
          }}
        >
          <pre style={{ margin: 0, fontSize: '0.875rem', fontFamily: 'monospace' }}>
            {JSON.stringify(contextStatus, null, 2)}
          </pre>
        </Box>
      </Box>
    )
  }

  // ===================================
  // Render States
  // ===================================
  if (loading && !contextStatus) {
    return <LoadingState />
  }

  if (error && !contextStatus) {
    return (
      <ErrorState
        error={error}
        onRetry={() => void loadContextStatus()}
        retryText={t('common.retry')}
      />
    )
  }

  // ===================================
  // Main Render
  // ===================================
  return (
    <Box sx={{ p: 3 }}>
      {/* Session Selector */}
      <Box sx={{ mb: 3, p: 3, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.context.selectSession)}
        </Typography>
        <Stack spacing={2}>
          <TextField
            label={t(K.page.context.sessionId)}
            placeholder={t(K.page.context.sessionIdPlaceholder)}
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            fullWidth
            size="small"
            helperText={t(K.page.context.sessionIdHelperText)}
          />
          <Stack direction="row" spacing={2} flexWrap="wrap">
            <Button
              variant="contained"
              color="primary"
              startIcon={<InfoIcon />}
              onClick={() => void loadContextStatus()}
              disabled={!sessionId || loading}
            >
              {t(K.page.context.loadContextStatus)}
            </Button>
            <Button
              variant="outlined"
              color="primary"
              startIcon={<HistoryIcon />}
              onClick={() => void loadRecentSessions()}
            >
              {t(K.page.context.recentSessions)}
            </Button>
          </Stack>
        </Stack>
      </Box>

      {/* Context Status Section */}
      {contextStatus && (
        <Box>
          {/* Tab Navigation */}
          <Tabs value={currentTab} onChange={(_, newValue) => setCurrentTab(newValue)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tab value="status" label={t(K.page.context.tabStatus)} icon={<InfoIcon />} iconPosition="start" />
            <Tab value="budget" label={t(K.page.context.tabBudget)} icon={<AccountBalanceIcon />} iconPosition="start" />
            <Tab value="operations" label={t(K.page.context.tabOperations)} icon={<SettingsIcon />} iconPosition="start" />
            <Tab value="raw" label={t(K.page.context.tabRawData)} icon={<CodeIcon />} iconPosition="start" />
          </Tabs>

          {/* Tab Content */}
          <Box sx={{ mt: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
            {currentTab === 'status' && renderStatusTab()}
            {currentTab === 'budget' && renderBudgetTab()}
            {currentTab === 'operations' && renderOperationsTab()}
            {currentTab === 'raw' && renderRawTab()}
          </Box>
        </Box>
      )}

      {/* Detach Confirmation Dialog */}
      <ConfirmDialog
        open={confirmDialogOpen}
        onClose={() => setConfirmDialogOpen(false)}
        title={t(K.page.context.detachConfirmTitle)}
        message={t(K.page.context.detachConfirmMessage).replace('{sessionId}', sessionId)}
        confirmText={t(K.page.context.detach)}
        cancelText={t(K.page.context.cancel)}
        onConfirm={detachContext}
        loading={detachLoading}
        color="error"
      />
    </Box>
  )
}
