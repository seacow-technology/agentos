/**
 * GovernancePage - Governance Dashboard
 *
 * CardGridPage 迁移
 * 使用 CardCollectionWrap + ItemCard
 * Phase 3 Integration: 添加 DetailDrawer 和操作 Dialog
 */

import { useState } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { K, useTextTranslation } from '@/ui/text'
import { DetailDrawer, DeleteConfirmDialog } from '@/ui/interaction'
import { Box, Typography, Chip } from '@mui/material'
import { Button } from '@/ui'
import WarningIcon from '@mui/icons-material/Warning'
import ErrorIcon from '@mui/icons-material/Error'
import InfoIcon from '@mui/icons-material/Info'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'

// Mock Governance Items 基础数据
const mockGovernanceItemsBase = [
  {
    id: 'gov-1',
    title: 'Unauthorized API Access Detected',
    description: 'Multiple attempts to access restricted API endpoints from unknown service account',
    severity: 'Critical',
    status: 'Open',
    createdAt: '2h ago',
    tags: ['Security', 'API', 'Critical'],
    icon: <ErrorIcon />,
  },
  {
    id: 'gov-2',
    title: 'Policy Violation: Resource Quota',
    description: 'Skill execution exceeded allocated memory quota by 150%',
    severity: 'High',
    status: 'In Review',
    createdAt: '5h ago',
    tags: ['Policy', 'Resources', 'High'],
    icon: <WarningIcon />,
  },
  {
    id: 'gov-3',
    title: 'Trust Tier Downgrade Request',
    description: 'Extension "data-processor" requesting trust tier downgrade from T2 to T3',
    severity: 'Medium',
    status: 'Pending',
    createdAt: '1d ago',
    tags: ['Trust', 'Extension', 'Review'],
    icon: <InfoIcon />,
  },
  {
    id: 'gov-4',
    title: 'Compliance Check Passed',
    description: 'All system components passed quarterly security audit',
    severity: 'Info',
    status: 'Resolved',
    createdAt: '2d ago',
    tags: ['Compliance', 'Audit', 'Success'],
    icon: <CheckCircleIcon />,
  },
  {
    id: 'gov-5',
    title: 'Skill Sandbox Breach Attempt',
    description: 'Skill "web-scraper" attempted to access filesystem outside sandbox',
    severity: 'Critical',
    status: 'Blocked',
    createdAt: '6h ago',
    tags: ['Security', 'Sandbox', 'Critical'],
    icon: <ErrorIcon />,
  },
  {
    id: 'gov-6',
    title: 'Rate Limit Configuration Change',
    description: 'API rate limits updated for all external services',
    severity: 'Low',
    status: 'Resolved',
    createdAt: '3d ago',
    tags: ['Configuration', 'API', 'Info'],
    icon: <InfoIcon />,
  },
]

export default function GovernancePage() {

  // ===================================
  // i18n Hook - Subscribe to language changes
  // ===================================
  const { t } = useTextTranslation()

  // ===================================
  // Phase 3 Integration - Interaction State
  // ===================================
  const [selectedItem, setSelectedItem] = useState<typeof mockGovernanceItemsBase[0] | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // ===================================
  // Data Fetching - Uses mock data (mockGovernanceItemsBase)
  // Ready for real API integration when backend available
  // ===================================

  // ===================================
  // Page Header and Actions
  // ===================================
  usePageHeader({
    title: t(K.page.governance.title),
    subtitle: t(K.page.governance.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => console.log('Refresh governance items'),
    },
    {
      key: 'create',
      label: t(K.page.governance.createPolicy),
      variant: 'contained',
      onClick: () => console.log('Create governance policy'),
    },
  ])

  // ===================================
  // Phase 3 Integration - Handlers
  // ===================================
  const handleCardClick = (item: typeof mockGovernanceItemsBase[0]) => {
    setSelectedItem(item)
    setDrawerOpen(true)
  }

  const handleDelete = () => {
    console.log('Delete governance item:', selectedItem?.id)
    setDeleteDialogOpen(false)
    setDrawerOpen(false)
  }

  // ===================================
  // Render
  // ===================================
  return (
    <>
      <CardCollectionWrap layout="grid" columns={3} gap={16}>
        {mockGovernanceItemsBase.map((item) => (
          <ItemCard
            key={item.id}
            title={item.title}
            description={item.description}
            meta={[
              { key: 'severity', label: t(K.page.governance.metaSeverity), value: item.severity },
              { key: 'status', label: t(K.page.governance.metaStatus), value: item.status },
              { key: 'createdAt', label: t(K.page.governance.metaCreated), value: item.createdAt },
            ]}
            tags={item.tags}
            icon={item.icon}
            actions={[
              {
                key: 'view',
                label: t(K.page.governance.actionView),
                variant: 'outlined',
                onClick: () => console.log('View governance item:', item.id),
              },
              {
                key: 'review',
                label: t(K.page.governance.actionReview),
                variant: 'contained',
                onClick: () => console.log('Review governance item:', item.id),
              },
            ]}
            onClick={() => handleCardClick(item)}
          />
        ))}
      </CardCollectionWrap>

      {/* Detail Drawer - Phase 3 Integration */}
      <DetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={selectedItem?.title || ''}
        actions={
          <>
            <Button
              variant="contained"
              color="primary"
              onClick={() => console.log('Review item:', selectedItem?.id)}
            >
              {t(K.page.governance.actionReview)}
            </Button>
            <Button
              variant="outlined"
              color="success"
              onClick={() => console.log('Resolve item:', selectedItem?.id)}
            >
              {t(K.page.governance.resolve)}
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={() => {
                setDrawerOpen(false)
                setDeleteDialogOpen(true)
              }}
            >
              {t('common.delete')}
            </Button>
          </>
        }
      >
        {selectedItem && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Severity */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governance.metaSeverity)}
              </Typography>
              <Chip
                label={selectedItem.severity}
                color={
                  selectedItem.severity === 'Critical'
                    ? 'error'
                    : selectedItem.severity === 'High'
                    ? 'warning'
                    : selectedItem.severity === 'Medium'
                    ? 'info'
                    : 'default'
                }
                size="small"
              />
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governance.metaStatus)}
              </Typography>
              <Chip label={selectedItem.status} size="small" />
            </Box>

            {/* Description */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governance.description)}
              </Typography>
              <Typography variant="body1">{selectedItem.description}</Typography>
            </Box>

            {/* Tags */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governance.tags)}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {selectedItem.tags.map((tag) => (
                  <Chip key={tag} label={tag} size="small" variant="outlined" />
                ))}
              </Box>
            </Box>

            {/* Created At */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {t(K.page.governance.metaCreated)}
              </Typography>
              <Typography variant="body1">{selectedItem.createdAt}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* Delete Confirm Dialog - Phase 3 Integration */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        onConfirm={handleDelete}
        resourceType={t(K.page.governance.governanceItem)}
        resourceName={selectedItem?.title}
      />
    </>
  )
}
