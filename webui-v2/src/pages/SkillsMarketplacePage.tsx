/**
 * SkillsMarketplacePage - Skills Marketplace
 *
 * 🔒 Phase 4 Stage C Worker C8: P2-11 through P2-16
 *
 * Contract compliance:
 * - ✅ Text System: t(K.xxx) for all text (P2-16)
 * - ✅ Layout: usePageHeader + usePageActions
 * - ✅ CardGrid Pattern: CardCollectionWrap + ItemCard
 * - ✅ API Integration: skillosService.listSkills (P2-13)
 * - ✅ DetailDrawer: View skill details (P2-14)
 * - ✅ Loading State: Skeleton UI (P2-15)
 * - ✅ Error Handling: Error state + Retry button (P2-16)
 */

import { useState, useEffect } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { t, K } from '@/ui/text'
import { toast } from '@/ui/feedback'
import {
  Box,
  Typography,
  Chip,
  Alert,
  Button,
} from '@mui/material'
import ExtensionIcon from '@mui/icons-material/Extension'
import CodeIcon from '@mui/icons-material/Code'
import StorageIcon from '@mui/icons-material/Storage'
import ApiIcon from '@mui/icons-material/Api'
import {
  skillosService,
  type Skill,
} from '@/services/skillos.service'

// ===================================
// Icon Mapping
// ===================================
const ICON_MAP: Record<string, JSX.Element> = {
  code: <CodeIcon />,
  storage: <StorageIcon />,
  api: <ApiIcon />,
  default: <ExtensionIcon />,
}

function getIcon(skillName: string): JSX.Element {
  const lowerName = skillName.toLowerCase()
  for (const [key, icon] of Object.entries(ICON_MAP)) {
    if (key !== 'default' && lowerName.includes(key)) {
      return icon
    }
  }
  return ICON_MAP.default
}

// ===================================
// Component
// ===================================

export default function SkillsMarketplacePage() {
  // ===================================
  // State Management
  // ===================================
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)

  // ===================================
  // P2-13: API Integration - List Skills
  // ===================================
  const loadSkills = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await skillosService.listSkills()
      setSkills(response.skills || [])
    } catch (err) {
      console.error('Failed to load skills:', err)
      setError(err instanceof Error ? err.message : 'Failed to load skills')
      toast.error(t(K.common.error))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSkills()
  }, [])

  // ===================================
  // P2-14: View Skill Details Action
  // ===================================
  const handleViewSkill = async (skill: Skill) => {
    try {
      // Fetch full skill details
      const response = await skillosService.getSkill(skill.id)
      setSelectedSkill(response.skill)
      setDetailDrawerOpen(true)
    } catch (err) {
      console.error('Failed to load skill details:', err)
      toast.error(t(K.common.error))
    }
  }

  const handleCloseDetailDrawer = () => {
    setDetailDrawerOpen(false)
    setSelectedSkill(null)
  }

  // ===================================
  // Install Skill Action
  // ===================================
  const [installing, setInstalling] = useState<string | null>(null)

  const handleInstallSkill = async (skillId: string) => {
    setInstalling(skillId)
    try {
      await skillosService.installSkill({ skill_id: skillId })
      toast.success(t(K.common.success))
      // Refresh list to get updated status
      await loadSkills()
      // Close drawer if open
      if (detailDrawerOpen) {
        handleCloseDetailDrawer()
      }
    } catch (err) {
      console.error('Failed to install skill:', err)
      toast.error(t(K.common.error))
    } finally {
      setInstalling(null)
    }
  }

  // ===================================
  // Page Header & Actions
  // ===================================
  usePageHeader({
    title: t(K.page.skillsMarketplace.title),
    subtitle: t(K.page.skillsMarketplace.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t(K.common.refresh),
      variant: 'outlined',
      onClick: loadSkills,
    },
  ])

  // ===================================
  // P2-16: Error Handling
  // ===================================
  if (error && !loading) {
    return (
      <Box sx={{ py: 4 }}>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={loadSkills}>
              {t(K.common.retry)}
            </Button>
          }
        >
          <Typography variant="body2">{error}</Typography>
        </Alert>
      </Box>
    )
  }

  return (
    <>
      {/* P2-15: Loading State + Card Grid */}
      <CardCollectionWrap layout="grid" columns={3} gap={16} loading={loading}>
        {skills.length === 0 && !loading ? (
          <Box sx={{ gridColumn: '1 / -1', textAlign: 'center', py: 8 }}>
            <Typography variant="body1" color="text.secondary">
              {t('page.skillsMarketplace.noSkills')}
            </Typography>
          </Box>
        ) : (
          skills.map((skill) => (
            <ItemCard
              key={skill.id}
              title={skill.name}
              description={skill.description}
              meta={[
                { key: 'version', label: t(K.page.skillsMarketplace.metaVersion), value: skill.version },
                { key: 'status', label: t('form.field.status'), value: skill.status },
              ]}
              tags={[skill.status]}
              icon={getIcon(skill.name)}
              actions={[
                {
                  key: 'view',
                  label: t(K.common.view),
                  variant: 'outlined',
                  onClick: () => handleViewSkill(skill),
                },
                {
                  key: 'install',
                  label: t(K.common.install),
                  variant: 'contained',
                  onClick: () => handleInstallSkill(skill.id),
                  disabled: skill.status === 'installed' || installing === skill.id,
                },
              ]}
              onClick={() => handleViewSkill(skill)}
            />
          ))
        )}
      </CardCollectionWrap>

      {/* P2-14: Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleCloseDetailDrawer}
        title={selectedSkill?.name || ''}
        subtitle={selectedSkill?.version || ''}
        actions={
          selectedSkill && (
            <Button
              variant="contained"
              onClick={() => handleInstallSkill(selectedSkill.id)}
              disabled={selectedSkill.status === 'installed' || installing === selectedSkill.id}
            >
              {t(K.common.install)}
            </Button>
          )
        }
      >
        {selectedSkill && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Status Badge */}
            <Box>
              <Chip
                label={selectedSkill.status}
                color={selectedSkill.status === 'installed' ? 'success' : 'default'}
                size="small"
              />
            </Box>

            {/* Description */}
            {selectedSkill.description && (
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom>
                  {t('common.description')}
                </Typography>
                <Typography variant="body2">{selectedSkill.description}</Typography>
              </Box>
            )}

            {/* Version */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t(K.page.skillsMarketplace.metaVersion)}
              </Typography>
              <Typography variant="body2">{selectedSkill.version}</Typography>
            </Box>

            {/* Status */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t('form.field.status')}
              </Typography>
              <Typography variant="body2">{selectedSkill.status}</Typography>
            </Box>

            {/* Created At */}
            <Box>
              <Typography variant="caption" color="text.secondary" gutterBottom>
                {t('common.createdAt')}
              </Typography>
              <Typography variant="body2">{selectedSkill.created_at}</Typography>
            </Box>
          </Box>
        )}
      </DetailDrawer>
    </>
  )
}
