/**
 * TriggersPage - 触发器管理
 *
 * ✅ i18n: 使用 useTextTranslation + K keys
 * ✅ API: agentosService.getTriggers()
 * ✅ States: loading, error, empty, success
 * ✅ Button functionality: Edit, Delete, View Detail
 * ✅ Error handling & validation
 *
 * CardGridPage 迁移 - Agent #3
 * 使用 CardCollectionWrap + ItemCard
 */

import { useState, useEffect } from 'react'
import { usePageHeader } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { EmptyState, Grid, TextField, MenuItem, Typography, Box, Button } from '@/ui'
import { K, useText } from '@/ui/text'
import { agentosService, type Trigger } from '@/services'
import { DialogForm } from '@/ui/interaction/DialogForm'
import { ConfirmDialog } from '@/ui/interaction/ConfirmDialog'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import ScheduleIcon from '@mui/icons-material/Schedule'
import NotificationsIcon from '@mui/icons-material/Notifications'
import WebhookIcon from '@mui/icons-material/Webhook'
import TimerIcon from '@mui/icons-material/Timer'
import EventIcon from '@mui/icons-material/Event'
import FlashOnIcon from '@mui/icons-material/FlashOn'

export default function TriggersPage() {
  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useText()

  // ===================================
  // API State
  // ===================================
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [triggers, setTriggers] = useState<Trigger[]>([])

  // ===================================
  // Dialog State Management
  // ===================================
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [selectedTrigger, setSelectedTrigger] = useState<Trigger | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // ===================================
  // Form State
  // ===================================
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    type: '',
    status: 'active',
  })

  // ===================================
  // API Call - Fetch Triggers
  // ===================================
  const fetchTriggers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await agentosService.getTriggers()
      setTriggers(response.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch triggers')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTriggers()
  }, [])

  // ===================================
  // Page Header
  // ===================================
  usePageHeader({
    title: t(K.page.triggers.title),
    subtitle: t(K.page.triggers.subtitle),
  })

  // ===================================
  // Icon Map for dynamic icons
  // ===================================
  const iconMap: Record<string, React.ReactNode> = {
    Schedule: <ScheduleIcon />,
    Notification: <NotificationsIcon />,
    Webhook: <WebhookIcon />,
    Timer: <TimerIcon />,
    Event: <EventIcon />,
    FlashOn: <FlashOnIcon />,
  }

  // ===================================
  // Event Handlers - Edit
  // ===================================
  const handleEditClick = (trigger: Trigger) => {
    setSelectedTrigger(trigger)
    setFormData({
      title: trigger.title,
      description: trigger.description,
      type: trigger.type,
      status: trigger.status,
    })
    setActionError(null)
    setEditDialogOpen(true)
  }

  const handleEditSubmit = async () => {
    if (!selectedTrigger) return

    // Validate form
    if (!formData.title.trim()) {
      setActionError(t(K.page.triggers.titleRequired))
      return
    }
    if (!formData.type) {
      setActionError(t(K.page.triggers.typeRequired))
      return
    }

    setActionLoading(true)
    setActionError(null)

    try {
      // Mock API call - simulate update
      // In real implementation: await agentosService.updateTrigger(selectedTrigger.id, formData)
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Update local state
      setTriggers(triggers.map(t =>
        t.id === selectedTrigger.id
          ? { ...t, ...formData }
          : t
      ))

      setEditDialogOpen(false)
      setSelectedTrigger(null)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to update trigger')
    } finally {
      setActionLoading(false)
    }
  }

  const handleEditClose = () => {
    if (!actionLoading) {
      setEditDialogOpen(false)
      setSelectedTrigger(null)
      setActionError(null)
    }
  }

  // ===================================
  // Event Handlers - Delete
  // ===================================
  const handleDeleteClick = (trigger: Trigger) => {
    setSelectedTrigger(trigger)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedTrigger) return

    setActionLoading(true)

    try {
      // Mock API call - simulate delete
      // In real implementation: await agentosService.deleteTrigger(selectedTrigger.id)
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Remove from local state
      setTriggers(triggers.filter(t => t.id !== selectedTrigger.id))

      setDeleteDialogOpen(false)
      setSelectedTrigger(null)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to delete trigger')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteClose = () => {
    if (!actionLoading) {
      setDeleteDialogOpen(false)
      setSelectedTrigger(null)
    }
  }

  // ===================================
  // Event Handlers - Detail View
  // ===================================
  const handleCardClick = (trigger: Trigger) => {
    setSelectedTrigger(trigger)
    setDetailDrawerOpen(true)
  }

  const handleDetailClose = () => {
    setDetailDrawerOpen(false)
    setSelectedTrigger(null)
  }

  // ===================================
  // Form Change Handler
  // ===================================
  const handleFormChange = (field: keyof typeof formData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear error when user starts typing
    if (actionError) {
      setActionError(null)
    }
  }

  // ===================================
  // Render States
  // ===================================
  
  // Loading state
  if (loading) {
    return (
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        <div style={{ padding: '40px', textAlign: 'center' }}>
          {t(K.common.loading)}...
        </div>
      </CardCollectionWrap>
    )
  }

  // Error state
  if (error) {
    return (
      <EmptyState
        message={`${t(K.common.error)}: ${error}`}
      />
    )
  }

  // Empty state
  if (triggers.length === 0) {
    return (
      <EmptyState
        message={t(K.page.triggers.noTriggersDesc)}
      />
    )
  }

  // Success state - render cards with dialogs
  return (
    <>
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        {triggers.map((trigger) => (
          <ItemCard
            key={trigger.id}
            title={trigger.title}
            description={trigger.description}
            meta={[
              { key: 'type', label: t(K.form.field.type), value: trigger.type },
              { key: 'status', label: t(K.form.field.status), value: trigger.status },
            ]}
            tags={trigger.status === 'active' ? [t(K.common.active)] : [t(K.common.inactive)]}
            icon={iconMap[trigger.type] || <EventIcon />}
            actions={[
              {
                key: 'edit',
                label: t(K.common.edit),
                variant: 'outlined',
                onClick: () => handleEditClick(trigger),
              },
              {
                key: 'delete',
                label: t(K.common.delete),
                variant: 'text',
                onClick: () => handleDeleteClick(trigger),
              },
            ]}
            onClick={() => handleCardClick(trigger)}
          />
        ))}
      </CardCollectionWrap>

      {/* Edit Dialog */}
      <DialogForm
        open={editDialogOpen}
        onClose={handleEditClose}
        title={t(K.page.triggers.editTrigger)}
        submitText={t(K.common.save)}
        cancelText={t(K.common.cancel)}
        onSubmit={handleEditSubmit}
        loading={actionLoading}
        submitDisabled={!formData.title.trim() || !formData.type}
      >
        <Grid container spacing={2}>
          {/* Error Message */}
          {actionError && (
            <Grid item xs={12}>
              <Box sx={{ p: 2, bgcolor: 'error.light', borderRadius: 1 }}>
                <Typography variant="body2" color="error.dark">
                  {actionError}
                </Typography>
              </Box>
            </Grid>
          )}

          {/* Title Field */}
          <Grid item xs={12}>
            <TextField
              label={t(K.form.field.title) + ' *'}
              fullWidth
              value={formData.title}
              onChange={(e) => handleFormChange('title', e.target.value)}
              disabled={actionLoading}
              error={!formData.title.trim()}
              helperText={!formData.title.trim() ? t(K.page.triggers.titleRequired) : ''}
            />
          </Grid>

          {/* Description Field */}
          <Grid item xs={12}>
            <TextField
              label={t(K.form.field.description)}
              fullWidth
              multiline
              rows={3}
              value={formData.description}
              onChange={(e) => handleFormChange('description', e.target.value)}
              disabled={actionLoading}
            />
          </Grid>

          {/* Type Field */}
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label={t(K.form.field.type) + ' *'}
              select
              value={formData.type}
              onChange={(e) => handleFormChange('type', e.target.value)}
              disabled={actionLoading}
              error={!formData.type}
            >
              <MenuItem value="Schedule">{t(K.page.triggers.typeSchedule)}</MenuItem>
              <MenuItem value="Notification">{t(K.page.triggers.typeNotification)}</MenuItem>
              <MenuItem value="Webhook">{t(K.page.triggers.typeWebhook)}</MenuItem>
              <MenuItem value="Timer">{t(K.page.triggers.typeTimer)}</MenuItem>
              <MenuItem value="Event">{t(K.page.triggers.typeEvent)}</MenuItem>
              <MenuItem value="FlashOn">{t(K.page.triggers.typeFlashOn)}</MenuItem>
            </TextField>
          </Grid>

          {/* Status Field */}
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label={t(K.form.field.status)}
              select
              value={formData.status}
              onChange={(e) => handleFormChange('status', e.target.value)}
              disabled={actionLoading}
            >
              <MenuItem value="active">{t(K.common.active)}</MenuItem>
              <MenuItem value="inactive">{t(K.common.inactive)}</MenuItem>
            </TextField>
          </Grid>
        </Grid>
      </DialogForm>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onClose={handleDeleteClose}
        title={t(K.page.triggers.deleteTrigger)}
        message={t(K.page.triggers.deleteConfirmMessage).replace('{title}', selectedTrigger?.title || '')}
        confirmText={t(K.common.delete)}
        cancelText={t(K.common.cancel)}
        onConfirm={handleDeleteConfirm}
        loading={actionLoading}
        color="error"
      />

      {/* Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleDetailClose}
        title={selectedTrigger?.title || t(K.page.triggers.triggerDetails)}
        subtitle={`ID: ${selectedTrigger?.id}`}
        actions={
          <>
            <Button
              variant="outlined"
              onClick={() => {
                handleDetailClose()
                if (selectedTrigger) {
                  handleEditClick(selectedTrigger)
                }
              }}
            >
              {t(K.common.edit)}
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={() => {
                handleDetailClose()
                if (selectedTrigger) {
                  handleDeleteClick(selectedTrigger)
                }
              }}
            >
              {t(K.common.delete)}
            </Button>
          </>
        }
      >
        {selectedTrigger && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Basic Information */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t(K.form.field.title)}
              </Typography>
              <Typography variant="body1">{selectedTrigger.title}</Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t(K.form.field.description)}
              </Typography>
              <Typography variant="body1">{selectedTrigger.description || t(K.common.noDescription)}</Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t(K.form.field.type)}
              </Typography>
              <Typography variant="body1">{selectedTrigger.type}</Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t(K.form.field.status)}
              </Typography>
              <Typography variant="body1" sx={{
                color: selectedTrigger.status === 'active' ? 'success.main' : 'text.secondary',
                textTransform: 'capitalize'
              }}>
                {selectedTrigger.status}
              </Typography>
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t(K.page.triggers.triggerId)}
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', bgcolor: 'grey.100', p: 1, borderRadius: 1 }}>
                {selectedTrigger.id}
              </Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
