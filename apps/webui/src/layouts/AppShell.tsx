import React, { useState, useRef, useLayoutEffect, useEffect, lazy, Suspense } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Popover,
  Paper,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
  Breadcrumbs,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
} from '@mui/material'
import {
  MenuIcon,
  DashboardIcon,
  ScienceIcon,
  DocumentIcon,
  InfoIcon,
  ChatIcon,
  PhoneIcon,
  VisibilityIcon,
  HistoryIcon,
  FolderIcon,
  TaskIcon,
  EventIcon,
  TimelineIcon,
  ExtensionIcon,
  StorageIcon,
  CodeIcon,
  CommentIcon,
  PersonIcon,
  SearchIcon,
  FavoriteIcon,
  WorkIcon,
  AnalyticsIcon,
  EditIcon,
  InventoryIcon,
  LinkIcon,
  AssignmentIcon,
  PlayIcon,
  StoreIcon,
  CloudIcon,
  SettingsIcon,
  IntegrationIcon,
  ChatBubbleIcon,
  EmailIcon,
  PublicIcon,
  BuildIcon,
  HelpIcon,
  ShieldIcon,
  GavelIcon,
  SupervisedUserCircleIcon,
  HubIcon,
  RemoteControlIcon,
  TrendingUpIcon,
  LockIcon,
  LockOpenIcon,
  TerminalIcon,
} from '@/ui/icons'
import {
  SHELL_GAP,
  SHELL_SURFACE,
  SHELL_SURFACE_SX,
  DRAWER_WIDTH,
} from '@/ui/layout/tokens'
import { PageHeaderProvider, PageHeaderBar } from '@/ui/layout'
import { t, K, changeLanguage, getCurrentLanguage } from '@/ui/text'
import { ThemeToggle, LanguageSwitch, ApiStatus, ApiStatusDialog } from '@/ui'
import { FrontdeskChatProvider } from '@/features/frontdesk'
import { FabChatLauncher } from '@/components/app/FabChatLauncher'
import { SystemStatusChip } from '@/components/system/SystemStatusChip'
import { useSystemStatus } from '@/features/systemStatus/useSystemStatus'
import { useApiHealth } from '@/hooks/useApiHealth'
import { useThemeMode } from '@/contexts/ThemeContext'
import { appInfo } from '@/platform/config'
import { clearToken, getToken, setToken } from '@/platform/auth/adminToken'
import { get } from '@/platform/http'
import { systemService } from '@services/system.service'
import { TerminalDrawer } from '@/components/terminal/TerminalDrawer'

const FrontdeskDrawer = lazy(() =>
  import('@/features/frontdesk/FrontdeskDrawer').then((mod) => ({
    default: mod.FrontdeskDrawer,
  }))
)

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  divider?: boolean // 分隔线标记
}

/**
 * 🔄 v2.2: 从 WebUI v1 迁移的完整菜单
 *
 * 顺序：
 * 1. Home（保持）
 * 2. Chat Section
 * 3. Control Section
 * 4. Sessions Section
 * 5. Observability Section
 * 6. Agent Section
 * 7. Knowledge Section
 * 8. Quality Section
 * 9. Governance Section (含 Policy Editor, Marketplace Registry, Review Queue)
 * 10. Capabilities v3 Section
 * 11. Trust Section (Trust Tier, Trust Trajectory, Publisher Trust)
 * 12. Network Section (Federated Nodes, Remote Control)
 * 13. Communication Section
 * 14. System Section
 * 15. Settings Section
 * 16. Dev Tools (Components)
 */
const getNavItems = (): NavItem[] => [
  // Home
  { label: t(K.nav.home), path: '/', icon: <DashboardIcon /> },

  // Chat Section
  { label: t(K.nav.chat), path: '/chat', icon: <ChatIcon />, divider: true },
  { label: t(K.nav.work), path: '/chat/work', icon: <WorkIcon /> },
  { label: t(K.nav.workList), path: '/work-list', icon: <AssignmentIcon /> },
  { label: t(K.nav.taskList), path: '/task-list', icon: <TaskIcon /> },
  { label: t(K.nav.coding), path: '/coding', icon: <CodeIcon /> },
  { label: t(K.nav.chatReport), path: '/chat-report', icon: <AnalyticsIcon /> },
  { label: t(K.nav.voice), path: '/voice', icon: <PhoneIcon /> },

  // Control Section
  { label: t(K.nav.overview), path: '/overview', icon: <DashboardIcon />, divider: true },

  // Sessions Section
  { label: t(K.nav.sessions), path: '/sessions', icon: <HistoryIcon />, divider: true },

  // Observability Section
  { label: t(K.nav.projects), path: '/projects', icon: <FolderIcon />, divider: true },
  { label: t(K.nav.tasks), path: '/tasks', icon: <TaskIcon /> },
  { label: t(K.nav.awsOps), path: '/aws', icon: <CloudIcon /> },
  { label: t(K.nav.events), path: '/events', icon: <EventIcon /> },
  { label: t(K.nav.logs), path: '/logs', icon: <DocumentIcon /> },
  { label: t(K.nav.history), path: '/history', icon: <HistoryIcon /> },
  { label: t(K.nav.pipeline), path: '/pipeline', icon: <IntegrationIcon /> },
  { label: t(K.nav.modeMonitor), path: '/mode-monitor', icon: <VisibilityIcon /> },

  // Agent Section
  { label: t(K.nav.skills), path: '/skills', icon: <ExtensionIcon />, divider: true },
  { label: t(K.nav.skillsMarketplace), path: '/skills-marketplace', icon: <StoreIcon /> },
  { label: t(K.nav.memory), path: '/memory', icon: <StorageIcon /> },
  { label: t(K.nav.memoryProposals), path: '/memory-proposals', icon: <InfoIcon /> },
  { label: t(K.nav.memoryTimeline), path: '/memory-timeline', icon: <TimelineIcon /> },
  { label: t(K.nav.snippets), path: '/snippets', icon: <CodeIcon /> },
  { label: t(K.nav.answers), path: '/answers', icon: <CommentIcon /> },
  { label: t(K.nav.authProfiles), path: '/auth-profiles', icon: <PersonIcon /> },

  // Knowledge Section
  { label: t(K.nav.brainOS), path: '/brain', icon: <ScienceIcon />, divider: true },
  { label: t(K.nav.queryPlayground), path: '/query-playground', icon: <SearchIcon /> },
  { label: t(K.nav.sources), path: '/sources', icon: <FolderIcon /> },
  { label: t(K.nav.health), path: '/health', icon: <FavoriteIcon /> },
  { label: t(K.nav.indexJobs), path: '/index-jobs', icon: <WorkIcon /> },
  { label: t(K.nav.subgraph), path: '/subgraph', icon: <IntegrationIcon /> },

  // Quality Section
  { label: t(K.nav.infoneedMetrics), path: '/info-need-metrics', icon: <AnalyticsIcon />, divider: true },

  // Governance Section
  { label: t(K.nav.governance), path: '/governance', icon: <AssignmentIcon />, divider: true },
  { label: t(K.nav.findings), path: '/findings', icon: <SearchIcon /> },
  { label: t(K.nav.leadScans), path: '/lead-scans', icon: <SearchIcon /> },
  { label: t(K.nav.decisionReview), path: '/decision-review', icon: <AssignmentIcon /> },
  { label: t(K.nav.reviewQueue), path: '/review-queue', icon: <AssignmentIcon /> },
  { label: t(K.nav.executionPlans), path: '/execution-plans', icon: <PlayIcon /> },
  { label: t(K.nav.intentWorkbench), path: '/intent-workbench', icon: <EditIcon /> },
  { label: t(K.nav.policyEditor), path: '/policy-editor', icon: <GavelIcon /> },
  { label: t(K.nav.contentRegistry), path: '/content-registry', icon: <InventoryIcon /> },
  { label: t(K.nav.answerPacks), path: '/answer-packs', icon: <InventoryIcon /> },
  { label: t(K.nav.marketplaceRegistry), path: '/marketplace-registry', icon: <StoreIcon /> },

  // Capabilities v3 Section
  { label: t(K.nav.capabilities), path: '/capabilities', icon: <DashboardIcon />, divider: true },
  { label: t(K.nav.decisionTimeline), path: '/decision-timeline', icon: <TimelineIcon /> },
  { label: t(K.nav.actionLog), path: '/action-log', icon: <DocumentIcon /> },
  { label: t(K.nav.evidenceChains), path: '/evidence-chains', icon: <LinkIcon /> },
  { label: t(K.nav.externalFactsReplay), path: '/external-facts/replay', icon: <LinkIcon /> },
  { label: t(K.nav.externalFactsPolicy), path: '/external-facts/policy', icon: <SettingsIcon /> },
  { label: t(K.nav.externalFactsProviders), path: '/external-facts/providers', icon: <CloudIcon /> },
  { label: t(K.nav.connectors), path: '/connectors', icon: <IntegrationIcon /> },
  { label: t(K.nav.factsSchema), path: '/facts/schema', icon: <SettingsIcon /> },
  { label: t(K.nav.auditLog), path: '/audit-log', icon: <AssignmentIcon /> },
  { label: t(K.nav.riskTimeline), path: '/risk-timeline', icon: <TimelineIcon /> },

  // Trust Section
  { label: t(K.nav.trustTier), path: '/trust-tier', icon: <ShieldIcon />, divider: true },
  { label: t(K.nav.trustTrajectory), path: '/trust-trajectory', icon: <TrendingUpIcon /> },
  { label: t(K.nav.publisherTrust), path: '/publisher-trust', icon: <SupervisedUserCircleIcon /> },

  // Network Section
  { label: t(K.nav.federatedNodes), path: '/federated-nodes', icon: <HubIcon />, divider: true },
  { label: t(K.nav.remoteControl), path: '/remote-control', icon: <RemoteControlIcon /> },
  { label: t(K.nav.sshHosts), path: '/ssh/hosts', icon: <HubIcon />, divider: true },
  { label: t(K.nav.sshConnections), path: '/ssh/connections', icon: <LinkIcon /> },
  { label: t(K.nav.sshKeychain), path: '/ssh/keychain', icon: <LockIcon /> },
  { label: t(K.nav.sshKnownHosts), path: '/ssh/known-hosts', icon: <ShieldIcon /> },
  { label: t(K.nav.sshSftp), path: '/ssh/sftp', icon: <FolderIcon /> },
  { label: t(K.nav.sshLogs), path: '/ssh/logs', icon: <DocumentIcon /> },
  { label: t(K.nav.sshProvider), path: '/ssh/provider', icon: <SettingsIcon /> },

  // Communication Section
  { label: t(K.nav.channels), path: '/channels', icon: <ChatBubbleIcon />, divider: true },
  { label: t(K.nav.emailChannel), path: '/channels/email', icon: <EmailIcon /> },
  { label: t(K.nav.wiki), path: '/wiki', icon: <DocumentIcon /> },
  { label: t(K.nav.teamsOrgs), path: '/channels/teams', icon: <ChatBubbleIcon /> },
  { label: t(K.nav.controlPanel), path: '/communication', icon: <PublicIcon /> },
  { label: t(K.nav.mcpMarketplace), path: '/mcp-marketplace', icon: <StoreIcon /> },
  { label: t(K.nav.networkAccess), path: '/network/access', icon: <CloudIcon /> },
  { label: t(K.nav.securityDevices), path: '/security/devices', icon: <ShieldIcon /> },

  // System Section
  { label: t(K.nav.context), path: '/context', icon: <StorageIcon />, divider: true },
  { label: t(K.nav.runtime), path: '/runtime', icon: <BuildIcon /> },
  { label: t(K.nav.support), path: '/support', icon: <HelpIcon /> },

  // Settings Section
  { label: t(K.nav.extensions), path: '/extensions', icon: <ExtensionIcon />, divider: true },
  { label: t(K.nav.models), path: '/models', icon: <ExtensionIcon /> },
  { label: t(K.nav.providers), path: '/providers', icon: <CloudIcon /> },
  { label: t(K.nav.config), path: '/config', icon: <SettingsIcon /> },
]

/**
 * AppShell - Main application layout shell
 *
 * 🎨 v2.2: Layout Contract 实体化
 *
 * 设计原则：
 * 1. **Sidebar**: 贴边实体结构 - 0 圆角、0 阴影、永远贴边（应用壳体）
 * 2. **AppBar/Footer**: 浮层卡片风格 - 使用 SHELL_SURFACE token（gap + borderRadius + elevation）
 * 3. **Main Content**: CONTENT_MAX_WIDTH 约束 + PageHeader 系统集成
 * 4. **统一常量**: 从 @/ui/layout/tokens 导入，禁止魔法数字
 *
 * 设计参考：MD3 / Vuexy 控制台风格
 * 目标：Layout 负责"形"，Page 只填"内容"
 */
export default function AppShell() {
  const theme = useTheme()
  const octopusos = (theme.palette as any).octopusos
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const headerStackRef = useRef<HTMLDivElement>(null)
  const isEmbedded = new URLSearchParams(location.search).get('embed') === '1'

  // ===================================
  // AppBar Actions State
  // ===================================
  // Theme mode (from ThemeContext)
  const { mode: themeMode, toggleTheme, setTheme } = useThemeMode()

  // Current language
  const [currentLanguage, setCurrentLanguage] = useState(() => getCurrentLanguage())

  // API health monitoring with automatic polling
  const { status: apiStatus, lastCheck, details, error, refresh } = useApiHealth({
    pollInterval: 30000, // 30 seconds
    enabled: true,
  })
  const { isRestricted } = useSystemStatus()
  const [adminDialogOpen, setAdminDialogOpen] = useState(false)
  const [adminTokenInput, setAdminTokenInput] = useState('')
  const [adminModeEnabled, setAdminModeEnabled] = useState(() => Boolean(getToken()))
  const [adminModeError, setAdminModeError] = useState('')
  const [validatingAdminToken, setValidatingAdminToken] = useState(false)
  const [workMode, setWorkMode] = useState<'reactive' | 'proactive' | 'silent_proactive'>('reactive')
  const [workModeAnchor, setWorkModeAnchor] = useState<HTMLElement | null>(null)
  const [terminalOpen, setTerminalOpen] = useState(false)

  const blurActiveElement = () => {
    const activeElement = document.activeElement
    if (activeElement instanceof HTMLElement) {
      activeElement.blur()
    }
  }

  const openAdminDialog = (tokenInput: string) => {
    blurActiveElement()
    setAdminTokenInput(tokenInput)
    setAdminModeError('')
    window.requestAnimationFrame(() => {
      setAdminDialogOpen(true)
    })
  }

  useEffect(() => {
    if (!import.meta.env.DEV) return
    console.debug('[ApiHealth][AppShell] status changed', {
      apiStatus,
      lastCheck: lastCheck ? lastCheck.toISOString() : null,
      error: error?.message ?? null,
      hasDetails: !!details,
      isRestricted,
    })
  }, [apiStatus, lastCheck, error, details, isRestricted])

  useEffect(() => {
    const refreshAdminMode = () => {
      setAdminModeEnabled(Boolean(getToken()))
    }
    const onRequireAdminToken = () => {
      openAdminDialog(getToken() || '')
    }
    window.addEventListener('focus', refreshAdminMode)
    window.addEventListener('octopusos:admin-token-required', onRequireAdminToken as EventListener)
    return () => {
      window.removeEventListener('focus', refreshAdminMode)
      window.removeEventListener('octopusos:admin-token-required', onRequireAdminToken as EventListener)
    }
  }, [])

  useEffect(() => {
    let alive = true
    const refreshWorkMode = async () => {
      try {
        const resp: any = await systemService.resolveConfig('work.mode.global')
        const value = String(resp?.value || 'reactive')
        if (!alive) return
        if (value === 'reactive' || value === 'proactive' || value === 'silent_proactive') {
          setWorkMode(value)
        } else {
          setWorkMode('reactive')
        }
      } catch {
        // Best-effort; keep prior mode.
      }
    }
    void refreshWorkMode()
    const id = window.setInterval(() => void refreshWorkMode(), 10000)
    window.addEventListener('focus', refreshWorkMode)
    const onWorkModeUpdated = (e: any) => {
      const m = String(e?.detail?.mode || '')
      if (m === 'reactive' || m === 'proactive' || m === 'silent_proactive') {
        setWorkMode(m)
      }
    }
    window.addEventListener('octopusos:work-mode-updated', onWorkModeUpdated as EventListener)
    return () => {
      alive = false
      window.clearInterval(id)
      window.removeEventListener('focus', refreshWorkMode)
      window.removeEventListener('octopusos:work-mode-updated', onWorkModeUpdated as EventListener)
    }
  }, [])

  // API Status Dialog state
  const [apiDialogOpen, setApiDialogOpen] = useState(false)

  // Handle language change
  const handleLanguageChange = (lang: string) => {
    const newLang = lang as 'en' | 'zh'
    changeLanguage(newLang)
    setCurrentLanguage(newLang)
  }

  // Handle API status click - show details dialog
  const handleApiStatusClick = () => {
    setApiDialogOpen(true)
  }

  // Handle API dialog close
  const handleApiDialogClose = () => {
    setApiDialogOpen(false)
  }

  const handleOpenTerminal = () => {
    blurActiveElement()
    setTerminalOpen(true)
  }

  const handleOpenAdminDialog = () => openAdminDialog(getToken() || '')

  const handleCloseAdminDialog = () => {
    setAdminModeError('')
    setAdminDialogOpen(false)
  }

  const handleEnableAdminMode = async () => {
    const token = adminTokenInput.trim()
    if (!token) return
    setValidatingAdminToken(true)
    setAdminModeError('')
    try {
      const response = await get<{ ok: boolean; valid: boolean }>('/api/admin/token/validate', {
        headers: { 'X-Admin-Token': token },
      })
      if (!response?.ok || !response?.valid) {
        setAdminModeError(t(K.appBar.adminTokenInvalid))
        return
      }
      setToken(token)
      setAdminModeEnabled(true)
      setAdminDialogOpen(false)
    } catch (error) {
      setAdminModeError(t(K.appBar.adminTokenInvalid))
    } finally {
      setValidatingAdminToken(false)
    }
  }

  const handleDisableAdminMode = () => {
    clearToken()
    setAdminTokenInput('')
    setAdminModeEnabled(false)
    setAdminModeError('')
    setAdminDialogOpen(false)
  }

  // 🎨 v2.3: 动态测量 Header Stack 高度 → CSS 变量
  useLayoutEffect(() => {
    const el = headerStackRef.current
    if (!el) return

    let lastHeight = -1
    let rafId = 0

    const updateHeight = () => {
      const height = Math.ceil(el.getBoundingClientRect().height)

      // 护栏 1：高度不变不写（避免无意义的 CSS 变量更新）
      if (height === lastHeight) return

      lastHeight = height
      document.documentElement.style.setProperty('--ui-header-stack-h', `${height}px`)
    }

    // 护栏 2：用 rAF 合并多次触发（避免抖动/回流风暴）
    const scheduleUpdate = () => {
      cancelAnimationFrame(rafId)
      rafId = requestAnimationFrame(updateHeight)
    }

    // 初始测量
    updateHeight()

    // 监听尺寸变化（PageHeaderBar 显示/隐藏、内容换行等）
    const resizeObserver = new ResizeObserver(scheduleUpdate)
    resizeObserver.observe(el)

    return () => {
      cancelAnimationFrame(rafId)
      resizeObserver.disconnect()
    }
  }, [])

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const handleNavigation = (path: string) => {
    navigate(path)
    if (isMobile) {
      setMobileOpen(false)
    }
  }

  // Generate breadcrumbs from current path
  const generateBreadcrumbs = () => {
    const paths = location.pathname.split('/').filter(Boolean)
    const breadcrumbs = [{ label: t(K.nav.home), path: '/' }]

    let currentPath = ''
    const navItems = getNavItems()
    paths.forEach((segment) => {
      currentPath += `/${segment}`
      const navItem = navItems.find(item => item.path === currentPath)
      breadcrumbs.push({
        label: navItem?.label || segment.charAt(0).toUpperCase() + segment.slice(1),
        path: currentPath,
      })
    })

    return breadcrumbs
  }

  const breadcrumbs = generateBreadcrumbs()

  // 需要锁定外层滚动（避免双滚动）的页面
  const isScrollLockedPage =
    location.pathname === '/chat' ||
    location.pathname === '/chat/work' ||
    location.pathname === '/coding' ||
    location.pathname === '/changelog'

  // Drawer content
  const drawer = (
    <>
      {/* Toolbar 占位（匹配 AppBar 高度） */}
      <Toolbar />
      <Box sx={{ height: SHELL_GAP * 2 }} />

      {/* Sidebar Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
          <Box
            component="img"
            src="/octopus-logo.png"
            alt="Octopus OS logo"
            sx={{
              width: 32,
              height: 32,
              objectFit: 'contain',
              borderRadius: 1,
              flexShrink: 0,
            }}
          />
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="h6" fontWeight="bold" sx={{ lineHeight: 1.2 }}>
              {appInfo.productName}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Modern Control Surface
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Navigation List */}
      <List
        sx={{
          flex: 1,
          p: 1,
          overflowY: 'auto',
          overflowX: 'hidden', // ✅ 防止水平溢出
          // 隐藏滚动条
          scrollbarWidth: 'none', // Firefox
          '&::-webkit-scrollbar': {
            display: 'none', // Chrome/Safari/Edge
          },
        }}
      >
        {getNavItems().map((item, index) => (
          <React.Fragment key={item.path}>
            {/* 分隔线：当 divider=true 且不是第一个元素时显示 */}
            {item.divider && index > 0 && (
              <Divider sx={{ my: 1 }} />
            )}
            <ListItem disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => handleNavigation(item.path)}
                sx={{ borderRadius: 1 }}
              >
                <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{
                    sx: { fontSize: 14 }
                  }}
                />
              </ListItemButton>
            </ListItem>
          </React.Fragment>
        ))}
      </List>

      {/* Sidebar Footer */}
      <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
        <List disablePadding sx={{ mb: 1 }}>
          <ListItem disablePadding>
            <ListItemButton
              selected={location.pathname === '/changelog'}
              onClick={() => handleNavigation('/changelog')}
              sx={{ borderRadius: 1 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}><DocumentIcon /></ListItemIcon>
              <ListItemText
                primary={t(K.nav.changeLog)}
                primaryTypographyProps={{ sx: { fontSize: 14 } }}
              />
            </ListItemButton>
          </ListItem>
        </List>
        <Typography variant="caption" color="text.secondary">
          {appInfo.webuiName}
        </Typography>
      </Box>
    </>
  )

  // Product embedding mode: render only the route content (no drawer / header stack).
  // This is used by Desktop Product Shell which embeds Console pages in an iframe.
  if (isEmbedded) {
    return (
      <FrontdeskChatProvider>
        <PageHeaderProvider>
          <Box
            sx={{
              width: '100vw',
              height: '100vh',
              bgcolor: 'background.default',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ width: '100%', height: '100%', overflow: 'auto' }}>
              <Outlet />
            </Box>
          </Box>
        </PageHeaderProvider>
      </FrontdeskChatProvider>
    )
  }

  return (
    <FrontdeskChatProvider>
      <PageHeaderProvider>
      <Box
        sx={{
          display: 'flex',
          height: '100vh',
          bgcolor: 'background.default', // 使用 theme，不用 Tailwind bg
        }}
      >
        {/* ===================================
            🎨 AppBar - 浮层卡片风格
            ===================================
            v2.2 关键特性：
            - 使用 SHELL_SURFACE token（gap/borderRadius/elevation）
            - top: SHELL_SURFACE.gap（12px）- 不贴顶
            - left/right: SHELL_SURFACE.gap - 两侧留白
            - borderRadius: SHELL_SURFACE.borderRadius - 统一圆角
            - elevation: SHELL_SURFACE.elevation - 轻阴影
            - overflow: hidden - 让圆角生效更干净
            - left 避开 Sidebar（贴边，不需要额外 gap）
        */}
        {/* ===================================
            🎨 Header Stack - AppBar + PageHeaderBar
            ===================================
            v2.3 关键特性：
            - 外层 Box：fixed 定位，控制位置和宽度
            - 内层 Box：ref 容器，用于测量真实高度
            - 高度自动写入 CSS 变量 --ui-header-stack-h
        */}
        <Box
          position="fixed"
          sx={{
            top: `${SHELL_SURFACE.gap}px`,
            left: { xs: `${SHELL_SURFACE.gap}px`, md: `${DRAWER_WIDTH + SHELL_SURFACE.gap}px` },
            right: `${SHELL_SURFACE.gap}px`,
            // 🔒 z-index 修复: 使用 appBar (1020),确保低于 modal (1040)
            // 原值 drawer + 1 (1041) 会导致 AppBar 显示在 Dialog 遮罩层之上
            zIndex: (theme) => theme.zIndex.appBar,
          }}
        >
          <Box ref={headerStackRef} data-ui="header-stack">
            {/* Bar #1: AppBar */}
            <AppBar
              position="static"
              elevation={SHELL_SURFACE.elevation}
              sx={{
                // 🎨 ShellSurface 统一 sx（与 PageHeaderBar/FooterBar 完全一致）
                ...SHELL_SURFACE_SX,
              }}
            >
              <Toolbar sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                {/* Mobile menu button */}
                <IconButton
                  color="inherit"
                  aria-label={t(K.common.openDrawer)}
                  edge="start"
                  onClick={handleDrawerToggle}
                  sx={{ mr: 2, display: { md: 'none' } }}
                >
                  <MenuIcon />
                </IconButton>

                {/* Breadcrumbs */}
                <Breadcrumbs
                  aria-label={t(K.common.breadcrumb)}
                  sx={{
                    color: 'text.primary',  // Auto-adapt to theme
                    flexGrow: 1
                  }}
                >
                  {breadcrumbs.map((crumb, index) => {
                    const isLast = index === breadcrumbs.length - 1
                    return isLast ? (
                      <Typography key={crumb.path} color="inherit">
                        {crumb.label}
                      </Typography>
                    ) : (
                      <Link
                        key={crumb.path}
                        color="inherit"
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          handleNavigation(crumb.path)
                        }}
                        underline="hover"
                      >
                        {crumb.label}
                      </Link>
                    )
                  })}
                </Breadcrumbs>

                {/* AppBar Actions */}
                <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                  <Chip
                    size="small"
                    variant="outlined"
                    clickable
                    onClick={(e) => setWorkModeAnchor(e.currentTarget)}
                    label={`${t(K.appBar.workModeLabel)}: ${
                      workMode === 'proactive'
                        ? t(K.page.workList.modeProactive)
                        : workMode === 'silent_proactive'
                          ? t(K.page.workList.modeSilent)
                          : t(K.page.workList.modeReactive)
                    }`}
                  />
                  <Popover
                    open={Boolean(workModeAnchor)}
                    anchorEl={workModeAnchor}
                    onClose={() => setWorkModeAnchor(null)}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                  >
                    <Box sx={{ p: 2, maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="subtitle2">
                        {t(K.appBar.workModeLabel)}:{" "}
                        {workMode === 'proactive'
                          ? t(K.page.workList.modeProactive)
                          : workMode === 'silent_proactive'
                            ? t(K.page.workList.modeSilent)
                            : t(K.page.workList.modeReactive)}
                      </Typography>
                      <Typography variant="body2">{t(K.appBar.workModeReactiveDesc)}</Typography>
                      <Typography variant="body2">{t(K.appBar.workModeProactiveDesc)}</Typography>
                      <Typography variant="body2">{t(K.appBar.workModeSilentDesc)}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {t(K.page.workList.subtitle)}
                      </Typography>
                    </Box>
                  </Popover>
                  <SystemStatusChip />
                  <IconButton
                    onClick={handleOpenTerminal}
                    title={t(K.appBar.localTerminal)}
                    aria-label={t(K.appBar.localTerminal)}
                    data-testid="local-terminal-button"
                  >
                    <TerminalIcon />
                  </IconButton>
                  <IconButton
                    color={adminModeEnabled ? 'success' : 'default'}
                    onClick={handleOpenAdminDialog}
                    title={
                      adminModeEnabled
                        ? t(K.appBar.adminModeEnabled)
                        : t(K.appBar.adminModeDisabled)
                    }
                  >
                    {adminModeEnabled ? <LockOpenIcon /> : <LockIcon />}
                  </IconButton>
                  <ThemeToggle
                    mode={themeMode}
                    onToggle={toggleTheme}
                    onSetTheme={setTheme}
                  />
                  <LanguageSwitch
                    currentLanguage={currentLanguage}
                    onLanguageChange={handleLanguageChange}
                  />
                  <ApiStatus
                    status={apiStatus}
                    onClick={handleApiStatusClick}
                  />
                </Box>
              </Toolbar>
            </AppBar>

            {/* Gap between AppBar and PageHeaderBar */}
            <Box sx={{ height: `${SHELL_GAP}px` }} />

            {/* Bar #2: PageHeaderBar */}
            <PageHeaderBar />
          </Box>
        </Box>

        <TerminalDrawer open={terminalOpen} onClose={() => setTerminalOpen(false)} />

      {/* ===================================
          🎨 Sidebar - Mobile (temporary)
          ===================================
          移动端：全屏 Drawer，不需要浮层效果
      */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={handleDrawerToggle}
        ModalProps={{
          keepMounted: true, // Better mobile performance
        }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: DRAWER_WIDTH,
          },
        }}
      >
        {drawer}
      </Drawer>

      {/* ===================================
          🎨 Sidebar - Desktop (permanent)
          ===================================
          v2.2 策略：贴边实体结构
          - borderRadius: 0 - 禁止圆角
          - boxShadow: 'none' - 禁止阴影
          - borderRight: 1px 分割线
          - backgroundImage: 'none' - 无渐变
          - 100vh 高度，贴边，不浮动

          设计原则：Sidebar 是"应用壳体"，不是"浮层卡片"
      */}
      <Drawer
        variant="permanent"
        elevation={0}
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': {
            boxSizing: 'border-box',
            width: DRAWER_WIDTH,

            // 🔒 实体化锁定
            borderRadius: 0,
            boxShadow: 'none',
            borderRight: (theme) => `1px solid ${theme.palette.divider}`,
            backgroundImage: 'none',

            // 贴边满高
            height: '100vh',
            overflowX: 'hidden',
          },
        }}
        open
      >
        {drawer}
      </Drawer>

      {/* ===================================
          🎨 Main - 内容区
          ===================================
          v2.2 结构：
          - Spacer: APPBAR_HEIGHT + SHELL_GAP * 2
          - PageHeaderProvider: Layout 控制 PageHeader
          - PageHeader: Layout 渲染，页面只上报参数
          - Outlet: 页面内容（CONTENT_MAX_WIDTH 约束）
          - Footer: 浮层卡片
      */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: { md: `${DRAWER_WIDTH}px` },
          bgcolor: 'background.default',
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0, // 防止内容撑破导致横向滚动
        }}
      >
        {/* Spacer: 使用 CSS 变量，自动跟随 Header Stack 高度 */}
        {/* 🎨 v2.3.3: --ui-header-stack-h 由 ResizeObserver 自动更新 */}
        {/* Header Stack 包含：top gap + AppBar + gap + PageHeaderBar */}
        {/* 🎨 v2.3.3: 下方留 SHELL_GAP × 2 (24px) 呼吸区 */}
        <Box
          sx={{
            height: `calc(var(--ui-header-stack-h, 0px) + ${SHELL_GAP * 2}px)`,
          }}
        />

        {/* 🎨 内容区域 - 全页面统一全宽容器 */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0, // 防止内容撑破
            overflow: isScrollLockedPage ? 'hidden' : 'auto',
            px: `${SHELL_GAP}px`,
            pb: isScrollLockedPage ? 0 : 3, // 非 chat/coding 页面保留底部呼吸区

            // 隐藏滚动条但保持滚动功能
            '&::-webkit-scrollbar': {
              display: 'none',
            },
            scrollbarWidth: 'none', // Firefox
            msOverflowStyle: 'none', // IE
          }}
        >
          <Outlet />
        </Box>

        {/* ===================================
            🎨 FooterBar - 浮层条风格
            ===================================
            v2.3 关键特性：
            - 独立的 Bar，与 AppBar/PageHeaderBar 同级、同风格
            - 使用 SHELL_SURFACE token（elevation/gap/borderRadius）
            - 内容宽度约束：CONTENT_MAX_WIDTH
        */}
        <Box
          component="footer"
          sx={{
            px: `${SHELL_GAP}px`,
            pb: `${SHELL_GAP}px`,
            mt: isScrollLockedPage ? `${SHELL_GAP}px` : 0,
          }}
        >
          <Paper
            elevation={SHELL_SURFACE.elevation}
            sx={{
              // 🎨 ShellSurface 统一 sx（与 AppBar/PageHeaderBar 完全一致）
              ...SHELL_SURFACE_SX,
              // ✅ 使用 OctopusOS tokens 适配暗色主题
              bgcolor: octopusos?.bg?.surface || 'background.default',

              // FooterBar 内边距
              px: 3,
              py: 2,
            }}
          >
            <Typography variant="body2" color="text.secondary">
              Build: {appInfo.buildVersion} | Release: {appInfo.releaseVersion} | {appInfo.webuiName}
            </Typography>
          </Paper>
        </Box>
      </Box>
    </Box>

    {/* ===================================
        API Status Details Dialog
        =================================== */}
        <FabChatLauncher />
        <Suspense fallback={null}>
          <FrontdeskDrawer />
        </Suspense>

        <ApiStatusDialog
          open={apiDialogOpen}
          onClose={handleApiDialogClose}
          status={apiStatus}
          lastCheck={lastCheck}
          details={details?.details || null}
          error={error}
          onRefresh={refresh}
        />
        <Dialog open={adminDialogOpen} onClose={handleCloseAdminDialog} maxWidth="sm" fullWidth>
          <DialogTitle>{t(K.appBar.adminModeTitle)}</DialogTitle>
          <DialogContent>
            <TextField
              label={t(K.appBar.adminTokenLabel)}
              value={adminTokenInput}
              onChange={(e) => {
                setAdminModeError('')
                setAdminTokenInput(e.target.value)
              }}
              fullWidth
              size="small"
              sx={{ mt: 1 }}
              type="password"
              placeholder={t(K.appBar.adminTokenPlaceholder)}
              error={Boolean(adminModeError)}
              helperText={adminModeError || t(K.appBar.adminTokenHelp)}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={handleCloseAdminDialog}>{t(K.common.cancel)}</Button>
            {adminModeEnabled ? (
              <Button variant="contained" color="warning" onClick={handleDisableAdminMode}>
                {t(K.appBar.disableAdminMode)}
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleEnableAdminMode}
                disabled={!adminTokenInput.trim() || validatingAdminToken}
              >
                {validatingAdminToken ? t(K.appBar.validatingAdminToken) : t(K.appBar.enableAdminMode)}
              </Button>
            )}
          </DialogActions>
        </Dialog>
      </PageHeaderProvider>
    </FrontdeskChatProvider>
  )
}
