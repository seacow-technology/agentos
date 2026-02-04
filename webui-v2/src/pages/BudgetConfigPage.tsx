/**
 * BudgetConfigPage - 预算配置与监控
 *
 * Phase 6.1: V1 API Alignment
 * - API: systemService.listBudgetConfigs() -> GET /api/budget/global (V1 singleton)
 * - Displays global budget config as single card
 * - Edit form matches V1 structure: max_tokens, auto_derive, allocation breakdown
 * - States: Loading/Success/Error/Empty
 * - i18n: Full translation support
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { DashboardGrid, StatCard, MetricCard } from '@/ui'
import { TrendingUpIcon, AccountBalanceIcon, MemoryIcon } from '@/ui/icons'
import { K, useText } from '@/ui/text'
import { toast } from '@/ui/feedback'
import { DialogForm } from '@/ui/interaction'
import { TextField, Checkbox, FormControlLabel, Alert, Box, Typography } from '@/ui'
import { Grid } from '@mui/material'
import { systemService } from '@/services'
import type { BudgetConfig } from '@/services/system.service'

/**
 * BudgetConfigPage 组件
 *
 * 📊 Pattern: DashboardPage（DashboardGrid + StatCard/MetricCard）
 */
export default function BudgetConfigPage() {
  // ===================================
  // i18n Hook
  // ===================================
  const { t } = useText()

  // ===================================
  // State: API Data
  // ===================================
  const [budgetConfigs, setBudgetConfigs] = useState<BudgetConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // ===================================
  // State: Edit Dialog (V1 Fields)
  // ===================================
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [selectedConfig, setSelectedConfig] = useState<BudgetConfig | null>(null)
  const [maxTokens, setMaxTokens] = useState('')
  const [autoDerive, setAutoDerive] = useState(false)
  const [windowTokens, setWindowTokens] = useState('')
  const [ragTokens, setRagTokens] = useState('')
  const [memoryTokens, setMemoryTokens] = useState('')
  const [summaryTokens, setSummaryTokens] = useState('')
  const [systemTokens, setSystemTokens] = useState('')
  const [safetyMargin, setSafetyMargin] = useState('')
  const [generationMaxTokens, setGenerationMaxTokens] = useState('')
  const [updating, setUpdating] = useState(false)

  // ===================================
  // State: Validation Errors
  // ===================================
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [showPreview, setShowPreview] = useState(false)

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.budgetConfig.title),
    subtitle: t(K.page.budgetConfig.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: () => loadBudgetConfigs(),
    },
  ])

  // ===================================
  // API: Load Budget Configs
  // ===================================
  const loadBudgetConfigs = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await systemService.listBudgetConfigs()
      setBudgetConfigs(response.configs || [])
    } catch (err: any) {
      console.error('Failed to load budget configs:', err)
      setError(err.message || t(K.page.budgetConfig.loadError))
      toast.error(t(K.page.budgetConfig.loadError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBudgetConfigs()
  }, [])

  // ===================================
  // Validation: Validate Configuration
  // ===================================
  const validateConfiguration = (): string[] => {
    const errors: string[] = []

    // Required field validation
    if (!maxTokens.trim()) {
      errors.push(t(K.page.budgetConfig.errorMaxTokensRequired))
    }

    // Numeric validation
    const maxTokensNum = parseInt(maxTokens)
    if (isNaN(maxTokensNum) || maxTokensNum <= 0) {
      errors.push(t(K.page.budgetConfig.errorMaxTokensPositive))
    }

    // Validate allocation fields if provided
    if (windowTokens.trim()) {
      const num = parseInt(windowTokens)
      if (isNaN(num) || num < 0) {
        errors.push(t(K.page.budgetConfig.errorWindowTokensNonNegative))
      }
    }

    if (ragTokens.trim()) {
      const num = parseInt(ragTokens)
      if (isNaN(num) || num < 0) {
        errors.push(t(K.page.budgetConfig.errorRagTokensNonNegative))
      }
    }

    if (memoryTokens.trim()) {
      const num = parseInt(memoryTokens)
      if (isNaN(num) || num < 0) {
        errors.push(t(K.page.budgetConfig.errorMemoryTokensNonNegative))
      }
    }

    if (summaryTokens.trim()) {
      const num = parseInt(summaryTokens)
      if (isNaN(num) || num < 0) {
        errors.push(t(K.page.budgetConfig.errorSummaryTokensNonNegative))
      }
    }

    if (systemTokens.trim()) {
      const num = parseInt(systemTokens)
      if (isNaN(num) || num < 0) {
        errors.push(t(K.page.budgetConfig.errorSystemTokensNonNegative))
      }
    }

    // Safety margin validation
    if (safetyMargin.trim()) {
      const num = parseFloat(safetyMargin)
      if (isNaN(num) || num < 0 || num > 1) {
        errors.push(t(K.page.budgetConfig.errorSafetyMarginRange))
      }
    }

    // Generation max tokens validation
    if (generationMaxTokens.trim()) {
      const num = parseInt(generationMaxTokens)
      if (isNaN(num) || num <= 0) {
        errors.push(t(K.page.budgetConfig.errorGenerationMaxTokensPositive))
      }
    }

    // Cross-field validation: Total allocation should not exceed max tokens
    if (!isNaN(maxTokensNum) && maxTokensNum > 0) {
      const totalAllocation =
        (windowTokens ? parseInt(windowTokens) || 0 : 0) +
        (ragTokens ? parseInt(ragTokens) || 0 : 0) +
        (memoryTokens ? parseInt(memoryTokens) || 0 : 0) +
        (summaryTokens ? parseInt(summaryTokens) || 0 : 0) +
        (systemTokens ? parseInt(systemTokens) || 0 : 0)

      if (totalAllocation > maxTokensNum) {
        errors.push(t(K.page.budgetConfig.errorAllocationExceeds).replace('{total}', totalAllocation.toString()).replace('{max}', maxTokensNum.toString()))
      }
    }

    return errors
  }

  // ===================================
  // Handler: Preview Configuration
  // ===================================
  const handlePreviewConfig = () => {
    const errors = validateConfiguration()
    setValidationErrors(errors)

    if (errors.length === 0) {
      setShowPreview(true)
    } else {
      toast.error(t(K.page.budgetConfig.errorFixValidation))
    }
  }

  // ===================================
  // API: Update Budget Config (V1 Compatible)
  // ===================================
  const handleUpdateConfig = async () => {
    if (!selectedConfig) {
      toast.error(t(K.page.budgetConfig.errorNoConfigSelected))
      return
    }

    // Validate before saving
    const errors = validateConfiguration()
    if (errors.length > 0) {
      setValidationErrors(errors)
      toast.error(t(K.page.budgetConfig.fillRequired))
      return
    }

    setUpdating(true)
    setValidationErrors([])

    try {
      const updateData = {
        max_tokens: parseInt(maxTokens),
        auto_derive: autoDerive,
        window_tokens: windowTokens ? parseInt(windowTokens) : undefined,
        rag_tokens: ragTokens ? parseInt(ragTokens) : undefined,
        memory_tokens: memoryTokens ? parseInt(memoryTokens) : undefined,
        summary_tokens: summaryTokens ? parseInt(summaryTokens) : undefined,
        system_tokens: systemTokens ? parseInt(systemTokens) : undefined,
        safety_margin: safetyMargin ? parseFloat(safetyMargin) : undefined,
        generation_max_tokens: generationMaxTokens ? parseInt(generationMaxTokens) : undefined,
      }

      await systemService.updateBudgetConfig(selectedConfig.id, updateData)

      setEditDialogOpen(false)
      setSelectedConfig(null)
      setShowPreview(false)
      resetFormFields()
      toast.success(t(K.page.budgetConfig.updateSuccess))
      await loadBudgetConfigs()
    } catch (err: any) {
      console.error('Failed to update budget config:', err)
      const errorMessage = err.message || t(K.page.budgetConfig.updateError)
      toast.error(errorMessage)
      setValidationErrors([errorMessage])
    } finally {
      setUpdating(false)
    }
  }

  // ===================================
  // Handler: Open Edit Dialog (V1 Fields)
  // ===================================
  const handleEditConfig = (config: BudgetConfig) => {
    setSelectedConfig(config)
    setMaxTokens(config.max_tokens.toString())
    setAutoDerive(config.auto_derive)
    setWindowTokens(config.allocation.window_tokens.toString())
    setRagTokens(config.allocation.rag_tokens.toString())
    setMemoryTokens(config.allocation.memory_tokens.toString())
    setSummaryTokens(config.allocation.summary_tokens.toString())
    setSystemTokens(config.allocation.system_tokens.toString())
    setSafetyMargin(config.safety_margin.toString())
    setGenerationMaxTokens(config.generation_max_tokens.toString())
    setValidationErrors([])
    setShowPreview(false)
    setEditDialogOpen(true)
  }

  const resetFormFields = () => {
    setMaxTokens('')
    setAutoDerive(false)
    setWindowTokens('')
    setRagTokens('')
    setMemoryTokens('')
    setSummaryTokens('')
    setSystemTokens('')
    setSafetyMargin('')
    setGenerationMaxTokens('')
    setValidationErrors([])
    setShowPreview(false)
  }

  // ===================================
  // Handler: Close Dialog
  // ===================================
  const handleCloseDialog = () => {
    setEditDialogOpen(false)
    setSelectedConfig(null)
    resetFormFields()
  }

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
  // Render: Error State
  // ===================================
  if (error) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'error.main' }}>
        {error}
      </div>
    )
  }

  // ===================================
  // Render: Empty State
  // ===================================
  if (budgetConfigs.length === 0) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div>{t(K.page.budgetConfig.noConfigs)}</div>
        <div style={{ marginTop: '8px', color: 'text.secondary' }}>
          {t(K.page.budgetConfig.noConfigsDesc)}
        </div>
      </div>
    )
  }

  // ===================================
  // Calculate Statistics (V1 Compatible)
  // ===================================
  const globalConfig = budgetConfigs[0]
  const totalAllocation =
    globalConfig.allocation.window_tokens +
    globalConfig.allocation.rag_tokens +
    globalConfig.allocation.memory_tokens +
    globalConfig.allocation.summary_tokens +
    globalConfig.allocation.system_tokens

  const stats = [
    {
      title: t(K.page.budgetConfig.statMaxTokens),
      value: globalConfig.max_tokens.toLocaleString(),
      icon: <AccountBalanceIcon />,
      onClick: () => handleEditConfig(globalConfig),
    },
    {
      title: t(K.page.budgetConfig.statAutoDerive),
      value: globalConfig.auto_derive ? t(K.page.budgetConfig.valueEnabled) : t(K.page.budgetConfig.valueManual),
      icon: <TrendingUpIcon />,
      changeType: globalConfig.auto_derive ? 'increase' as const : undefined,
      onClick: () => handleEditConfig(globalConfig),
    },
    {
      title: t(K.page.budgetConfig.statTotalAllocation),
      value: totalAllocation.toLocaleString(),
      icon: <MemoryIcon />,
      onClick: () => handleEditConfig(globalConfig),
    },
  ]

  // ===================================
  // Render: Success State
  // ===================================
  return (
    <>
      <DashboardGrid columns={3} gap={16}>
        {/* Row 1: Stat Cards */}
        {stats.map((stat, index) => (
          <StatCard
            key={index}
            title={stat.title}
            value={stat.value}
            changeType={stat.changeType}
            icon={stat.icon}
            onClick={stat.onClick}
          />
        ))}

        {/* Row 2: Global Budget Config Card */}
        <MetricCard
          key={globalConfig.id}
          title={globalConfig.name}
          description={t(K.page.budgetConfig.globalConfigDesc)}
          metrics={[
            {
              key: 'max_tokens',
              label: t(K.page.budgetConfig.labelMaxTokens),
              value: globalConfig.max_tokens.toLocaleString(),
            },
            {
              key: 'window_tokens',
              label: t(K.page.budgetConfig.labelWindowTokens),
              value: globalConfig.allocation.window_tokens.toLocaleString(),
            },
            {
              key: 'rag_tokens',
              label: t(K.page.budgetConfig.labelRagTokens),
              value: globalConfig.allocation.rag_tokens.toLocaleString(),
            },
            {
              key: 'memory_tokens',
              label: t(K.page.budgetConfig.labelMemoryTokens),
              value: globalConfig.allocation.memory_tokens.toLocaleString(),
            },
            {
              key: 'summary_tokens',
              label: t(K.page.budgetConfig.labelSummaryTokens),
              value: globalConfig.allocation.summary_tokens.toLocaleString(),
            },
            {
              key: 'system_tokens',
              label: t(K.page.budgetConfig.labelSystemTokens),
              value: globalConfig.allocation.system_tokens.toLocaleString(),
            },
            {
              key: 'safety_margin',
              label: t(K.page.budgetConfig.labelSafetyMargin),
              value: `${(globalConfig.safety_margin * 100).toFixed(1)}%`,
            },
            {
              key: 'generation_max',
              label: t(K.page.budgetConfig.labelGenerationMax),
              value: globalConfig.generation_max_tokens.toLocaleString(),
            },
          ]}
          actions={[
            {
              key: 'edit',
              label: t(K.common.edit),
              onClick: () => handleEditConfig(globalConfig),
            },
          ]}
        />
      </DashboardGrid>

      {/* Edit Budget Config Dialog (V1 Structure) */}
      <DialogForm
        open={editDialogOpen}
        onClose={handleCloseDialog}
        title={t(K.page.budgetConfig.dialogTitle)}
        submitText={showPreview ? t(K.common.save) : t(K.page.budgetConfig.buttonPreviewSave)}
        cancelText={t(K.common.cancel)}
        onSubmit={showPreview ? handleUpdateConfig : handlePreviewConfig}
        submitDisabled={!maxTokens.trim() || updating}
      >
        <Grid container spacing={2}>
          {/* Validation Errors Alert */}
          {validationErrors.length > 0 && (
            <Grid item xs={12}>
              <Alert severity="error">
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                  {t(K.page.budgetConfig.validationErrorsTitle)}
                </Typography>
                <Box component="ul" sx={{ margin: 0, paddingLeft: 2 }}>
                  {validationErrors.map((error, index) => (
                    <li key={index}>
                      <Typography variant="body2">{error}</Typography>
                    </li>
                  ))}
                </Box>
              </Alert>
            </Grid>
          )}

          {/* Preview Summary */}
          {showPreview && validationErrors.length === 0 && (
            <Grid item xs={12}>
              <Alert severity="info">
                <Typography variant="body2" sx={{ fontWeight: 600, mb: 1 }}>
                  {t(K.page.budgetConfig.previewTitle)}
                </Typography>
                <Box component="ul" sx={{ margin: 0, paddingLeft: 2 }}>
                  <li>
                    <Typography variant="body2">
                      {t(K.page.budgetConfig.previewMaxTokens).replace('{value}', parseInt(maxTokens).toLocaleString())}
                    </Typography>
                  </li>
                  <li>
                    <Typography variant="body2">
                      {t(K.page.budgetConfig.previewAutoDerive).replace('{value}', autoDerive ? t(K.common.enabled) : t(K.common.disabled))}
                    </Typography>
                  </li>
                  <li>
                    <Typography variant="body2">
                      {t(K.page.budgetConfig.previewTotalAllocation).replace('{value}', (
                        (windowTokens ? parseInt(windowTokens) || 0 : 0) +
                        (ragTokens ? parseInt(ragTokens) || 0 : 0) +
                        (memoryTokens ? parseInt(memoryTokens) || 0 : 0) +
                        (summaryTokens ? parseInt(summaryTokens) || 0 : 0) +
                        (systemTokens ? parseInt(systemTokens) || 0 : 0)
                      ).toLocaleString())}
                    </Typography>
                  </li>
                  <li>
                    <Typography variant="body2">
                      {t(K.page.budgetConfig.previewSafetyMargin).replace('{value}', safetyMargin ? `${(parseFloat(safetyMargin) * 100).toFixed(1)}%` : t(K.page.budgetConfig.previewNotSet))}
                    </Typography>
                  </li>
                </Box>
              </Alert>
            </Grid>
          )}

          {/* Auto Derive Checkbox */}
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={autoDerive}
                  onChange={(e) => {
                    setAutoDerive(e.target.checked)
                    setShowPreview(false)
                  }}
                  disabled={updating}
                />
              }
              label={t(K.page.budgetConfig.fieldAutoDeriveLabel)}
            />
          </Grid>

          {/* Max Tokens - Required Field */}
          <Grid item xs={12}>
            <TextField
              label={t(K.page.budgetConfig.fieldMaxTokens)}
              placeholder={t(K.page.budgetConfig.fieldMaxTokensPlaceholder)}
              value={maxTokens}
              onChange={(e) => {
                setMaxTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              required
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelMaxTokens)))}
              helperText={t(K.page.budgetConfig.fieldMaxTokensHelper)}
            />
          </Grid>

          {/* Allocation Breakdown */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
              {t(K.page.budgetConfig.sectionAllocation)}
            </Typography>
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldWindowTokens)}
              placeholder={t(K.page.budgetConfig.fieldWindowTokensPlaceholder)}
              value={windowTokens}
              onChange={(e) => {
                setWindowTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelWindowTokens)))}
            />
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldRagTokens)}
              placeholder={t(K.page.budgetConfig.fieldRagTokensPlaceholder)}
              value={ragTokens}
              onChange={(e) => {
                setRagTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelRagTokens)))}
            />
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldMemoryTokens)}
              placeholder={t(K.page.budgetConfig.fieldMemoryTokensPlaceholder)}
              value={memoryTokens}
              onChange={(e) => {
                setMemoryTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelMemoryTokens)))}
            />
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldSummaryTokens)}
              placeholder={t(K.page.budgetConfig.fieldSummaryTokensPlaceholder)}
              value={summaryTokens}
              onChange={(e) => {
                setSummaryTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelSummaryTokens)))}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              label={t(K.page.budgetConfig.fieldSystemTokens)}
              placeholder={t(K.page.budgetConfig.fieldSystemTokensPlaceholder)}
              value={systemTokens}
              onChange={(e) => {
                setSystemTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelSystemTokens)))}
            />
          </Grid>

          {/* Other Settings */}
          <Grid item xs={12}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, mt: 1 }}>
              {t(K.page.budgetConfig.sectionAdvanced)}
            </Typography>
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldSafetyMargin)}
              placeholder={t(K.page.budgetConfig.fieldSafetyMarginPlaceholder)}
              value={safetyMargin}
              onChange={(e) => {
                setSafetyMargin(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              inputProps={{ step: '0.01', min: '0', max: '1' }}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelSafetyMargin)))}
              helperText={t(K.page.budgetConfig.fieldSafetyMarginHelper)}
            />
          </Grid>

          <Grid item xs={6}>
            <TextField
              label={t(K.page.budgetConfig.fieldGenerationMaxTokens)}
              placeholder={t(K.page.budgetConfig.fieldGenerationMaxTokensPlaceholder)}
              value={generationMaxTokens}
              onChange={(e) => {
                setGenerationMaxTokens(e.target.value)
                setShowPreview(false)
              }}
              fullWidth
              type="number"
              disabled={updating}
              error={validationErrors.some(err => err.includes(t(K.page.budgetConfig.labelGenerationMax)))}
            />
          </Grid>
        </Grid>
      </DialogForm>
    </>
  )
}
