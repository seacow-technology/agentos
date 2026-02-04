/**
 * TrustTierPage - Trust Tier Management
 *
 * Phase 6: Real API Integration
 * 使用 networkosService.listTrustTiers()
 * CardCollectionWrap + StatusCard
 *
 * Features:
 * - Display trust tiers (T0-T3) with real API data
 * - Show risk levels, quotas, and capabilities per tier
 * - Detail drawer for tier information
 * - Full state handling (Loading, Success, Error, Empty)
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { StatusCard } from '@/ui/cards/StatusCard'
import { DetailDrawer } from '@/ui/interaction'
import { LoadingState, ErrorState, EmptyState } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { Button, Chip } from '@/ui'
// eslint-disable-next-line no-restricted-imports -- Box and Typography are allowed per G3
import { Box, Typography } from '@mui/material'
import { SecurityIcon, VerifiedIcon, LockIcon, RefreshIcon } from '@/ui/icons'
import { networkosService } from '@/services'
import type { TrustTierInfo } from '@/services/networkos.service'

/**
 * TrustTierPage Component
 *
 * Pattern: CardGridPage with API Integration
 * - Uses networkosService.listTrustTiers()
 * - CardCollectionWrap + StatusCard display
 * - DetailDrawer for tier details
 */
export default function TrustTierPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tiers, setTiers] = useState<TrustTierInfo[]>([])
  const [selectedTier, setSelectedTier] = useState<TrustTierInfo | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // ===================================
  // Data Fetching
  // ===================================
  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await networkosService.listTrustTiers()
      setTiers(response.tiers || [])
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t(K.page.trustTier.errorLoadData)
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ===================================
  // Page Header and Actions
  // ===================================
  usePageHeader({
    title: t(K.page.trustTier.title),
    subtitle: t(K.page.trustTier.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      icon: <RefreshIcon />,
      onClick: async () => {
        await loadData()
      },
    },
  ])

  // ===================================
  // Handlers
  // ===================================
  const handleCardClick = (tier: TrustTierInfo) => {
    setSelectedTier(tier)
    setDrawerOpen(true)
  }

  const handleViewEntities = (tier: TrustTierInfo) => {
    // View entities functionality will be added in future phase
    console.log('View entities for tier:', tier.name)
  }

  // ===================================
  // Helper Functions
  // ===================================
  const getTierIcon = (tier: string) => {
    if (tier === 'T0') return <SecurityIcon />
    if (tier === 'T1') return <VerifiedIcon />
    if (tier === 'T2') return <SecurityIcon />
    if (tier === 'T3') return <LockIcon />
    return <SecurityIcon />
  }

  const getRiskColor = (riskLevel: string): 'running' | 'warning' | 'error' | 'stopped' => {
    const colorMap: Record<string, 'running' | 'warning' | 'error' | 'stopped'> = {
      LOW: 'running',
      MED: 'warning',
      HIGH: 'warning',
      CRITICAL: 'error',
    }
    return colorMap[riskLevel] || 'warning'
  }

  const getRiskLabelKey = (riskLevel: string) => {
    const keyMap: Record<string, string> = {
      LOW: K.page.trustTier.riskLOW,
      MED: K.page.trustTier.riskMED,
      HIGH: K.page.trustTier.riskHIGH,
      CRITICAL: K.page.trustTier.riskCRITICAL,
    }
    return keyMap[riskLevel] || K.page.trustTier.riskMED
  }

  const formatQuota = (profile: TrustTierInfo['default_policy']['default_quota_profile']) => {
    if (!profile) return 'N/A'
    const cpm = profile.calls_per_minute || 0
    return `${cpm}/min`
  }

  const formatRuntime = (profile: TrustTierInfo['default_policy']['default_quota_profile']) => {
    if (!profile) return 'N/A'
    const ms = profile.max_runtime_ms || 0
    return `${(ms / 1000).toFixed(0)}s`
  }

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState message={t(K.page.trustTier.loadingMessage)} />
  }

  // ===================================
  // Error State
  // ===================================
  if (error) {
    return <ErrorState error={error} onRetry={loadData} />
  }

  // ===================================
  // Empty State
  // ===================================
  if (!tiers || tiers.length === 0) {
    return (
      <EmptyState
        /* eslint-disable-next-line react/jsx-no-literals */
        message={`${t(K.page.trustTier.emptyTitle)} - ${t(K.page.trustTier.emptyDescription)}`}
      />
    )
  }

  // ===================================
  // Render
  // ===================================
  return (
    <>
      {/* eslint-disable-next-line react/jsx-no-literals */}
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        {tiers.map((tier) => {
          const riskLevel = tier.default_policy?.risk_level || 'MED'

          return (
            <StatusCard
              key={tier.tier}
              title={tier.name}
              status={getRiskColor(riskLevel)}
              /* eslint-disable-next-line react/jsx-no-literals */
              statusLabel={`${t(K.page.trustTier.riskLabel)}: ${t(getRiskLabelKey(riskLevel))}`}
              /* eslint-disable-next-line react/jsx-no-literals */
              description={`${tier.count} ${t(K.page.trustTier.metaCapabilities)}`}
              meta={[
                {
                  key: 'quota',
                  label: t(K.page.trustTier.metaQuotaCalls),
                  value: formatQuota(tier.default_policy?.default_quota_profile),
                },
                {
                  key: 'admin',
                  label: t(K.page.trustTier.metaRequiresAdmin),
                  value: tier.default_policy?.requires_admin_token
                    ? t(K.page.trustTier.valueRequired)
                    : t(K.page.trustTier.valueNo),
                },
                {
                  key: 'concurrent',
                  label: t(K.page.trustTier.metaMaxConcurrent),
                  value: tier.default_policy?.default_quota_profile?.max_concurrent?.toString() || 'N/A',
                },
                {
                  key: 'runtime',
                  label: t(K.page.trustTier.metaMaxRuntime),
                  value: formatRuntime(tier.default_policy?.default_quota_profile),
                },
              ]}
              icon={getTierIcon(tier.tier)}
              actions={[
                {
                  key: 'details',
                  label: t(K.page.trustTier.actionDetails),
                  variant: 'outlined',
                  onClick: () => handleCardClick(tier),
                },
                {
                  key: 'entities',
                  label: t(K.page.trustTier.actionViewEntities),
                  variant: 'text',
                  onClick: () => handleViewEntities(tier),
                },
              ]}
              onClick={() => handleCardClick(tier)}
            />
          )
        })}
      </CardCollectionWrap>

      {/* Detail Drawer */}
      {/* eslint-disable react/jsx-no-literals */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedTier?.name || ''}
        actions={
          <>
            <Button
              variant="contained"
              color="primary"
              onClick={() => {
                if (selectedTier) {
                  handleViewEntities(selectedTier)
                }
              }}
            >
              {t(K.page.trustTier.actionViewEntities)}
            </Button>
            <Button
              variant="outlined"
              onClick={() => setDrawerOpen(false)}
            >
              {t('common.close')}
            </Button>
          </>
        }
      >
        {selectedTier && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Tier Info */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.tierId)}
              </Typography>
              <Typography variant="body1" fontWeight={500}>
                {selectedTier.tier}
              </Typography>
            </Box>

            {/* Risk Level */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.riskLabel)}
              </Typography>
              <Chip
                label={t(getRiskLabelKey(selectedTier.default_policy?.risk_level || 'MED'))}
                color={
                  getRiskColor(selectedTier.default_policy?.risk_level || 'MED') === 'error'
                    ? 'error'
                    : getRiskColor(selectedTier.default_policy?.risk_level || 'MED') === 'warning'
                    ? 'warning'
                    : 'success'
                }
                size="small"
              />
            </Box>

            {/* Capabilities Count */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.metaCapabilities)}
              </Typography>
              <Typography variant="body1">{selectedTier.count}</Typography>
            </Box>

            {/* Admin Token Required */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.metaRequiresAdmin)}
              </Typography>
              <Typography variant="body1">
                {selectedTier.default_policy?.requires_admin_token
                  ? t(K.page.trustTier.valueRequired)
                  : t(K.page.trustTier.valueNo)}
              </Typography>
            </Box>

            {/* Quota Profile */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.quotaProfile)}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, ml: 2 }}>
                <Typography variant="body2">
                  • {t(K.page.trustTier.metaQuotaCalls)}:{' '}
                  {formatQuota(selectedTier.default_policy?.default_quota_profile)}
                </Typography>
                <Typography variant="body2">
                  • {t(K.page.trustTier.metaMaxConcurrent)}:{' '}
                  {selectedTier.default_policy?.default_quota_profile?.max_concurrent || 'N/A'}
                </Typography>
                <Typography variant="body2">
                  • {t(K.page.trustTier.metaMaxRuntime)}:{' '}
                  {formatRuntime(selectedTier.default_policy?.default_quota_profile)}
                </Typography>
              </Box>
            </Box>

            {/* Capabilities List */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.trustTier.entities)} ({selectedTier.capabilities.length})
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {selectedTier.capabilities.length > 0 ? (
                  selectedTier.capabilities.slice(0, 10).map((capId) => (
                    <Chip key={capId} label={capId} size="small" variant="outlined" />
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {t(K.page.trustTier.noCapabilities)}
                  </Typography>
                )}
                {selectedTier.capabilities.length > 10 && (
                  <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                    {t(K.page.trustTier.andMore, { count: selectedTier.capabilities.length - 10 })}
                  </Typography>
                )}
              </Box>
            </Box>
          </Box>
        )}
      </DetailDrawer>
      {/* eslint-enable react/jsx-no-literals */}
    </>
  )
}
