/**
 * ChannelsPage - Communication Channels
 *
 * Phase 6.1 Batch 9: API Integration
 * - Integrated with /api/channels-marketplace API
 * - Removed mock data
 * - Real-time channel management
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap, ItemCard, type ItemCardMeta, type ItemCardAction } from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { DialogForm } from '@/ui/interaction'
import { RefreshIcon, ChatBubbleIcon, ErrorIcon, CancelIcon, CheckCircleIcon } from '@/ui/icons'
import { TextField, Select, MenuItem } from '@/ui'
import { Box, Typography, Grid } from '@mui/material'
import { httpClient } from '@platform/http'

// ===================================
// Types
// ===================================

interface Channel {
  id: string
  name: string
  icon: string
  description: string
  provider?: string
  capabilities: string[]
  status: string
  enabled: boolean
  security_mode: string
  last_heartbeat_at?: number
  privacy_badges: string[]
}

export default function ChannelsPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  const [loading, setLoading] = useState(false)
  const [enabledChannels, setEnabledChannels] = useState<Channel[]>([])
  const [availableChannels, setAvailableChannels] = useState<Channel[]>([])

  // Dialog State
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [channelName, setChannelName] = useState('')
  const [channelType, setChannelType] = useState('whatsapp')
  const [channelConfig, setChannelConfig] = useState('')

  // Test Channel Dialog State
  const [testDialogOpen, setTestDialogOpen] = useState(false)
  const [testChannelId, setTestChannelId] = useState('')
  const [testChannelName, setTestChannelName] = useState('')
  const [testMessage, setTestMessage] = useState('Hello! This is a test message from AgentOS.')

  // ===================================
  // Data Loading
  // ===================================

  const loadChannels = async () => {
    setLoading(true)
    try {
      const response = await httpClient.get<{ ok: boolean; data: { channels: Channel[]; total: number } }>(
        '/api/channels-marketplace'
      )

      const data = response.data
      if (data.ok && data.data) {
        // Split into enabled and available
        const enabled = data.data.channels.filter((ch: Channel) => ch.enabled)
        const available = data.data.channels.filter((ch: Channel) => !ch.enabled)

        setEnabledChannels(enabled)
        setAvailableChannels(available)
      }
    } catch (error) {
      console.error('Failed to load channels:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadChannels()
  }, [])

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.channels.title),
    subtitle: t(K.page.channels.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      icon: <RefreshIcon />,
      variant: 'outlined',
      onClick: loadChannels,
    },
    {
      key: 'create',
      label: t(K.page.channels.addChannel),
      variant: 'contained',
      onClick: () => {
        setCreateDialogOpen(true)
      },
    },
  ])

  // ===================================
  // Dialog Handlers
  // ===================================
  const handleCreateSubmit = () => {
    console.log('Create Channel:', {
      name: channelName,
      type: channelType,
      config: channelConfig,
    })
    setCreateDialogOpen(false)
    setChannelName('')
    setChannelType('whatsapp')
    setChannelConfig('')
  }

  const handleTestChannel = async (channelId: string, channelTitle: string) => {
    setTestChannelId(channelId)
    setTestChannelName(channelTitle)
    setTestDialogOpen(true)
  }

  const handleTestSubmit = async () => {
    try {
      const response = await httpClient.post<{ ok: boolean }>(`/api/channels-marketplace/${testChannelId}/test`, {
        test_type: 'basic',
        test_data: { message: testMessage },
      })

      if (response.data.ok) {
        console.log('Channel test successful')
      } else {
        console.error('Channel test failed')
      }
    } catch (error) {
      console.error('Failed to test channel:', error)
    } finally {
      setTestDialogOpen(false)
      setTestMessage('Hello! This is a test message from AgentOS.')
    }
  }

  const handleEnableChannel = async (channelId: string) => {
    try {
      const response = await httpClient.post<{ ok: boolean }>(`/api/channels-marketplace/${channelId}/enable`, {})
      if (response.data.ok) {
        await loadChannels()
      }
    } catch (error) {
      console.error('Failed to enable channel:', error)
    }
  }

  const handleDisableChannel = async (channelId: string) => {
    try {
      const response = await httpClient.post<{ ok: boolean }>(`/api/channels-marketplace/${channelId}/disable`, {})
      if (response.data.ok) {
        await loadChannels()
      }
    } catch (error) {
      console.error('Failed to disable channel:', error)
    }
  }

  // ===================================
  // Transform Channels to Cards
  // ===================================
  const getChannelIcon = (status: string) => {
    if (status === 'enabled') return <CheckCircleIcon />
    if (status === 'error') return <ErrorIcon />
    if (status === 'disabled') return <CancelIcon />
    return <ChatBubbleIcon />
  }

  const getStatusColor = (status: string): 'success' | 'error' | 'warning' | 'default' => {
    if (status === 'enabled') return 'success'
    if (status === 'error') return 'error'
    if (status === 'disabled' || status === 'needs_setup') return 'default'
    return 'warning'
  }

  const transformedEnabledChannels = enabledChannels.map((channel) => ({
    id: channel.id,
    title: channel.name,
    description: channel.description,
    icon: getChannelIcon(channel.status),
    meta: [
      { key: 'provider', label: t(K.page.channels.type), value: channel.provider || 'N/A' },
      {
        key: 'status',
        label: t(K.page.channels.status),
        value: channel.status,
        color: getStatusColor(channel.status),
      },
      { key: 'capabilities', label: t(K.page.channels.capabilities), value: channel.capabilities.join(', ') },
    ] as ItemCardMeta[],
    actions: [
      { key: 'test', label: t(K.page.channels.test), onClick: () => handleTestChannel(channel.id, channel.name) },
      { key: 'configure', label: t(K.page.channels.configure), onClick: () => console.log('Configure', channel.id) },
      { key: 'disable', label: t(K.page.channels.disable), onClick: () => handleDisableChannel(channel.id) },
    ] as ItemCardAction[],
  }))

  const transformedAvailableChannels = availableChannels.map((channel) => ({
    id: channel.id,
    title: channel.name,
    description: channel.description,
    icon: getChannelIcon(channel.status),
    meta: [
      { key: 'provider', label: t(K.page.channels.type), value: channel.provider || 'N/A' },
      {
        key: 'status',
        label: t(K.page.channels.status),
        value: channel.status,
        color: getStatusColor(channel.status),
      },
    ] as ItemCardMeta[],
    actions: [
      { key: 'setup', label: t(K.page.channels.setup), onClick: () => handleEnableChannel(channel.id) },
    ] as ItemCardAction[],
  }))

  // ===================================
  // Render: Two Sections
  // ===================================
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Your Channels Section */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {t(K.page.channels.yourChannels)}
        </Typography>
        <CardCollectionWrap loading={loading}>
          {transformedEnabledChannels.length > 0 ? (
            transformedEnabledChannels.map((channel) => (
              <ItemCard
                key={channel.id}
                title={channel.title}
                description={channel.description}
                icon={channel.icon}
                meta={channel.meta}
                actions={channel.actions}
              />
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t(K.page.channels.noEnabledChannels)}
            </Typography>
          )}
        </CardCollectionWrap>
      </Box>

      {/* Available Channels Section */}
      <Box>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {t(K.page.channels.availableChannels)}
        </Typography>
        <CardCollectionWrap loading={loading}>
          {transformedAvailableChannels.length > 0 ? (
            transformedAvailableChannels.map((channel) => (
              <ItemCard
                key={channel.id}
                title={channel.title}
                description={channel.description}
                icon={channel.icon}
                meta={channel.meta}
                actions={channel.actions}
              />
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t(K.page.channels.allChannelsEnabled)}
            </Typography>
          )}
        </CardCollectionWrap>
      </Box>

      {/* Create Channel Dialog */}
      <DialogForm
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        title={t(K.page.channels.addChannel)}
        submitText={t('common.create')}
        cancelText={t('common.cancel')}
        onSubmit={handleCreateSubmit}
        submitDisabled={!channelName.trim()}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.channels.fieldChannelName)}
              placeholder={t(K.page.channels.fieldChannelNamePlaceholder)}
              value={channelName}
              onChange={(e) => setChannelName(e.target.value)}
              fullWidth
              required             />
          </Grid>
          <Grid item xs={12}>
            <Select
              label={t(K.page.channels.fieldChannelType)}
              fullWidth
              value={channelType}
              onChange={(e) => setChannelType(e.target.value)}
            >
              <MenuItem value="whatsapp">{t(K.page.channels.typeWhatsApp)}</MenuItem>
              <MenuItem value="telegram">{t(K.page.channels.typeTelegram)}</MenuItem>
              <MenuItem value="slack">{t(K.page.channels.typeSlack)}</MenuItem>
              <MenuItem value="discord">{t(K.page.channels.typeDiscord)}</MenuItem>
              <MenuItem value="sms">{t(K.page.channels.typeSMS)}</MenuItem>
              <MenuItem value="email">{t(K.page.channels.typeEmail)}</MenuItem>
            </Select>
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.channels.fieldConfiguration)}
              placeholder={t(K.page.channels.fieldConfigurationPlaceholder)}
              value={channelConfig}
              onChange={(e) => setChannelConfig(e.target.value)}
              fullWidth
              multiline
              rows={3}
            />
          </Grid>
        </Grid>
      </DialogForm>

      {/* Test Channel Dialog */}
      <DialogForm
        open={testDialogOpen}
        onClose={() => setTestDialogOpen(false)}
        title={`${t(K.page.channels.testChannelTitle)}: ${testChannelName}`}
        submitText={t(K.page.channels.sendTest)}
        cancelText={t('common.cancel')}
        onSubmit={handleTestSubmit}
        submitDisabled={!testMessage.trim()}
      >
        <Grid container spacing={2}>
          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t(K.page.channels.testMessageDesc)}
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <TextField
              label={t(K.page.channels.fieldTestMessage)}
              placeholder={t(K.page.channels.fieldTestMessagePlaceholder)}
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              fullWidth
              required
              multiline
              rows={4}             />
          </Grid>
        </Grid>
      </DialogForm>
    </Box>
  )
}
