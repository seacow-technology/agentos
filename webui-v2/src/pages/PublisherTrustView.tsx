/**
 * PublisherTrustView - Publisher Trust Management
 *
 * Phase 6: Real API Integration
 *
 * Contract compliance:
 * - ✅ Text System: t(K.page.publisherTrust.xxx) for all text (G7-G8)
 * - ✅ Layout: usePageHeader + usePageActions (G10-G11)
 * - ✅ TableShell Pattern: TableShell for publisher list
 * - ✅ API Integration: networkosService.listPublishers + DetailDrawer
 * - ✅ State Management: Loading, Success, Error, Empty states
 */

import { useState, useEffect, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell } from '@/ui/table'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { t, K } from '@/ui/text'
import { toast } from '@/ui/feedback'
import type { GridColDef } from '@/ui'
import {
  Box,
  Typography,
  Chip,
  Alert,
  Button,
  IconButton,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import VisibilityIcon from '@mui/icons-material/Visibility'
import TuneIcon from '@mui/icons-material/Tune'
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser'
import ShieldIcon from '@mui/icons-material/Shield'
import WarningIcon from '@mui/icons-material/Warning'
import BlockIcon from '@mui/icons-material/Block'
import {
  networkosService,
  type Publisher,
  type PublisherDetail,
} from '@/services/networkos.service'

// Constants for MUI prop values
const SIZE_SMALL = 'small' as const
const VARIANT_H6 = 'h6' as const
const VARIANT_BODY1 = 'body1' as const
const VARIANT_BODY2 = 'body2' as const
const VARIANT_CAPTION = 'caption' as const
const COLOR_TEXT_SECONDARY = 'text.secondary' as const

export default function PublisherTrustView() {
  // ===================================
  // State Management
  // ===================================
  const [publishers, setPublishers] = useState<Publisher[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPublisher, setSelectedPublisher] = useState<PublisherDetail | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [sortBy] = useState('trust_score')
  const [order] = useState<'asc' | 'desc'>('desc')

  // ===================================
  // API Integration - List Publishers
  // ===================================
  const loadPublishers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await networkosService.listPublishers({
        sort_by: sortBy,
        order,
      })
      // Add id field for DataGrid (using publisher_id)
      const publishersWithId = (response.publishers || []).map(pub => ({
        ...pub,
        id: pub.publisher_id,
      }))
      setPublishers(publishersWithId)
    } catch (err) {
      console.error('Failed to load publishers:', err)
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      toast.error(t(K.page.publisherTrust.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [sortBy, order])

  useEffect(() => {
    loadPublishers()
  }, [loadPublishers])

  // ===================================
  // View Publisher Details Action
  // ===================================
  const handleViewPublisher = async (publisher: Publisher) => {
    try {
      const response = await networkosService.getPublisher(publisher.publisher_id)
      setSelectedPublisher(response.publisher)
      setDetailDrawerOpen(true)
    } catch (err) {
      console.error('Failed to load publisher details:', err)
      toast.error(t(K.common.error))
    }
  }

  const handleCloseDetailDrawer = () => {
    setDetailDrawerOpen(false)
    setSelectedPublisher(null)
  }

  // ===================================
  // Adjust Trust Action
  // ===================================
  const handleAdjustTrust = async (publisherId: string) => {
    try {
      await networkosService.updatePublisherTrust(publisherId)
      toast.success(t(K.page.publisherTrust.updateSuccess))
      // Refresh list
      await loadPublishers()
      // Close drawer if open
      if (detailDrawerOpen) {
        handleCloseDetailDrawer()
      }
    } catch (err) {
      console.error('Failed to update publisher trust:', err)
      toast.error(t(K.page.publisherTrust.updateFailed))
    }
  }

  // ===================================
  // Helper Functions
  // ===================================
  const getTrustLevelColor = (level: string): 'success' | 'info' | 'warning' | 'error' | 'default' => {
    switch (level) {
      case 'verified':
        return 'success'
      case 'trusted':
        return 'info'
      case 'unverified':
        return 'warning'
      case 'suspended':
        return 'error'
      default:
        return 'default'
    }
  }

  const getTrustLevelIcon = (level: string) => {
    switch (level) {
      case 'verified':
        return <VerifiedUserIcon fontSize={SIZE_SMALL} />
      case 'trusted':
        return <ShieldIcon fontSize={SIZE_SMALL} />
      case 'unverified':
        return <WarningIcon fontSize={SIZE_SMALL} />
      case 'suspended':
        return <BlockIcon fontSize={SIZE_SMALL} />
      default:
        return null
    }
  }

  const getTrustLevelLabel = (level: string) => {
    switch (level) {
      case 'verified':
        return t(K.page.publisherTrust.trustVerified)
      case 'trusted':
        return t(K.page.publisherTrust.trustTrusted)
      case 'unverified':
        return t(K.page.publisherTrust.trustUnverified)
      case 'suspended':
        return t(K.page.publisherTrust.trustSuspended)
      default:
        return level
    }
  }

  // ===================================
  // Page Header & Actions
  // ===================================
  usePageHeader({
    title: t(K.page.publisherTrust.title),
    subtitle: t(K.page.publisherTrust.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      icon: <RefreshIcon />,
      onClick: loadPublishers,
    },
  ])

  // ===================================
  // Table Configuration
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: t(K.page.publisherTrust.name),
      width: 200,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {getTrustLevelIcon(params.row.trust_level)}
          <Typography variant={VARIANT_BODY2}>{params.value}</Typography>
        </Box>
      ),
    },
    {
      field: 'trust_level',
      headerName: t(K.page.publisherTrust.trustLevel),
      width: 150,
      renderCell: (params) => (
        <Chip
          label={getTrustLevelLabel(params.value)}
          color={getTrustLevelColor(params.value)}
          size={SIZE_SMALL}
        />
      ),
    },
    {
      field: 'trust_score',
      headerName: t(K.page.publisherTrust.trustScore),
      width: 120,
      type: 'number',
      renderCell: (params) => `${params.value.toFixed(1)}%`,
    },
    {
      field: 'capability_count',
      headerName: t(K.page.publisherTrust.capabilitiesCount),
      width: 120,
      type: 'number',
    },
    {
      field: 'success_rate',
      headerName: t(K.page.publisherTrust.successRate),
      width: 120,
      type: 'number',
      renderCell: (params) => `${params.value.toFixed(1)}%`,
    },
    {
      field: 'last_activity_at',
      headerName: t(K.page.publisherTrust.lastActivityAt),
      width: 180,
      renderCell: (params) => new Date(params.value).toLocaleString(),
    },
    {
      field: 'actions',
      headerName: '',
      width: 120,
      sortable: false,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton
            size={SIZE_SMALL}
            onClick={() => handleViewPublisher(params.row)}
            title={t(K.page.publisherTrust.viewDetails)}
          >
            <VisibilityIcon fontSize={SIZE_SMALL} />
          </IconButton>
          <IconButton
            size={SIZE_SMALL}
            onClick={() => handleAdjustTrust(params.row.publisher_id)}
            title={t(K.page.publisherTrust.adjustTrust)}
          >
            <TuneIcon fontSize={SIZE_SMALL} />
          </IconButton>
        </Box>
      ),
    },
  ]

  // ===================================
  // Render: Error State
  // ===================================
  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="contained" onClick={loadPublishers}>
          {t(K.common.refresh)}
        </Button>
      </Box>
    )
  }

  // ===================================
  // Render: Empty State
  // ===================================
  if (!loading && publishers.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant={VARIANT_H6} gutterBottom>
          {t(K.page.publisherTrust.emptyTitle)}
        </Typography>
        <Typography variant={VARIANT_BODY1} color={COLOR_TEXT_SECONDARY} gutterBottom>
          {t(K.page.publisherTrust.emptyDescription)}
        </Typography>
        <Button variant="contained" onClick={loadPublishers} startIcon={<RefreshIcon />}>
          {t(K.common.refresh)}
        </Button>
      </Box>
    )
  }

  // ===================================
  // Render: Main Content
  // ===================================
  return (
    <>
      <TableShell
        columns={columns}
        rows={publishers}
        loading={loading}
      />

      {/* Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleCloseDetailDrawer}
        title={selectedPublisher?.name || ''}
        subtitle={t(K.page.publisherTrust.viewDetails)}
      >
        {selectedPublisher && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Trust Level */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.trustLevel)}
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                <Chip
                  label={getTrustLevelLabel(selectedPublisher.trust_level)}
                  color={getTrustLevelColor(selectedPublisher.trust_level)}
                  icon={getTrustLevelIcon(selectedPublisher.trust_level) || undefined}
                />
              </Box>
            </Box>

            {/* Trust Score */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.trustScore)}
              </Typography>
              <Typography variant={VARIANT_H6}>
                {selectedPublisher.trust_score.toFixed(1)}%
              </Typography>
            </Box>

            {/* Statistics */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.executions)}
              </Typography>
              <Box sx={{ mt: 0.5, display: 'flex', gap: 2 }}>
                <Box>
                  <Typography variant={VARIANT_BODY2}>
                    {t(K.page.publisherTrust.successful)}: {selectedPublisher.successful_executions}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant={VARIANT_BODY2}>
                    {t(K.page.publisherTrust.failed)}: {selectedPublisher.failed_executions}
                  </Typography>
                </Box>
              </Box>
            </Box>

            {/* Success Rate */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.successRate)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>
                {selectedPublisher.success_rate.toFixed(1)}%
              </Typography>
            </Box>

            {/* Average Risk Score */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.avgRiskScore)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>
                {selectedPublisher.average_risk_score.toFixed(1)}
              </Typography>
            </Box>

            {/* Capabilities Count */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                {t(K.page.publisherTrust.capabilitiesCount)}
              </Typography>
              <Typography variant={VARIANT_BODY1}>
                {selectedPublisher.capability_count}
              </Typography>
            </Box>

            {/* Action Button */}
            <Box sx={{ mt: 2 }}>
              <Button
                variant="contained"
                fullWidth
                onClick={() => handleAdjustTrust(selectedPublisher.publisher_id)}
                startIcon={<TuneIcon />}
              >
                {t(K.page.publisherTrust.adjustTrust)}
              </Button>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
