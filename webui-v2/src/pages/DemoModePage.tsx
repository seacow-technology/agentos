/**
 * DemoModePage - 演示模式控制
 *
 * Phase 6: Real API Integration
 * - API: systemService.getDemoModeStatus(), toggleDemoMode()
 * - Pattern: StatusCard + Toggle Switch
 * - States: Loading/Success/Error
 * - i18n: Full translation support
 */

import { useState, useEffect } from 'react'
import { Box, Switch, FormControlLabel, Typography } from '@mui/material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { PlayIcon, StopIcon, InfoIcon } from '@/ui/icons'
import { systemService } from '@/services'

export default function DemoModePage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [demoModeEnabled, setDemoModeEnabled] = useState(false)

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.demoMode.title),
    subtitle: t(K.page.demoMode.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => loadDemoModeStatus(),
    },
  ])

  // ===================================
  // API: Load Demo Mode Status
  // ===================================
  const loadDemoModeStatus = async () => {
    setLoading(true)
    try {
      const response = await systemService.getDemoModeStatus()
      setDemoModeEnabled(response.demo_mode?.enabled || false)
    } catch (err: any) {
      console.error('Failed to load demo mode status:', err)
      toast.error(t(K.page.demoMode.loadError))
    } finally {
      setLoading(false)
    }
  }

  // ===================================
  // API: Toggle Demo Mode
  // ===================================
  const handleToggleDemoMode = async (enabled: boolean) => {
    try {
      if (enabled) {
        await systemService.enableDemoMode()
      } else {
        await systemService.disableDemoMode()
      }
      setDemoModeEnabled(enabled)
      toast.success(
        enabled
          ? t(K.page.demoMode.enabledSuccess)
          : t(K.page.demoMode.disabledSuccess)
      )
    } catch (err: any) {
      console.error('Failed to toggle demo mode:', err)
      toast.error(t(K.page.demoMode.toggleError))
      // Revert on error
      setDemoModeEnabled(!enabled)
    }
  }

  useEffect(() => {
    loadDemoModeStatus()
  }, [])

  // ===================================
  // Render: Loading State
  // ===================================
  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        {t(K.common.loading)}
      </div>
    )
  }

  // ===================================
  // Render: Success State
  // ===================================
  return (
    <Box>
      {/* Demo Mode Control */}
      <Box sx={{ mb: 3, p: 3, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
        <FormControlLabel
          control={
            <Switch
              checked={demoModeEnabled}
              onChange={(e) => handleToggleDemoMode(e.target.checked)}
              color="primary"
            />
          }
          label={
            <Box>
              <Typography variant="h6">
                {t(K.page.demoMode.toggleLabel)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {t(K.page.demoMode.toggleDescription)}
              </Typography>
            </Box>
          }
        />
      </Box>

      {/* Statistics */}
      <DashboardGrid columns={3} gap={16}>
        <StatCard
          title={t(K.page.demoMode.statusTitle)}
          value={demoModeEnabled ? t(K.page.skills.statusEnabled) : t(K.page.skills.statusDisabled)}
          icon={demoModeEnabled ? <PlayIcon /> : <StopIcon />}
        />
        <StatCard
          title={t(K.page.demoMode.dataSourceTitle)}
          value={demoModeEnabled ? t(K.page.demoMode.mockData) : t(K.page.demoMode.realData)}
          icon={<InfoIcon />}
        />
        <StatCard
          title={t(K.page.demoMode.performanceTitle)}
          value={demoModeEnabled ? t(K.page.demoMode.fast) : t(K.page.demoMode.normal)}
          icon={<InfoIcon />}
        />
      </DashboardGrid>
    </Box>
  )
}
