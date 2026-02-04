/**
 * AuditLogPage - 审计日志页面
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ Table Contract: TableShell 三行结构（FilterBar/Content/Pagination）
 * - ✅ No Interaction: mock 数据，onClick 空函数（G12-G16）
 * - ✅ Unified Exit: 不自定义布局，使用 TableShell 封装
 */

import { useState, useEffect } from 'react'
import { TextField, Select, MenuItem, Box, Card, CardContent, Typography, Chip } from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import BlockIcon from '@mui/icons-material/Block'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { TableShell, FilterBar } from '@/ui'
import { useTextTranslation, K } from '@/ui/text'
import type { GridColDef } from '@/ui'
import { agentosService } from '@/services'

/**
 * Audit Log Type
 */
interface AuditLog {
  invocation_id: string
  agent_id: string
  capability_id: string
  operation: string
  allowed: boolean
  reason: string
  context: Record<string, unknown>
  timestamp: string
}

/**
 * Format timestamp to relative time
 */
function formatTimestamp(timestamp: string): string {
  if (!timestamp) return 'N/A';

  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  return date.toLocaleString();
}

/**
 * AuditLogPage 组件
 *
 * 📊 Pattern: TablePage（FilterBar + Table + Pagination）
 */
export default function AuditLogPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State - Four States + Filters
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [agentFilter, setAgentFilter] = useState('')
  const [capabilityFilter, setCapabilityFilter] = useState('')
  const [resultFilter, setResultFilter] = useState<string>('all')
  const [stats, setStats] = useState({ total: 0, allowed: 0, denied: 0, success_rate: 0 })
  const [pagination, setPagination] = useState({ limit: 100, offset: 0, has_more: false })

  // ===================================
  // Data Fetching - Real API
  // ===================================
  const reloadAuditLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await agentosService.getGovernanceAudit({
        agent_id: agentFilter || undefined,
        capability_id: capabilityFilter || undefined,
        allowed: resultFilter === 'all' ? undefined : resultFilter === 'allowed',
        limit: pagination.limit,
        offset: pagination.offset,
      })
      setAuditLogs(response.invocations)
      setStats(response.stats)
      setPagination(response.pagination)
    } catch (err) {
      console.error('Failed to fetch audit logs:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    reloadAuditLogs()
  }, [])

  // ===================================
  // Export to CSV
  // ===================================
  const exportToCSV = () => {
    if (auditLogs.length === 0) return;

    const headers = ['Invocation ID', 'Agent', 'Capability', 'Operation', 'Result', 'Reason', 'Timestamp'];
    const rows = auditLogs.map(inv => [
      inv.invocation_id,
      inv.agent_id,
      inv.capability_id,
      inv.operation,
      inv.allowed ? 'Allowed' : 'Denied',
      inv.reason || '',
      inv.timestamp
    ]);

    const csv = [headers, ...rows].map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `governance_audit_${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ===================================
  // Page Header (v2.4 API)
  // ===================================
  usePageHeader({
    title: t('page.auditLog.title'),
    subtitle: t('page.auditLog.subtitle'),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: reloadAuditLogs,
    },
    {
      key: 'export',
      label: t('common.export'),
      variant: 'contained',
      onClick: exportToCSV,
    },
  ])

  // ===================================
  // Table Columns Definition
  // ===================================
  const columns: GridColDef[] = [
    {
      field: 'invocation_id',
      headerName: 'Invocation ID',
      width: 200,
    },
    {
      field: 'agent_id',
      headerName: t('page.auditLog.columnAgent'),
      width: 150,
    },
    {
      field: 'capability_id',
      headerName: t('page.auditLog.columnCapability'),
      width: 200,
    },
    {
      field: 'operation',
      headerName: t('page.auditLog.columnOperation'),
      width: 150,
    },
    {
      field: 'allowed',
      headerName: t('page.auditLog.columnResult'),
      width: 120,
      renderCell: (params) => {
        const allowed = params.row.allowed;
        return (
          <Chip
            label={allowed ? 'Allowed' : 'Denied'}
            color={allowed ? 'success' : 'error'}
            size="small"
            icon={allowed ? <CheckCircleIcon /> : <BlockIcon />}
          />
        );
      },
    },
    {
      field: 'reason',
      headerName: t('page.auditLog.columnReason'),
      flex: 1,
      minWidth: 150,
      renderCell: (params) => {
        const reason = params.row.reason || 'N/A';
        const allowed = params.row.allowed;
        return (
          <Typography
            variant="body2"
            sx={{ color: allowed ? 'text.primary' : 'error.main' }}
          >
            {reason}
          </Typography>
        );
      },
    },
    {
      field: 'timestamp',
      headerName: t('page.auditLog.columnTimestamp'),
      width: 180,
      renderCell: (params) => formatTimestamp(params.row.timestamp),
    },
  ]

  // ===================================
  // Render: TableShell Pattern with Four States
  // ===================================
  if (error) {
    return (
      <TableShell
        loading={false}
        rows={[]}
        columns={columns}
        />
    )
  }

  return (
    <>
      {/* Stats Cards */}
      {stats.total > 0 && (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mb: 3 }}>
          <Card>
            <CardContent>
              <Typography variant="h4">{stats.total}</Typography>
              <Typography color="text.secondary">{t(K.page.auditLog.statTotalInvocations)}</Typography>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <Typography variant="h4" color="success.main">{stats.allowed}</Typography>
              <Typography color="text.secondary">{t(K.page.auditLog.statAllowed)}</Typography>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <Typography variant="h4" color="error.main">{stats.denied}</Typography>
              <Typography color="text.secondary">{t(K.page.auditLog.statDenied)}</Typography>
            </CardContent>
          </Card>
          <Card>
            <CardContent>
              <Typography variant="h4" color="primary.main">{stats.success_rate}%</Typography>
              <Typography color="text.secondary">{t(K.page.auditLog.statSuccessRate)}</Typography>
            </CardContent>
          </Card>
        </Box>
      )}

      <TableShell
        loading={loading}
        rows={auditLogs}
        columns={columns}
        filterBar={
          <FilterBar
            filters={[
              {
                width: 4,
                component: (
                  <TextField
                    label={t(K.page.auditLog.filterAgent)}
                    placeholder={t(K.page.auditLog.agentIdPlaceholder)}
                    fullWidth
                    size="small"
                    value={agentFilter}
                    onChange={(e) => setAgentFilter(e.target.value)}
                  />
                ),
              },
              {
                width: 4,
                component: (
                  <TextField
                    label={t(K.page.auditLog.filterCapability)}
                    placeholder={t(K.page.auditLog.capabilityIdPlaceholder)}
                    fullWidth
                    size="small"
                    value={capabilityFilter}
                    onChange={(e) => setCapabilityFilter(e.target.value)}
                  />
                ),
              },
              {
                width: 4,
                component: (
                  <Select
                    label={t(K.page.auditLog.filterResult)}
                    fullWidth
                    size="small"
                    value={resultFilter}
                    onChange={(e) => setResultFilter(e.target.value)}
                  >
                    <MenuItem value="all">{t(K.common.all)}</MenuItem>
                    <MenuItem value="allowed">{t(K.page.auditLog.statAllowed)}</MenuItem>
                    <MenuItem value="denied">{t(K.page.auditLog.statDenied)}</MenuItem>
                  </Select>
                ),
              },
            ]}
            actions={[
              {
                key: 'reset',
                label: t('common.reset'),
                onClick: () => {
                  setAgentFilter('');
                  setCapabilityFilter('');
                  setResultFilter('all');
                  setPagination({ ...pagination, offset: 0 });
                  reloadAuditLogs();
                },
              },
              {
                key: 'apply',
                label: t('common.apply'),
                variant: 'contained',
                onClick: () => {
                  setPagination({ ...pagination, offset: 0 });
                  reloadAuditLogs();
                },
              },
            ]}
          />
        }
        emptyState={{
          title: t('page.auditLog.noLogs'),
          description: t('page.auditLog.noLogsDesc'),
          actions: [
            {
              label: t('common.refresh'),
              onClick: reloadAuditLogs,
              variant: 'contained',
            },
          ],
        }}
        pagination={{
          page: Math.floor(pagination.offset / pagination.limit),
          pageSize: pagination.limit,
          total: stats.total,
          onPageChange: (newPage: number) => {
            const newOffset = newPage * pagination.limit;
            setPagination({ ...pagination, offset: newOffset });
            reloadAuditLogs();
          },
        }}
        onRowClick={(row) => {
          console.log('Audit log row clicked:', row)
        }}
      />
    </>
  )
}
