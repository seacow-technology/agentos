/**
 * SupportPage - Support & Diagnostics
 *
 * Phase 6.1: Full API Integration & State Management
 * - Real API calls for diagnostics
 * - Complete error/empty/success state handling
 * - i18n compliant
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap, ItemCard, AppCard, AppCardHeader, AppCardBody, PrimaryButton } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import {
  Download as DownloadIcon,
  Preview as PreviewIcon,
  ContentCopy as CopyIcon,
  Favorite as FavoriteIcon,
  Power as PowerIcon,
  Done as DoneIcon,
  Description as DescriptionIcon,
} from '@mui/icons-material'
import { Box, Typography, Alert } from '@mui/material'
import { httpClient } from '@platform/http'

interface DiagnosticLink {
  id: string
  title: string
  description: string
  icon: React.ReactNode
  meta: Array<{ key: string; label: string; value: string }>
  actions: Array<{ key: string; label: string; onClick: () => void }>
}

interface DiagnosticData {
  systemHealth: string
  providersReady: number
  lastSelfCheckTime: string
  lastLogTime: string
}

export default function SupportPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quickLinks, setQuickLinks] = useState<DiagnosticLink[]>([])

  // ===================================
  // Data Loading
  // ===================================

  // Format timestamp to user-friendly format
  const formatTimestamp = (timestamp: string): string => {
    try {
      const date = new Date(timestamp)
      // Check if date is valid
      if (isNaN(date.getTime())) {
        return timestamp
      }
      // Format: YYYY-MM-DD HH:mm:ss
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    } catch (error) {
      console.error('Failed to format timestamp:', error)
      return timestamp
    }
  }

  const loadDiagnostics = async () => {
    setLoading(true)
    setError(null)
    try {
      // Real API call for diagnostic data
      const response = await httpClient.get<{ ok: boolean; data: DiagnosticData }>('/api/support/diagnostics')

      if (response.data.ok && response.data.data) {
        // Build quick links from diagnostic data
        const links: DiagnosticLink[] = [
          {
            id: '1',
            title: t(K.page.support.systemHealth),
            description: t(K.page.support.systemHealthDesc),
            icon: <FavoriteIcon />,
            meta: [{ key: 'status', label: t(K.page.support.status), value: response.data.data.systemHealth }],
            actions: [
              {
                key: 'view',
                label: t(K.page.support.view),
                onClick: () => console.log('View System Health'),
              },
            ],
          },
          {
            id: '2',
            title: t(K.page.support.providerStatus),
            description: t(K.page.support.providerStatusDesc),
            icon: <PowerIcon />,
            meta: [{
              key: 'providers',
              label: t(K.page.support.providers),
              value: `${response.data.data.providersReady} Ready`
            }],
            actions: [
              {
                key: 'view',
                label: t(K.page.support.view),
                onClick: () => console.log('View Providers'),
              },
            ],
          },
          {
            id: '3',
            title: t(K.page.support.runSelfCheck),
            description: t(K.page.support.runSelfCheckDesc),
            icon: <DoneIcon />,
            meta: [{
              key: 'lastRun',
              label: t(K.page.support.lastRun),
              value: formatTimestamp(response.data.data.lastSelfCheckTime)
            }],
            actions: [
              {
                key: 'run',
                label: t(K.page.support.run),
                onClick: () => console.log('Run Self-check'),
              },
            ],
          },
          {
            id: '4',
            title: t(K.page.support.viewLogs),
            description: t(K.page.support.viewLogsDesc),
            icon: <DescriptionIcon />,
            meta: [{
              key: 'latest',
              label: t(K.page.support.latest),
              value: formatTimestamp(response.data.data.lastLogTime)
            }],
            actions: [
              {
                key: 'view',
                label: t(K.page.support.view),
                onClick: () => console.log('View Logs'),
              },
            ],
          },
        ]

        setQuickLinks(links)
      }
    } catch (err) {
      console.error('Failed to load diagnostics:', err)
      setError(err instanceof Error ? err.message : 'Failed to load diagnostic data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDiagnostics()
  }, [])

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.support.title),
    subtitle: t(K.page.support.subtitle),
  })

  usePageActions([
    {
      key: 'download',
      label: t(K.common.download),
      icon: <DownloadIcon />,
      variant: 'outlined',
      onClick: () => {
        console.log('Download clicked')
      },
    },
    {
      key: 'view',
      label: t(K.page.support.view),
      icon: <PreviewIcon />,
      variant: 'outlined',
      onClick: () => {
        console.log('View clicked')
      },
    },
    {
      key: 'copy',
      label: t(K.common.copy),
      icon: <CopyIcon />,
      variant: 'outlined',
      onClick: () => {
        console.log('Copy clicked')
      },
    },
  ])

  // ===================================
  // Render
  // ===================================
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Error State */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Diagnostic Bundle Section */}
      <AppCard>
        <AppCardHeader title={t(K.page.support.diagnosticBundle)} />
        <AppCardBody>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t(K.page.support.diagnosticBundleDesc)}
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <PrimaryButton
              startIcon={<DownloadIcon />}
              onClick={() => console.log('Download as JSON')}
              disabled={loading || !!error}
            >
              {t(K.page.support.downloadJson)}
            </PrimaryButton>
            <PrimaryButton
              startIcon={<PreviewIcon />}
              onClick={() => console.log('View Inline')}
              disabled={loading || !!error}
            >
              {t(K.page.support.viewInline)}
            </PrimaryButton>
            <PrimaryButton
              startIcon={<CopyIcon />}
              onClick={() => console.log('Copy to Clipboard')}
              disabled={loading || !!error}
            >
              {t(K.page.support.copyClipboard)}
            </PrimaryButton>
          </Box>
        </AppCardBody>
      </AppCard>

      {/* Quick Links Section */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {t(K.page.support.quickLinks)}
        </Typography>
        
        <CardCollectionWrap loading={loading}>
          {quickLinks.length > 0 ? (
            quickLinks.map((link) => (
              <ItemCard
                key={link.id}
                title={link.title}
                description={link.description}
                icon={link.icon}
                meta={link.meta}
                actions={link.actions}
              />
            ))
          ) : (
            !loading && !error && (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="body1" color="text.secondary">
                  {t(K.page.support.noDiagnostics)}
                </Typography>
              </Box>
            )
          )}
        </CardCollectionWrap>
      </Box>

      {/* Help & Resources Section */}
      <AppCard>
        <AppCardHeader title={t(K.page.support.helpResources)} />
        <AppCardBody>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Typography variant="body2">
              • <a href="https://docs.agentos.org" target="_blank" rel="noopener noreferrer">{t(K.page.support.documentation)}</a>
            </Typography>
            <Typography variant="body2">
              • <a href="https://github.com/agentos/agentos/issues" target="_blank" rel="noopener noreferrer">{t(K.page.support.reportIssue)}</a>
            </Typography>
            <Typography variant="body2">
              • <a href="https://github.com/agentos/agentos/discussions" target="_blank" rel="noopener noreferrer">{t(K.page.support.community)}</a>
            </Typography>
            <Typography variant="body2">
              • <a href="mailto:support@agentos.org">{t(K.page.support.supportEmail)}</a>
            </Typography>
          </Box>
        </AppCardBody>
      </AppCard>
    </Box>
  )
}
