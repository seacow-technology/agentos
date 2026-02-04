import { CssBaseline } from '@mui/material'
import { Routes, Route } from 'react-router-dom'
import { SnackbarProvider } from 'notistack'
import HomePage from './pages/HomePage'
import { AppShell, AuthGate } from './layouts'
import { ThemeProvider } from './contexts/ThemeContext'
import ErrorBoundary from './components/ErrorBoundary'

// Chat Section
import ChatPage from './pages/ChatPage'
import ChatReportPage from './pages/ChatReportPage'
import VoicePage from './pages/VoicePage'

// Control Section
import OverviewPage from './pages/OverviewPage'

// Sessions Section
import SessionsPage from './pages/SessionsPage'

// Observability Section
import ProjectsPage from './pages/ProjectsPage'
import TasksPage from './pages/TasksPage'
import EventsPage from './pages/EventsPage'
import LogsPage from './pages/LogsPage'
import HistoryPage from './pages/HistoryPage'
import PipelinePage from './pages/PipelinePage'
import ModeMonitorPage from './pages/ModeMonitorPage'

// Agent Section
import SkillsPage from './pages/SkillsPage'
import SkillsMarketplacePage from './pages/SkillsMarketplacePage'
import MemoryPage from './pages/MemoryPage'
import MemoryProposalsPage from './pages/MemoryProposalsPage'
import MemoryTimelinePage from './pages/MemoryTimelinePage'
import MemoryEntriesPage from './pages/MemoryEntriesPage'
import SnippetsPage from './pages/SnippetsPage'
import AnswersPage from './pages/AnswersPage'
import AuthProfilesPage from './pages/AuthProfilesPage'
import ToolsPage from './pages/ToolsPage'
import TriggersPage from './pages/TriggersPage'

// Knowledge Section
import BrainPage from './pages/BrainPage'
import BrainDashboardPage from './pages/BrainDashboardPage'
import QueryPlaygroundPage from './pages/QueryPlaygroundPage'
import SourcesPage from './pages/SourcesPage'
import HealthPage from './pages/HealthPage'
import KnowledgeHealthPage from './pages/KnowledgeHealthPage'
import IndexJobsPage from './pages/IndexJobsPage'
import SubgraphPage from './pages/SubgraphPage'
import DatasourcesPage from './pages/DatasourcesPage'
import ProvenancePage from './pages/ProvenancePage'

// Quality Section
import InfoNeedMetricsPage from './pages/InfoNeedMetricsPage'

// Governance Section
import GovernancePage from './pages/GovernancePage'
import FindingsPage from './pages/FindingsPage'
import LeadScansPage from './pages/LeadScansPage'
import DecisionReviewPage from './pages/DecisionReviewPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import ExecutionPlansPage from './pages/ExecutionPlansPage'
import IntentWorkbenchPage from './pages/IntentWorkbenchPage'
import ContentRegistryPage from './pages/ContentRegistryPage'
import AnswerPacksPage from './pages/AnswerPacksPage'
import PolicyEditorPage from './pages/PolicyEditorPage'
import MarketplaceRegistryPage from './pages/MarketplaceRegistryPage'
import EvolutionDecisionsPage from './pages/EvolutionDecisionsPage'
import BudgetConfigPage from './pages/BudgetConfigPage'

// Capabilities v3 Section
import CapabilitiesPage from './pages/CapabilitiesPage'
import DecisionTimelinePage from './pages/DecisionTimelinePage'
import ActionLogPage from './pages/ActionLogPage'
import EvidenceChainsPage from './pages/EvidenceChainsPage'
import AuditLogPage from './pages/AuditLogPage'
import TrustTierPage from './pages/TrustTierPage'
import TrustTrajectoryPage from './pages/TrustTrajectoryPage'
import RiskTimelinePage from './pages/RiskTimelinePage'
import FederatedNodesView from './pages/FederatedNodesView'
import PublisherTrustView from './pages/PublisherTrustView'
import RemoteControlPage from './pages/RemoteControlPage'

// Settings Section
import ExtensionsPage from './pages/ExtensionsPage'
import McpMarketplacePage from './pages/McpMarketplacePage'
import ModelsPage from './pages/ModelsPage'
import ProvidersPage from './pages/ProvidersPage'
import ConfigPage from './pages/ConfigPage'
import ConfigEntriesPage from './pages/ConfigEntriesPage'
import PluginsPage from './pages/PluginsPage'

// Communication Section
import ChannelsPage from './pages/ChannelsPage'
import CommunicationPage from './pages/CommunicationPage'
import MessagesPage from './pages/MessagesPage'
import NotificationsPage from './pages/NotificationsPage'

// System Section
import ContextPage from './pages/ContextPage'
import RuntimePage from './pages/RuntimePage'
import SupportPage from './pages/SupportPage'
import SystemHealthPage from './pages/SystemHealthPage'
import DemoModePage from './pages/DemoModePage'
import UsersPage from './pages/UsersPage'

// 404 Not Found
import NotFoundPage from './pages/NotFoundPage'

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <CssBaseline />
        <SnackbarProvider
          maxSnack={3}
          anchorOrigin={{
            vertical: 'top',
            horizontal: 'right',
          }}
          autoHideDuration={3000}
        >
        <Routes>
        {/* Routes with AppShell layout */}
        <Route
          element={
            <AuthGate>
              <AppShell />
            </AuthGate>
          }
        >
          <Route path="/" element={<HomePage />} />

          {/* Chat Section */}
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat-report" element={<ChatReportPage />} />
          <Route path="/voice" element={<VoicePage />} />

          {/* Control Section */}
          <Route path="/overview" element={<OverviewPage />} />

          {/* Sessions Section */}
          <Route path="/sessions" element={<SessionsPage />} />

          {/* Observability Section */}
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/mode-monitor" element={<ModeMonitorPage />} />

          {/* Agent Section */}
          <Route path="/skills" element={<SkillsPage />} />
          <Route path="/skills-marketplace" element={<SkillsMarketplacePage />} />
          <Route path="/memory" element={<MemoryPage />} />
          <Route path="/memory-proposals" element={<MemoryProposalsPage />} />
          <Route path="/memory-timeline" element={<MemoryTimelinePage />} />
          <Route path="/memory-entries" element={<MemoryEntriesPage />} />
          <Route path="/snippets" element={<SnippetsPage />} />
          <Route path="/answers" element={<AnswersPage />} />
          <Route path="/auth-profiles" element={<AuthProfilesPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/triggers" element={<TriggersPage />} />

          {/* Knowledge Section */}
          <Route path="/brain" element={<BrainPage />} />
          <Route path="/brain-dashboard" element={<BrainDashboardPage />} />
          <Route path="/query-playground" element={<QueryPlaygroundPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/datasources" element={<DatasourcesPage />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/knowledge-health" element={<KnowledgeHealthPage />} />
          <Route path="/index-jobs" element={<IndexJobsPage />} />
          <Route path="/subgraph" element={<SubgraphPage />} />
          <Route path="/provenance" element={<ProvenancePage />} />

          {/* Quality Section */}
          <Route path="/infoneed-metrics" element={<InfoNeedMetricsPage />} />
          <Route path="/info-need-metrics" element={<InfoNeedMetricsPage />} />

          {/* Governance Section */}
          <Route path="/governance" element={<GovernancePage />} />
          <Route path="/findings" element={<FindingsPage />} />
          <Route path="/lead-scans" element={<LeadScansPage />} />
          <Route path="/decision-review" element={<DecisionReviewPage />} />
          <Route path="/review-queue" element={<ReviewQueuePage />} />
          <Route path="/execution-plans" element={<ExecutionPlansPage />} />
          <Route path="/intent-workbench" element={<IntentWorkbenchPage />} />
          <Route path="/content-registry" element={<ContentRegistryPage />} />
          <Route path="/answer-packs" element={<AnswerPacksPage />} />
          <Route path="/policy-editor" element={<PolicyEditorPage />} />
          <Route path="/marketplace-registry" element={<MarketplaceRegistryPage />} />
          <Route path="/evolution-decisions" element={<EvolutionDecisionsPage />} />
          <Route path="/budget-config" element={<BudgetConfigPage />} />

          {/* Capabilities v3 Section */}
          <Route path="/capabilities" element={<CapabilitiesPage />} />
          <Route path="/decision-timeline" element={<DecisionTimelinePage />} />
          <Route path="/action-log" element={<ActionLogPage />} />
          <Route path="/evidence-chains" element={<EvidenceChainsPage />} />
          <Route path="/audit-log" element={<AuditLogPage />} />
          <Route path="/trust-tier" element={<TrustTierPage />} />
          <Route path="/trust-trajectory" element={<TrustTrajectoryPage />} />
          <Route path="/risk-timeline" element={<RiskTimelinePage />} />
          <Route path="/federated-nodes" element={<FederatedNodesView />} />
          <Route path="/publisher-trust" element={<PublisherTrustView />} />
          <Route path="/remote-control" element={<RemoteControlPage />} />

          {/* Communication Section */}
          <Route path="/channels" element={<ChannelsPage />} />
          <Route path="/communication" element={<CommunicationPage />} />
          <Route path="/messages" element={<MessagesPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />

          {/* System Section */}
          <Route path="/context" element={<ContextPage />} />
          <Route path="/runtime" element={<RuntimePage />} />
          <Route path="/support" element={<SupportPage />} />
          <Route path="/system-health" element={<SystemHealthPage />} />
          <Route path="/demo-mode" element={<DemoModePage />} />
          <Route path="/users" element={<UsersPage />} />

          {/* Settings Section */}
          <Route path="/extensions" element={<ExtensionsPage />} />
          <Route path="/mcp-marketplace" element={<McpMarketplacePage />} />
          <Route path="/models" element={<ModelsPage />} />
          <Route path="/providers" element={<ProvidersPage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/config-entries" element={<ConfigEntriesPage />} />
          <Route path="/plugins" element={<PluginsPage />} />

          {/* 404 Not Found - Catch all unmatched routes */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        </Routes>
        </SnackbarProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

export default App
