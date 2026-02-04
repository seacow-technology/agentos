/**
 * McpMarketplacePage - MCP Marketplace
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t(K.xxx)（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ CardGrid Pattern: CardCollectionWrap + ItemCard
 * - ✅ API Integration: listMCPMarketplace + DetailDrawer + ConfirmDialog
 * - ✅ Security: Governance preview + audit_id display
 */

import { useState, useEffect, useMemo, useCallback } from 'react'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { CardCollectionWrap } from '@/ui/cards/CardCollectionWrap'
import { ItemCard } from '@/ui/cards/ItemCard'
import { DetailDrawer } from '@/ui/interaction/DetailDrawer'
import { ConfirmDialog } from '@/ui/interaction/ConfirmDialog'
import {
  FilterBar,
  Box,
  Typography,
  Chip,
  Alert,
  Divider,
  Link,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
} from '@/ui'
import { K, useTextTranslation } from '@/ui/text'
import { toast } from '@/ui/feedback'
import {
  ExtensionIcon,
  StorageIcon,
  CloudIcon,
  CodeIcon,
  WarningIcon,
  CheckCircleIcon,
} from '@/ui/icons'
import {
  communicationosService,
  type MCPMarketplaceItem,
  type MCPPackageDetail,
  type MCPGovernancePreview,
} from '@/services/communicationos.service'

// Constants for MUI prop values (to pass ESLint jsx-no-literals)
const SIZE_SMALL = 'small' as const
const VARIANT_H6 = 'h6' as const
const VARIANT_BODY1 = 'body1' as const
const VARIANT_BODY2 = 'body2' as const
const VARIANT_CAPTION = 'caption' as const
const VARIANT_SUBTITLE2 = 'subtitle2' as const
const VARIANT_OUTLINED = 'outlined' as const
const VARIANT_CONTAINED = 'contained' as const
const COLOR_TEXT_SECONDARY = 'text.secondary' as const
const COLOR_ERROR = 'error' as const
const COLOR_SUCCESS = 'success' as const
const COLOR_WARNING = 'warning' as const
const COLOR_PRIMARY = 'primary' as const
const COLOR_DEFAULT = 'default' as const
const SEVERITY_WARNING = 'warning' as const
const LAYOUT_GRID = 'grid' as const
const LINK_TARGET_BLANK = '_blank' as const
const LINK_REL_NOOPENER = 'noopener' as const
const SELECT_VALUE_ALL = 'all' as const

const ICON_MAP: Record<string, JSX.Element> = {
  git: <CodeIcon />,
  github: <CodeIcon />,
  database: <StorageIcon />,
  sql: <StorageIcon />,
  api: <CodeIcon />,
  communication: <CodeIcon />,
  cloud: <CloudIcon />,
  storage: <CloudIcon />,
  default: <ExtensionIcon />,
}

function getIcon(tags: string[]): JSX.Element {
  const lowerTags = tags.map((t) => t.toLowerCase())
  for (const [key, icon] of Object.entries(ICON_MAP)) {
    if (key !== 'default' && lowerTags.some((t) => t.includes(key))) {
      return icon
    }
  }
  return ICON_MAP.default
}

export default function McpMarketplacePage() {
  const { t } = useTextTranslation()

  // ===================================
  // State Management
  // ===================================
  const [packages, setPackages] = useState<MCPMarketplaceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedPackage, setSelectedPackage] = useState<MCPPackageDetail | null>(null)
  const [governance, setGovernance] = useState<MCPGovernancePreview | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [installDialogOpen, setInstallDialogOpen] = useState(false)
  const [packageToInstall, setPackageToInstall] = useState<MCPMarketplaceItem | null>(null)
  const [installing, setInstalling] = useState(false)
  const [uninstallDialogOpen, setUninstallDialogOpen] = useState(false)
  const [packageToUninstall, setPackageToUninstall] = useState<MCPMarketplaceItem | null>(null)
  const [uninstalling, setUninstalling] = useState(false)

  // ===================================
  // P1-13: Search & Filter State
  // ===================================
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [connectedOnly, setConnectedOnly] = useState(false)

  // ===================================
  // P0-11: List API Integration
  // ===================================
  const loadPackages = useCallback(async () => {
    setLoading(true)
    try {
      const response = await communicationosService.listMCPMarketplace()
      setPackages(response.packages || [])
    } catch (error) {
      console.error('Failed to load MCP packages:', error)
      toast.error(t(K.page.mcpMarketplace.installError))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    loadPackages()
  }, [loadPackages])

  // ===================================
  // P1-13: Filter & Search Logic
  // ===================================
  const filteredPackages = useMemo(() => {
    let result = packages

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (pkg) =>
          pkg.name.toLowerCase().includes(query) ||
          (pkg.description && pkg.description.toLowerCase().includes(query)) ||
          pkg.author.toLowerCase().includes(query) ||
          pkg.tags.some((tag) => tag.toLowerCase().includes(query))
      )
    }

    // Category filter (tag-based)
    if (selectedCategory !== 'all') {
      result = result.filter((pkg) =>
        pkg.tags.some((tag) => tag.toLowerCase() === selectedCategory.toLowerCase())
      )
    }

    // Connected only filter
    if (connectedOnly) {
      result = result.filter((pkg) => pkg.is_connected)
    }

    return result
  }, [packages, searchQuery, selectedCategory, connectedOnly])

  // Extract unique categories from tags
  const categories = useMemo(() => {
    const uniqueTags = new Set<string>()
    packages.forEach((pkg) => {
      pkg.tags.forEach((tag) => uniqueTags.add(tag))
    })
    return Array.from(uniqueTags).sort()
  }, [packages])

  // Clear all filters
  const handleClearFilters = () => {
    setSearchQuery('')
    setSelectedCategory('all')
    setConnectedOnly(false)
  }

  // ===================================
  // P0-12: Package Detail View
  // ===================================
  const handleViewPackage = async (pkg: MCPMarketplaceItem) => {
    try {
      const [detailResponse, governanceResponse] = await Promise.all([
        communicationosService.getMCPMarketplaceItem(pkg.package_id),
        communicationosService.getMCPGovernancePreview(pkg.package_id),
      ])

      if (detailResponse.ok && detailResponse.data) {
        setSelectedPackage(detailResponse.data)
      }

      if (governanceResponse.ok && governanceResponse.data) {
        setGovernance(governanceResponse.data)
      }

      setDetailDrawerOpen(true)
    } catch (error) {
      console.error('Failed to load package details:', error)
      toast.error(t(K.page.mcpMarketplace.installError))
    }
  }

  const handleCloseDetailDrawer = () => {
    setDetailDrawerOpen(false)
    setSelectedPackage(null)
    setGovernance(null)
  }

  // ===================================
  // P0-14: Installation Flow
  // ===================================
  const handleInstallClick = (pkg: MCPMarketplaceItem) => {
    setPackageToInstall(pkg)
    setInstallDialogOpen(true)
  }

  const handleConfirmInstall = async () => {
    if (!packageToInstall) return

    setInstalling(true)
    try {
      const response = await communicationosService.attachMCPPackage({
        package_id: packageToInstall.package_id,
      })

      if (response.ok && response.data) {
        const { audit_id, warnings, next_steps } = response.data

        // Build success message with audit_id
        const message = `${t(K.page.mcpMarketplace.installSuccess)}\n${t(K.page.mcpMarketplace.auditId)}: ${audit_id}`
        toast.success(message)

        // Show warnings if any
        if (warnings && warnings.length > 0) {
          toast.warning(`${t(K.page.mcpMarketplace.detailWarnings)}:\n${warnings.join('\n')}`)
        }

        // Show next steps if any
        if (next_steps && next_steps.length > 0) {
          console.info('Next steps:', next_steps)
        }

        // Reload packages to reflect new connection status
        await loadPackages()

        // Close dialogs
        setInstallDialogOpen(false)
        setDetailDrawerOpen(false)
        setPackageToInstall(null)
      }
    } catch (error) {
      console.error('Failed to install package:', error)
      toast.error(t(K.page.mcpMarketplace.installError))
    } finally {
      setInstalling(false)
    }
  }

  const handleCancelInstall = () => {
    setInstallDialogOpen(false)
    setPackageToInstall(null)
  }

  // ===================================
  // P2-5: Uninstall Functionality
  // ===================================
  const handleUninstallClick = (pkg: MCPMarketplaceItem) => {
    setPackageToUninstall(pkg)
    setUninstallDialogOpen(true)
  }

  const handleConfirmUninstall = async () => {
    if (!packageToUninstall) return

    setUninstalling(true)
    try {
      const response = await communicationosService.uninstallMCPPackage(
        packageToUninstall.package_id
      )

      if (response.ok && response.data) {
        const { audit_id, warnings } = response.data

        // Build success message with audit_id
        const message = `${t(K.page.mcpMarketplace.uninstallSuccess)}\n${t(K.page.mcpMarketplace.auditId)}: ${audit_id}`
        toast.success(message)

        // Show warnings if any
        if (warnings && warnings.length > 0) {
          toast.warning(`${t(K.page.mcpMarketplace.detailWarnings)}:\n${warnings.join('\n')}`)
        }

        // Reload packages to reflect new connection status
        await loadPackages()

        // Close dialogs
        setUninstallDialogOpen(false)
        setDetailDrawerOpen(false)
        setPackageToUninstall(null)
      }
    } catch (error) {
      console.error('Failed to uninstall package:', error)
      toast.error(t(K.page.mcpMarketplace.uninstallError))
    } finally {
      setUninstalling(false)
    }
  }

  const handleCancelUninstall = () => {
    setUninstallDialogOpen(false)
    setPackageToUninstall(null)
  }

  // ===================================
  // Page Header & Actions
  // ===================================
  usePageHeader({
    title: t(K.page.mcpMarketplace.title),
    subtitle: t(K.page.mcpMarketplace.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: loadPackages,
    },
    {
      key: 'discover',
      label: t(K.page.mcpMarketplace.discoverServers),
      variant: 'contained',
      onClick: loadPackages,
    },
  ])

  return (
    <>
      {/* P1-13: Filter Bar */}
      <FilterBar
        filters={[
          {
            width: 6,
            component: (
              <TextField
                label={t(K.common.search)}
                placeholder={t(K.page.mcpMarketplace.searchPlaceholder)}
                fullWidth
                size={SIZE_SMALL}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            ),
          },
          {
            width: 3,
            component: (
              <Select
                label={t(K.page.mcpMarketplace.filterCategory)}
                fullWidth
                size={SIZE_SMALL}
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
              >
                <MenuItem value={SELECT_VALUE_ALL}>{t(K.page.mcpMarketplace.categoryAll)}</MenuItem>
                {categories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            ),
          },
          {
            width: 3,
            component: (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={connectedOnly}
                    onChange={(e) => setConnectedOnly(e.target.checked)}
                  />
                }
                label={t(K.page.mcpMarketplace.connectedOnly)}
              />
            ),
          },
        ]}
        actions={[
          {
            key: 'clear',
            label: t(K.page.mcpMarketplace.clearFilters),
            onClick: handleClearFilters,
          },
        ]}
      />

      {/* Card Grid */}
      <CardCollectionWrap layout={LAYOUT_GRID} columns={3} gap={16} loading={loading}>
        {filteredPackages.length === 0 && !loading ? (
          <Box sx={{ gridColumn: '1 / -1', textAlign: 'center', py: 8 }}>
            <Typography variant={VARIANT_BODY1} color={COLOR_TEXT_SECONDARY}>
              {t(K.page.mcpMarketplace.noPackages)}
            </Typography>
          </Box>
        ) : (
          filteredPackages.map((pkg) => (
            <ItemCard
              key={pkg.package_id}
              title={pkg.name}
              description={pkg.description}
              meta={[
                { key: 'version', label: t(K.page.mcpMarketplace.metaVersion), value: pkg.version },
                { key: 'author', label: t(K.page.mcpMarketplace.metaAuthor), value: pkg.author },
                {
                  key: 'trust_tier',
                  label: t(K.page.mcpMarketplace.metaTrustTier),
                  value: pkg.recommended_trust_tier,
                },
              ]}
              tags={[
                ...(pkg.is_connected
                  ? [t(K.page.mcpMarketplace.statusConnected)]
                  : [t(K.page.mcpMarketplace.statusAvailable)]),
                ...pkg.tags,
              ]}
              icon={getIcon(pkg.tags)}
              actions={[
                {
                  key: 'view',
                  label: t(K.page.mcpMarketplace.actionView),
                  variant: 'outlined',
                  onClick: () => handleViewPackage(pkg),
                },
                {
                  key: 'install',
                  label: t(K.page.mcpMarketplace.actionInstall),
                  variant: 'contained',
                  onClick: () => handleInstallClick(pkg),
                  disabled: pkg.is_connected,
                },
                ...(pkg.is_connected
                  ? [
                      {
                        key: 'uninstall',
                        label: t(K.page.mcpMarketplace.actionUninstall),
                        variant: 'outlined' as const,
                        onClick: () => handleUninstallClick(pkg),
                      },
                    ]
                  : []),
              ]}
              onClick={() => handleViewPackage(pkg)}
            />
          ))
        )}
      </CardCollectionWrap>

      {/* P0-12: Detail Drawer */}
      <DetailDrawer
        open={detailDrawerOpen}
        onClose={handleCloseDetailDrawer}
        title={selectedPackage?.name || ''}
        subtitle={selectedPackage?.version || ''}
        actions={
          selectedPackage && (
            <Box sx={{ display: 'flex', gap: 1 }}>
              {selectedPackage.is_connected ? (
                <Button
                  variant={VARIANT_OUTLINED}
                  color={COLOR_ERROR}
                  onClick={() => handleUninstallClick({
                    package_id: selectedPackage.package_id,
                    name: selectedPackage.name,
                    version: selectedPackage.version,
                    author: selectedPackage.author,
                    description: selectedPackage.description,
                    transport: selectedPackage.transport,
                    recommended_trust_tier: selectedPackage.recommended_trust_tier,
                    requires_admin_token: selectedPackage.requires_admin_token,
                    is_connected: selectedPackage.is_connected,
                    tags: selectedPackage.tags,
                  })}
                >
                  {t(K.page.mcpMarketplace.actionUninstall)}
                </Button>
              ) : (
                <Button
                  variant={VARIANT_CONTAINED}
                  onClick={() => handleInstallClick({
                    package_id: selectedPackage.package_id,
                    name: selectedPackage.name,
                    version: selectedPackage.version,
                    author: selectedPackage.author,
                    description: selectedPackage.description,
                    transport: selectedPackage.transport,
                    recommended_trust_tier: selectedPackage.recommended_trust_tier,
                    requires_admin_token: selectedPackage.requires_admin_token,
                    is_connected: selectedPackage.is_connected,
                    tags: selectedPackage.tags,
                  })}
                >
                  {t(K.page.mcpMarketplace.actionInstall)}
                </Button>
              )}
            </Box>
          )
        }
      >
        {selectedPackage && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Status Badge */}
            <Box>
              <Chip
                icon={selectedPackage.is_connected ? <CheckCircleIcon /> : undefined}
                label={
                  selectedPackage.is_connected
                    ? t(K.page.mcpMarketplace.statusConnected)
                    : t(K.page.mcpMarketplace.statusAvailable)
                }
                color={selectedPackage.is_connected ? COLOR_SUCCESS : COLOR_DEFAULT}
                size={SIZE_SMALL}
              />
            </Box>

            {/* Description */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.mcpMarketplace.detailDescription)}
              </Typography>
              <Typography variant={VARIANT_BODY2}>{selectedPackage.description}</Typography>
            </Box>

            {/* Long Description */}
            {selectedPackage.long_description && (
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                  {t(K.page.mcpMarketplace.detailLongDescription)}
                </Typography>
                <Typography
                  variant={VARIANT_BODY2}
                  sx={{ whiteSpace: 'pre-line' }}
                >
                  {selectedPackage.long_description}
                </Typography>
              </Box>
            )}

            {/* Metadata */}
            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.mcpMarketplace.metaAuthor)}
              </Typography>
              <Typography variant={VARIANT_BODY2}>{selectedPackage.author}</Typography>
            </Box>

            <Box>
              <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                {t(K.page.mcpMarketplace.detailTransport)}
              </Typography>
              <Typography variant={VARIANT_BODY2}>{selectedPackage.transport}</Typography>
            </Box>

            {selectedPackage.license && (
              <Box>
                <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                  {t(K.page.mcpMarketplace.detailLicense)}
                </Typography>
                <Typography variant={VARIANT_BODY2}>{selectedPackage.license}</Typography>
              </Box>
            )}

            {/* Links */}
            {(selectedPackage.homepage || selectedPackage.repository) && (
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                {selectedPackage.homepage && (
                  <Link href={selectedPackage.homepage} target={LINK_TARGET_BLANK} rel={LINK_REL_NOOPENER}>
                    {t(K.page.mcpMarketplace.detailHomepage)}
                  </Link>
                )}
                {selectedPackage.repository && (
                  <Link href={selectedPackage.repository} target={LINK_TARGET_BLANK} rel={LINK_REL_NOOPENER}>
                    {t(K.page.mcpMarketplace.detailRepository)}
                  </Link>
                )}
              </Box>
            )}

            <Divider />

            {/* P0-13: Governance Preview */}
            {governance && (
              <Box>
                <Typography variant={VARIANT_H6} gutterBottom>
                  {t(K.page.mcpMarketplace.detailGovernance)}
                </Typography>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                  <Box>
                    <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                      {t(K.page.mcpMarketplace.detailTrustTier)}
                    </Typography>
                    <Typography variant={VARIANT_BODY2}>{governance.inferred_trust_tier}</Typography>
                  </Box>

                  <Box>
                    <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY}>
                      {t(K.page.mcpMarketplace.detailRiskLevel)}
                    </Typography>
                    <Chip
                      label={governance.inferred_risk_level}
                      color={
                        governance.inferred_risk_level === 'HIGH'
                          ? COLOR_ERROR
                          : governance.inferred_risk_level === 'MEDIUM'
                          ? COLOR_WARNING
                          : COLOR_SUCCESS
                      }
                      size={SIZE_SMALL}
                    />
                  </Box>

                  <Box>
                    <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                      {t(K.page.mcpMarketplace.detailQuota)}
                    </Typography>
                    <Box sx={{ ml: 2 }}>
                      <Typography variant={VARIANT_BODY2}>
                        {t(K.page.mcpMarketplace.callsPerMinute)}{': '}{governance.default_quota.calls_per_minute}
                      </Typography>
                      <Typography variant={VARIANT_BODY2}>
                        {t(K.page.mcpMarketplace.maxConcurrent)}{': '}{governance.default_quota.max_concurrent}
                      </Typography>
                      <Typography variant={VARIANT_BODY2}>
                        {t(K.page.mcpMarketplace.maxRuntime)}{': '}{governance.default_quota.max_runtime_ms}{'ms'}
                      </Typography>
                    </Box>
                  </Box>

                  {governance.requires_admin_token_for.length > 0 && (
                    <Alert severity={SEVERITY_WARNING} icon={<WarningIcon />}>
                      <Typography variant={VARIANT_BODY2}>
                        {t(K.page.mcpMarketplace.requiresAdminTokenFor)}{': '}{governance.requires_admin_token_for.join(', ')}
                      </Typography>
                    </Alert>
                  )}

                  {governance.gate_warnings.length > 0 && (
                    <Box>
                      <Typography variant={VARIANT_CAPTION} color={COLOR_TEXT_SECONDARY} gutterBottom>
                        {t(K.page.mcpMarketplace.detailWarnings)}
                      </Typography>
                      {governance.gate_warnings.map((warning, idx) => (
                        <Alert key={idx} severity={SEVERITY_WARNING} sx={{ mt: 1 }}>
                          {warning}
                        </Alert>
                      ))}
                    </Box>
                  )}
                </Box>
              </Box>
            )}

            <Divider />

            {/* Tools */}
            <Box>
              <Typography variant={VARIANT_H6} gutterBottom>
                {t(K.page.mcpMarketplace.detailTools)}{' ('}{selectedPackage.tools.length}{')'}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                {selectedPackage.tools.map((tool, idx) => (
                  <Box key={idx} sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
                    <Typography variant={VARIANT_SUBTITLE2} gutterBottom>
                      {tool.name}
                    </Typography>
                    <Typography variant={VARIANT_BODY2} color={COLOR_TEXT_SECONDARY}>
                      {tool.description}
                    </Typography>
                    {tool.requires_confirmation && (
                      <Chip
                        label={t(K.page.mcpMarketplace.requiresConfirmation)}
                        size={SIZE_SMALL}
                        color={COLOR_WARNING}
                        sx={{ mt: 1 }}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Tags */}
            <Box>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {selectedPackage.tags.map((tag) => (
                  <Chip key={tag} label={tag} size={SIZE_SMALL} variant={VARIANT_OUTLINED} />
                ))}
              </Box>
            </Box>
          </Box>
        )}
      </DetailDrawer>

      {/* P0-14: Install Confirmation Dialog */}
      {packageToInstall && (
        <ConfirmDialog
          open={installDialogOpen}
          onClose={handleCancelInstall}
          title={t(K.page.mcpMarketplace.installDialogTitle)}
          message={[
            t(K.page.mcpMarketplace.installDialogMessage),
            '',
            `Package: ${packageToInstall.name}`,
            `Version: ${packageToInstall.version}`,
            `Trust Tier: ${packageToInstall.recommended_trust_tier}`,
          ].join('\n')}
          confirmText={t(K.page.mcpMarketplace.installDialogConfirm)}
          cancelText={t('common.cancel')}
          onConfirm={handleConfirmInstall}
          loading={installing}
          color={COLOR_PRIMARY}
        />
      )}

      {/* P2-5: Uninstall Confirmation Dialog */}
      {packageToUninstall && (
        <ConfirmDialog
          open={uninstallDialogOpen}
          onClose={handleCancelUninstall}
          title={t(K.page.mcpMarketplace.uninstallDialogTitle)}
          message={[
            t(K.page.mcpMarketplace.uninstallDialogMessage),
            '',
            `Package: ${packageToUninstall.name}`,
          ].join('\n')}
          confirmText={t(K.page.mcpMarketplace.uninstallDialogConfirm)}
          cancelText={t('common.cancel')}
          onConfirm={handleConfirmUninstall}
          loading={uninstalling}
          color={COLOR_ERROR}
        />
      )}
    </>
  )
}
