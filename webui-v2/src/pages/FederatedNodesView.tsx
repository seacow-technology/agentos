/**
 * FederatedNodesView - Federated Nodes Management
 *
 * Phase 6: Real API Integration
 * 使用 networkosService.listFederatedNodes()
 * CardCollectionWrap + StatusCard
 *
 * Features:
 * - Display federated nodes with real API data
 * - Show node status, address, trust level, last heartbeat
 * - Connect/disconnect node actions
 * - Detail drawer for node information
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
import { CloudIcon, RefreshIcon, LinkIcon, CheckCircleIcon } from '@/ui/icons'
import { networkosService } from '@/services'
import type { FederatedNode } from '@/services/networkos.service'

/**
 * FederatedNodesView Component
 *
 * Pattern: CardGridPage with API Integration
 * - Uses networkosService.listFederatedNodes()
 * - CardCollectionWrap + StatusCard display
 * - DetailDrawer for node details
 */
export default function FederatedNodesView() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nodes, setNodes] = useState<FederatedNode[]>([])
  const [selectedNode, setSelectedNode] = useState<FederatedNode | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // ===================================
  // Data Fetching
  // ===================================
  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await networkosService.listFederatedNodes()
      setNodes(response.nodes || [])
      if (response.nodes && response.nodes.length > 0) {
        toast.success(t(K.page.federatedNodes.loadSuccess))
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t(K.page.federatedNodes.loadFailed)
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
    title: t(K.page.federatedNodes.title),
    subtitle: t(K.page.federatedNodes.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      icon: <RefreshIcon />,
      onClick: async () => {
        await loadData()
        toast.success(t(K.page.federatedNodes.refresh))
      },
    },
  ])

  // ===================================
  // Handlers
  // ===================================
  const handleCardClick = (node: FederatedNode) => {
    setSelectedNode(node)
    setDrawerOpen(true)
  }

  const handleConnect = async (node: FederatedNode) => {
    try {
      setActionLoading(true)
      await networkosService.connectNode(node.id, { address: node.address })
      toast.success(t(K.page.federatedNodes.connectSuccess))
      await loadData()
      // Update selected node if drawer is open
      if (selectedNode?.id === node.id) {
        const updatedNode = nodes.find(n => n.id === node.id)
        if (updatedNode) {
          setSelectedNode(updatedNode)
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t(K.page.federatedNodes.connectFailed)
      toast.error(errorMessage)
    } finally {
      setActionLoading(false)
    }
  }

  const handleDisconnect = async (node: FederatedNode) => {
    try {
      setActionLoading(true)
      await networkosService.disconnectNode(node.id)
      toast.success(t(K.page.federatedNodes.disconnectSuccess))
      await loadData()
      // Update selected node if drawer is open
      if (selectedNode?.id === node.id) {
        const updatedNode = nodes.find(n => n.id === node.id)
        if (updatedNode) {
          setSelectedNode(updatedNode)
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : t(K.page.federatedNodes.disconnectFailed)
      toast.error(errorMessage)
    } finally {
      setActionLoading(false)
    }
  }

  // ===================================
  // Helper Functions
  // ===================================
  const getNodeIcon = (status: FederatedNode['status']) => {
    if (status === 'connected') return <CheckCircleIcon />
    if (status === 'disconnected') return <CloudIcon />
    if (status === 'pending') return <LinkIcon />
    return <CloudIcon />
  }

  const getStatusColor = (status: FederatedNode['status']): 'running' | 'warning' | 'error' | 'stopped' => {
    const colorMap: Record<FederatedNode['status'], 'running' | 'warning' | 'error' | 'stopped'> = {
      connected: 'running',
      disconnected: 'stopped',
      pending: 'warning',
      error: 'error',
    }
    return colorMap[status] || 'stopped'
  }

  const getStatusLabelKey = (status: FederatedNode['status']) => {
    const keyMap: Record<FederatedNode['status'], string> = {
      connected: K.page.federatedNodes.statusConnected,
      disconnected: K.page.federatedNodes.statusDisconnected,
      pending: K.page.federatedNodes.statusPending,
      error: K.page.federatedNodes.statusError,
    }
    return keyMap[status] || K.page.federatedNodes.statusDisconnected
  }

  const formatTrustLevel = (level: number) => {
    return `${(level * 100).toFixed(0)}%`
  }

  const formatHeartbeat = (heartbeat?: string) => {
    if (!heartbeat) return t(K.page.federatedNodes.noHeartbeat)
    return heartbeat
  }

  // ===================================
  // Loading State
  // ===================================
  if (loading) {
    return <LoadingState message={t(K.page.federatedNodes.loadingMessage)} />
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
  if (!nodes || nodes.length === 0) {
    return (
      <EmptyState
        /* eslint-disable-next-line react/jsx-no-literals */
        message={`${t(K.page.federatedNodes.emptyTitle)} - ${t(K.page.federatedNodes.emptyDescription)}`}
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
        {nodes.map((node) => {
          const isConnected = node.status === 'connected'

          return (
            <StatusCard
              key={node.id}
              title={node.name}
              status={getStatusColor(node.status)}
              statusLabel={t(getStatusLabelKey(node.status))}
              description={node.address}
              meta={[
                {
                  key: 'trustLevel',
                  label: t(K.page.federatedNodes.trustLevel),
                  value: formatTrustLevel(node.trust_level),
                },
                {
                  key: 'lastHeartbeat',
                  label: t(K.page.federatedNodes.lastHeartbeat),
                  value: formatHeartbeat(node.last_heartbeat),
                },
                {
                  key: 'capabilities',
                  label: t(K.page.federatedNodes.capabilities),
                  value: node.capabilities?.length?.toString() || '0',
                },
              ]}
              icon={getNodeIcon(node.status)}
              actions={[
                {
                  key: 'details',
                  label: t(K.page.federatedNodes.viewDetails),
                  variant: 'outlined',
                  onClick: () => handleCardClick(node),
                },
                isConnected
                  ? {
                      key: 'disconnect',
                      label: t(K.page.federatedNodes.disconnect),
                      variant: 'text',
                      onClick: () => handleDisconnect(node),
                      disabled: actionLoading,
                    }
                  : {
                      key: 'connect',
                      label: t(K.page.federatedNodes.connect),
                      variant: 'text',
                      onClick: () => handleConnect(node),
                      disabled: actionLoading,
                    },
              ]}
              onClick={() => handleCardClick(node)}
            />
          )
        })}
      </CardCollectionWrap>

      {/* Detail Drawer */}
      {/* eslint-disable react/jsx-no-literals */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedNode?.name || ''}
        actions={
          <>
            {selectedNode?.status === 'connected' ? (
              <Button
                variant="outlined"
                color="error"
                onClick={() => {
                  if (selectedNode) {
                    handleDisconnect(selectedNode)
                  }
                }}
                disabled={actionLoading}
              >
                {t(K.page.federatedNodes.disconnect)}
              </Button>
            ) : (
              <Button
                variant="contained"
                color="primary"
                onClick={() => {
                  if (selectedNode) {
                    handleConnect(selectedNode)
                  }
                }}
                disabled={actionLoading}
              >
                {t(K.page.federatedNodes.connect)}
              </Button>
            )}
            <Button
              variant="outlined"
              onClick={() => setDrawerOpen(false)}
            >
              {t('common.close')}
            </Button>
          </>
        }
      >
        {selectedNode && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Node ID */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.nodeId)}
              </Typography>
              <Typography variant="body1" fontWeight={500}>
                {selectedNode.id}
              </Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.status)}
              </Typography>
              <Chip
                label={t(getStatusLabelKey(selectedNode.status))}
                color={
                  getStatusColor(selectedNode.status) === 'running'
                    ? 'success'
                    : getStatusColor(selectedNode.status) === 'error'
                    ? 'error'
                    : getStatusColor(selectedNode.status) === 'warning'
                    ? 'warning'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Address */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.address)}
              </Typography>
              <Typography variant="body1">{selectedNode.address}</Typography>
            </Box>

            {/* Trust Level */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.trustLevel)}
              </Typography>
              <Typography variant="body1">{formatTrustLevel(selectedNode.trust_level)}</Typography>
            </Box>

            {/* Last Heartbeat */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.lastHeartbeat)}
              </Typography>
              <Typography variant="body1">{formatHeartbeat(selectedNode.last_heartbeat)}</Typography>
            </Box>

            {/* Connected At */}
            {selectedNode.connected_at && (
              <Box>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  {t(K.page.federatedNodes.connectedAt)}
                </Typography>
                <Typography variant="body1">{selectedNode.connected_at}</Typography>
              </Box>
            )}

            {/* Capabilities */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.federatedNodes.capabilities)} ({selectedNode.capabilities?.length || 0})
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {selectedNode.capabilities && selectedNode.capabilities.length > 0 ? (
                  selectedNode.capabilities.slice(0, 10).map((capId) => (
                    <Chip key={capId} label={capId} size="small" variant="outlined" />
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">
                    {t(K.page.federatedNodes.noCapabilities)}
                  </Typography>
                )}
                {selectedNode.capabilities && selectedNode.capabilities.length > 10 && (
                  <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>
                    {t(K.page.federatedNodes.andMore, { count: selectedNode.capabilities.length - 10 })}
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
