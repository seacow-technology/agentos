import React, { useState, useRef, useLayoutEffect } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
  Breadcrumbs,
  Link,
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
  PublicIcon,
  BuildIcon,
  HelpIcon,
  ShieldIcon,
  GavelIcon,
  SupervisedUserCircleIcon,
  HubIcon,
  RemoteControlIcon,
  TrendingUpIcon,
} from '@/ui/icons'
import {
  SHELL_GAP,
  SHELL_SURFACE,
  SHELL_SURFACE_SX,
  DRAWER_WIDTH,
  CONTENT_MAX_WIDTH,
} from '@/ui/layout/tokens'
import { PageHeaderProvider, PageHeaderBar } from '@/ui/layout'
import { t, K, changeLanguage, getCurrentLanguage } from '@/ui/text'
import { ThemeToggle, LanguageSwitch, ApiStatus, ApiStatusDialog } from '@/ui'
import { useApiHealth } from '@/hooks/useApiHealth'
import { useThemeMode } from '@/contexts/ThemeContext'

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
  { label: t(K.nav.chatReport), path: '/chat-report', icon: <AnalyticsIcon /> },
  { label: t(K.nav.voice), path: '/voice', icon: <PhoneIcon /> },

  // Control Section
  { label: t(K.nav.overview), path: '/overview', icon: <DashboardIcon />, divider: true },

  // Sessions Section
  { label: t(K.nav.sessions), path: '/sessions', icon: <HistoryIcon />, divider: true },

  // Observability Section
  { label: t(K.nav.projects), path: '/projects', icon: <FolderIcon />, divider: true },
  { label: t(K.nav.tasks), path: '/tasks', icon: <TaskIcon /> },
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
  { label: t(K.nav.auditLog), path: '/audit-log', icon: <AssignmentIcon /> },
  { label: t(K.nav.riskTimeline), path: '/risk-timeline', icon: <TimelineIcon /> },

  // Trust Section
  { label: t(K.nav.trustTier), path: '/trust-tier', icon: <ShieldIcon />, divider: true },
  { label: t(K.nav.trustTrajectory), path: '/trust-trajectory', icon: <TrendingUpIcon /> },
  { label: t(K.nav.publisherTrust), path: '/publisher-trust', icon: <SupervisedUserCircleIcon /> },

  // Network Section
  { label: t(K.nav.federatedNodes), path: '/federated-nodes', icon: <HubIcon />, divider: true },
  { label: t(K.nav.remoteControl), path: '/remote-control', icon: <RemoteControlIcon /> },

  // Communication Section
  { label: t(K.nav.channels), path: '/channels', icon: <ChatBubbleIcon />, divider: true },
  { label: t(K.nav.controlPanel), path: '/communication', icon: <PublicIcon /> },

  // System Section
  { label: t(K.nav.context), path: '/context', icon: <StorageIcon />, divider: true },
  { label: t(K.nav.runtime), path: '/runtime', icon: <BuildIcon /> },
  { label: t(K.nav.support), path: '/support', icon: <HelpIcon /> },

  // Settings Section
  { label: t(K.nav.extensions), path: '/extensions', icon: <ExtensionIcon />, divider: true },
  { label: t(K.nav.mcpMarketplace), path: '/mcp-marketplace', icon: <StoreIcon /> },
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
  const agentos = (theme.palette as any).agentos
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [mobileOpen, setMobileOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const headerStackRef = useRef<HTMLDivElement>(null)

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

  // 检测是否为特殊页面（不受宽度限制，高度拉满）
  const isFullscreenPage = location.pathname === '/chat'

  // Drawer content
  const drawer = (
    <>
      {/* Toolbar 占位（匹配 AppBar 高度） */}
      <Toolbar />
      <Box sx={{ height: SHELL_GAP * 2 }} />

      {/* Sidebar Header */}
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" fontWeight="bold">
          AgentOS v2
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Modern Control Surface
        </Typography>
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
        <Typography variant="caption" color="text.secondary">
          AgentOS WebUI v2.0
        </Typography>
      </Box>
    </>
  )

  return (
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
        <Box sx={{ height: `calc(var(--ui-header-stack-h, 0px) + ${SHELL_GAP * 2}px)` }} />

        {/* 🎨 内容区域 - Chat 页面特殊处理 */}
        {isFullscreenPage ? (
          // Chat 页面：无宽度限制，无滚动容器，高度拉满
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0, // 防止内容撑破
              overflow: 'hidden',
            }}
          >
            <Outlet />
          </Box>
        ) : (
          // 普通页面：滚动容器 + 宽度约束
          <Box
            sx={{
              flex: 1,
              overflow: 'auto',
              px: 3, // 24px 左右内边距
              pb: 3, // 24px 底部内边距

              // 隐藏滚动条但保持滚动功能
              '&::-webkit-scrollbar': {
                display: 'none',
              },
              scrollbarWidth: 'none', // Firefox
              msOverflowStyle: 'none', // IE
            }}
          >
            {/* 🔒 内容最大宽度约束 */}
            <Box sx={{ maxWidth: CONTENT_MAX_WIDTH, mx: 'auto' }}>
              {/* Outlet: 页面内容 */}
              {/* PageHeader 已在 AppBar HeaderSurface 中渲染 */}
              <Outlet />
            </Box>
          </Box>
        )}

        {/* ===================================
            🎨 FooterBar - 浮层条风格
            ===================================
            v2.3 关键特性：
            - 独立的 Bar，与 AppBar/PageHeaderBar 同级、同风格
            - 使用 SHELL_SURFACE token（elevation/gap/borderRadius）
            - 内容宽度约束：CONTENT_MAX_WIDTH
        */}
        <Box component="footer" sx={{ px: `${SHELL_GAP}px`, pb: `${SHELL_GAP}px` }}>
          <Paper
            elevation={SHELL_SURFACE.elevation}
            sx={{
              // 🎨 ShellSurface 统一 sx（与 AppBar/PageHeaderBar 完全一致）
              ...SHELL_SURFACE_SX,
              // ✅ 使用 AgentOS tokens 适配暗色主题
              bgcolor: agentos?.bg?.surface || 'background.default',

              // FooterBar 内边距
              px: 3,
              py: 2,
            }}
          >
            {/* 🔒 内容最大宽度约束 */}
            <Box sx={{ maxWidth: CONTENT_MAX_WIDTH }}>
              <Typography variant="body2" color="text.secondary">
                Build: v2.0.0-alpha | AgentOS WebUI v2
              </Typography>
            </Box>
          </Paper>
        </Box>
      </Box>
    </Box>

    {/* ===================================
        API Status Details Dialog
        =================================== */}
    <ApiStatusDialog
      open={apiDialogOpen}
      onClose={handleApiDialogClose}
      status={apiStatus}
      lastCheck={lastCheck}
      details={details?.details || null}
      error={error}
      onRefresh={refresh}
    />
    </PageHeaderProvider>
  )
}
