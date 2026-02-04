/**
 * PolicyEditorPage - 策略编辑器页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.page.policyEditor.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构
 * - ✅ Phase 4 Integration: 添加 DialogForm for inline policy editing
 * - ✅ Unified Exit: TableShell 封装
 * - ✅ Phase 6 API Integration: Real API calls
 */

import { useState, useEffect, useCallback } from 'react'
import { Box, Typography } from '@/ui'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar, TextField, Select, MenuItem } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DialogForm, DeleteConfirmDialog } from '@/ui/interaction'
import { toast } from '@/ui/feedback'
import { networkosService } from '@/services/networkos.service'
import type { GridColDef } from '@/ui'
import type { ExecutionPolicy } from '@/services/networkos.service'

// ===================================
// Constants
// ===================================

const TEXTFIELD_SIZE = 'small'
const FILTER_ALL = 'all'
const POLICY_TYPE_AGENT = 'agent'
const POLICY_TYPE_SECURITY = 'security'
const POLICY_TYPE_PRIVACY = 'privacy'
const POLICY_TYPE_RATE_LIMIT = 'rate-limit'
const POLICY_TYPE_ENVIRONMENT = 'environment'
const POLICY_TYPE_EMERGENCY = 'emergency'

// ===================================
// Types
// ===================================

interface PolicyRow {
  id: string
  name: string
  description: string
  type: string
  status: string
  enabled: boolean
  rules: Record<string, unknown>
}

/**
 * 数据转换函数：ExecutionPolicy → PolicyRow
 */
function policyToRow(policy: ExecutionPolicy): PolicyRow {
  return {
    id: policy.id,
    name: policy.name,
    description: `Policy Type: ${policy.policy_type}`,
    type: policy.policy_type,
    status: policy.enabled ? 'Active' : 'Inactive',
    enabled: policy.enabled,
    rules: policy.rules,
  }
}

// Mock data removed - Phase 6 uses real API from networkosService

/**
 * PolicyEditorPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 * 🎨 8列表格 + Inline Policy Editor (DialogForm)
 * 🔌 Phase 6: Real API Integration
 */
export default function PolicyEditorPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Data & Loading
  // ===================================
  const [policies, setPolicies] = useState<PolicyRow[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState(FILTER_ALL)

  // ===================================
  // Phase 4 Integration - Policy Editor State
  // ===================================
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyRow | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [editedPolicyJson, setEditedPolicyJson] = useState('')
  const [validationError, setValidationError] = useState('')
  const [policyName, setPolicyName] = useState('')
  const [policyType, setPolicyType] = useState('')

  // ===================================
  // Phase 6 API Integration - Load Policies
  // ===================================
  const loadPolicies = useCallback(async () => {
    setLoading(true)
    try {
      const response = await networkosService.listExecutionPolicies()
      const rows = response.policies.map(policyToRow)
      setPolicies(rows)
    } catch (error) {
      console.error('Failed to load policies:', error)
      toast.error(t(K.page.policyEditor.loadFailed))
      // Fallback to empty array on error
      setPolicies([])
    } finally {
      setLoading(false)
    }
  }, [t])

  // Load policies on mount
  useEffect(() => {
    loadPolicies()
  }, [loadPolicies])

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t(K.page.policyEditor.title),
    subtitle: t(K.page.policyEditor.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: async () => {
        await loadPolicies()
      },
    },
    {
      key: 'create',
      label: t(K.page.policyEditor.addPolicy),
      variant: 'contained',
      onClick: () => {
        setSelectedPolicy(null)
        setPolicyName('')
        setPolicyType(POLICY_TYPE_AGENT)
        setEditedPolicyJson(
          JSON.stringify(
            {
              example: 'new policy',
            },
            null,
            2
          )
        )
        setValidationError('')
        setEditorOpen(true)
      },
    },
  ])

  // ===================================
  // Phase 4 Integration - Handlers with Phase 6 API Integration
  // ===================================
  const handleRowClick = (row: PolicyRow) => {
    setSelectedPolicy(row)
    setPolicyName(row.name)
    setPolicyType(row.type)
    setEditedPolicyJson(JSON.stringify(row.rules, null, 2))
    setValidationError('')
    setEditorOpen(true)
  }

  const handleSavePolicy = async () => {
    // Validate JSON
    let parsedRules: Record<string, unknown>
    try {
      parsedRules = JSON.parse(editedPolicyJson)
      setValidationError('')
    } catch (e) {
      setValidationError(t(K.page.policyEditor.invalidJson))
      return
    }

    // Phase 6 API Integration - Create or Update
    try {
      if (selectedPolicy) {
        // Update existing policy
        await networkosService.updateExecutionPolicy(selectedPolicy.id, {
          name: policyName,
          policy_type: policyType,
          rules: parsedRules,
          enabled: selectedPolicy.enabled,
        })
        toast.success(t(K.page.policyEditor.updateSuccess))
      } else {
        // Create new policy
        if (!policyName.trim()) {
          setValidationError(t(K.page.policyEditor.policyNameRequired))
          return
        }
        await networkosService.createExecutionPolicy({
          name: policyName,
          policy_type: policyType,
          rules: parsedRules,
        })
        toast.success(t(K.page.policyEditor.createSuccess))
      }
      setEditorOpen(false)
      await loadPolicies() // Reload policies
    } catch (error) {
      console.error('Failed to save policy:', error)
      toast.error(
        selectedPolicy
          ? t(K.page.policyEditor.updateFailed)
          : t(K.page.policyEditor.createFailed)
      )
    }
  }

  const handleDelete = async () => {
    if (!selectedPolicy) return

    // Phase 6 API Integration - Delete
    try {
      await networkosService.deleteExecutionPolicy(selectedPolicy.id)
      toast.success(t(K.page.policyEditor.deleteSuccess))
      setDeleteDialogOpen(false)
      setEditorOpen(false)
      await loadPolicies() // Reload policies
    } catch (error) {
      console.error('Failed to delete policy:', error)
      toast.error(t(K.page.policyEditor.deleteFailed))
    }
  }

  // ===================================
  // Table Columns Definition (5列 - Phase 6)
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'ID',
      width: 200,
    },
    {
      field: 'name',
      headerName: t(K.page.policyEditor.name),
      flex: 1,
      minWidth: 200,
    },
    {
      field: 'type',
      headerName: t(K.page.policyEditor.type),
      width: 150,
    },
    {
      field: 'status',
      headerName: t(K.page.policyEditor.status),
      width: 120,
    },
    {
      field: 'description',
      headerName: t(K.page.policyEditor.description),
      flex: 1,
      minWidth: 250,
    },
  ]

  // ===================================
  // Render: TableShell Pattern + Phase 4 Interactions + Phase 6 API
  // ===================================
  return (
    <>
      <TableShell
        loading={loading}
        rows={policies}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 6,
                component: (
                  <TextField
                    label={t(K.common.search)}
                    placeholder={t(K.form.placeholder.search)}
                    fullWidth
                    size={TEXTFIELD_SIZE}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                ),
              },
              {
                width: 6,
                component: (
                  <Select
                    fullWidth
                    size={TEXTFIELD_SIZE}
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    displayEmpty
                  >
                    <MenuItem value={FILTER_ALL}>{t(K.page.policyEditor.allTypes)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_AGENT}>{t(K.page.policyEditor.typeAgent)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_SECURITY}>{t(K.page.policyEditor.typeSecurity)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_PRIVACY}>{t(K.page.policyEditor.typePrivacy)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_RATE_LIMIT}>{t(K.page.policyEditor.typeRateLimit)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_ENVIRONMENT}>{t(K.page.policyEditor.typeEnvironment)}</MenuItem>
                    <MenuItem value={POLICY_TYPE_EMERGENCY}>{t(K.page.policyEditor.typeEmergency)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t(K.common.reset),
                onClick: () => {
                  setSearchQuery('')
                  setTypeFilter(FILTER_ALL)
                },
              },
              {
                key: 'apply',
                label: t(K.common.apply),
                variant: 'contained',
                onClick: () => {
                  loadPolicies()
                  toast.info(t(K.common.apply))
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t(K.page.policyEditor.noPolicies),
          description: t(K.page.policyEditor.noPoliciesDesc),
          actions: [
            {
              label: t(K.page.policyEditor.addPolicy),
              onClick: () => {
                setSelectedPolicy(null)
                setPolicyName('')
                setPolicyType(POLICY_TYPE_AGENT)
                setEditedPolicyJson(
                  JSON.stringify(
                    {
                      example: 'new policy',
                    },
                    null,
                    2
                  )
                )
                setValidationError('')
                setEditorOpen(true)
              },
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page: 0,
          pageSize: 25,
          total: policies.length,
          onPageChange: () => {},
        }}
        onRowClick={handleRowClick}
      />

      {/* Inline Policy Editor - Phase 4 Integration (P1-17) */}
      <DialogForm
        open={editorOpen}
        onClose={() => setEditorOpen(false)}
        title={
          selectedPolicy
            ? t(K.page.policyEditor.editPolicy)
            : t(K.page.policyEditor.createPolicy)
        }
        submitText={t(K.common.save)}
        cancelText={t(K.common.cancel)}
        onSubmit={handleSavePolicy}
        maxWidth="md"
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Policy Name - Editable for both create and edit */}
          <TextField
            label={t(K.page.policyEditor.policyName)}
            value={policyName}
            onChange={(e) => setPolicyName(e.target.value)}
            fullWidth
            required
            size={TEXTFIELD_SIZE}
          />

          {/* Policy Type - Editable for both create and edit */}
          <Select
            value={policyType}
            onChange={(e) => setPolicyType(e.target.value)}
            fullWidth
            size={TEXTFIELD_SIZE}
            displayEmpty
          >
            <MenuItem value={POLICY_TYPE_AGENT}>{t(K.page.policyEditor.typeAgent)}</MenuItem>
            <MenuItem value={POLICY_TYPE_SECURITY}>{t(K.page.policyEditor.typeSecurity)}</MenuItem>
            <MenuItem value={POLICY_TYPE_PRIVACY}>{t(K.page.policyEditor.typePrivacy)}</MenuItem>
            <MenuItem value={POLICY_TYPE_RATE_LIMIT}>{t(K.page.policyEditor.typeRateLimit)}</MenuItem>
            <MenuItem value={POLICY_TYPE_ENVIRONMENT}>{t(K.page.policyEditor.typeEnvironment)}</MenuItem>
            <MenuItem value={POLICY_TYPE_EMERGENCY}>{t(K.page.policyEditor.typeEmergency)}</MenuItem>
          </Select>

          {/* Policy JSON Editor */}
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {t(K.page.policyEditor.policyJson)}
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={16}
              value={editedPolicyJson}
              onChange={(e) => {
                setEditedPolicyJson(e.target.value)
                setValidationError('')
              }}
              error={!!validationError}
              helperText={validationError}
              placeholder={t(K.page.policyEditor.jsonPlaceholder)}
              sx={{
                fontFamily: 'monospace',
                '& .MuiInputBase-input': {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                },
              }}
            />
          </Box>

          {/* Validation Hint */}
          {!validationError && (
            <Typography variant="caption" color="text.secondary">
              {t(K.page.policyEditor.validationHint)}
            </Typography>
          )}

          {/* Delete Button (for edit mode only) */}
          {selectedPolicy && (
            <Box sx={{ pt: 1, borderTop: 1, borderColor: 'divider' }}>
              <Typography
                variant="body2"
                color="error"
                sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                onClick={() => {
                  setEditorOpen(false)
                  setDeleteDialogOpen(true)
                }}
              >
                {t(K.page.policyEditor.deletePolicy)}
              </Typography>
            </Box>
          )}
        </Box>
      </DialogForm>

      {/* Delete Confirm Dialog - Phase 4 Integration */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType="Policy"
        resourceName={selectedPolicy?.name}
      />
    </>
  )
}
