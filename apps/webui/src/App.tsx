import { CssBaseline } from '@mui/material'
import { Routes, Route, Navigate } from 'react-router-dom'
import { SnackbarProvider } from 'notistack'
import { Suspense, lazy } from 'react'
import { LoadingState } from '@/components'
import { GlobalButtonTooltipProvider } from '@/components/GlobalButtonTooltipProvider'
import AuthGate from './layouts/AuthGate'
import { ThemeProvider } from './contexts/ThemeContext'
import ErrorBoundary from './components/ErrorBoundary'

const HomePage = lazy(() => import('./pages/HomePage'))
const AppShell = lazy(() => import('./layouts/AppShell'))

// Chat Section
const ChatPage = lazy(() => import('./pages/ChatPage'))
const WorkPage = lazy(() => import('./pages/WorkPage'))
const WorkListPage = lazy(() => import('./pages/WorkListPage'))
const TaskListPage = lazy(() => import('./pages/TaskListPage'))
const ChangeLogPage = lazy(() => import('./pages/ChangeLogPage'))
const WikiPage = lazy(() => import('./pages/WikiPage'))
const CodingPage = lazy(() => import('./pages/CodingPage'))
const ChatReportPage = lazy(() => import('./pages/ChatReportPage'))
const DispatchReviewQueuePage = lazy(() => import('./pages/DispatchReviewQueuePage'))
const VoicePage = lazy(() => import('./pages/VoicePage'))
const ExternalFactsReplayPage = lazy(() => import('./pages/ExternalFactsReplayPage'))
const ExternalFactsPolicyPage = lazy(() => import('./pages/ExternalFactsPolicyPage'))
const ExternalFactsProvidersPage = lazy(() => import('./pages/ExternalFactsProvidersPage'))
const ConnectorsPage = lazy(() => import('./pages/ConnectorsPage'))
const FactsSchemaPage = lazy(() => import('./pages/FactsSchemaPage'))

// Control Section
const OverviewPage = lazy(() => import('./pages/OverviewPage'))

// Sessions Section
const SessionsPage = lazy(() => import('./pages/SessionsPage'))

// Observability Section
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))
const TasksPage = lazy(() => import('./pages/TasksPage'))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage'))
const AwsOpsPage = lazy(() => import('./pages/AwsOpsPage'))
const EventsPage = lazy(() => import('./pages/EventsPage'))
const LogsPage = lazy(() => import('./pages/LogsPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const PipelinePage = lazy(() => import('./pages/PipelinePage'))
const ModeMonitorPage = lazy(() => import('./pages/ModeMonitorPage'))

// Agent Section
const SkillsPage = lazy(() => import('./pages/SkillsPage'))
const SkillsMarketplacePage = lazy(() => import('./pages/SkillsMarketplacePage'))
const MemoryPage = lazy(() => import('./pages/MemoryPage'))
const MemoryProposalsPage = lazy(() => import('./pages/MemoryProposalsPage'))
const MemoryTimelinePage = lazy(() => import('./pages/MemoryTimelinePage'))
const MemoryEntriesPage = lazy(() => import('./pages/MemoryEntriesPage'))
const SnippetsPage = lazy(() => import('./pages/SnippetsPage'))
const AnswersPage = lazy(() => import('./pages/AnswersPage'))
const AuthProfilesPage = lazy(() => import('./pages/AuthProfilesPage'))
const ToolsPage = lazy(() => import('./pages/ToolsPage'))
const TriggersPage = lazy(() => import('./pages/TriggersPage'))

// Knowledge Section
const BrainPage = lazy(() => import('./pages/BrainPage'))
const BrainDashboardPage = lazy(() => import('./pages/BrainDashboardPage'))
const QueryPlaygroundPage = lazy(() => import('./pages/QueryPlaygroundPage'))
const SourcesPage = lazy(() => import('./pages/SourcesPage'))
const HealthPage = lazy(() => import('./pages/HealthPage'))
const KnowledgeHealthPage = lazy(() => import('./pages/KnowledgeHealthPage'))
const IndexJobsPage = lazy(() => import('./pages/IndexJobsPage'))
const SubgraphPage = lazy(() => import('./pages/SubgraphPage'))
const DatasourcesPage = lazy(() => import('./pages/DatasourcesPage'))
const ProvenancePage = lazy(() => import('./pages/ProvenancePage'))

// Quality Section
const InfoNeedMetricsPage = lazy(() => import('./pages/InfoNeedMetricsPage'))

// Governance Section
const GovernancePage = lazy(() => import('./pages/GovernancePage'))
const FindingsPage = lazy(() => import('./pages/FindingsPage'))
const LeadScansPage = lazy(() => import('./pages/LeadScansPage'))
const DecisionReviewPage = lazy(() => import('./pages/DecisionReviewPage'))
const ReviewQueuePage = lazy(() => import('./pages/ReviewQueuePage'))
const ExecutionPlansPage = lazy(() => import('./pages/ExecutionPlansPage'))
const IntentWorkbenchPage = lazy(() => import('./pages/IntentWorkbenchPage'))
const ContentRegistryPage = lazy(() => import('./pages/ContentRegistryPage'))
const AnswerPacksPage = lazy(() => import('./pages/AnswerPacksPage'))
const PolicyEditorPage = lazy(() => import('./pages/PolicyEditorPage'))
const MarketplaceRegistryPage = lazy(() => import('./pages/MarketplaceRegistryPage'))
const EvolutionDecisionsPage = lazy(() => import('./pages/EvolutionDecisionsPage'))
const BudgetConfigPage = lazy(() => import('./pages/BudgetConfigPage'))

// Capabilities v3 Section
const CapabilitiesPage = lazy(() => import('./pages/CapabilitiesPage'))
const DecisionTimelinePage = lazy(() => import('./pages/DecisionTimelinePage'))
const ActionLogPage = lazy(() => import('./pages/ActionLogPage'))
const EvidenceChainsPage = lazy(() => import('./pages/EvidenceChainsPage'))
const AuditLogPage = lazy(() => import('./pages/AuditLogPage'))
const TrustTierPage = lazy(() => import('./pages/TrustTierPage'))
const TrustTrajectoryPage = lazy(() => import('./pages/TrustTrajectoryPage'))
const RiskTimelinePage = lazy(() => import('./pages/RiskTimelinePage'))
const FederatedNodesView = lazy(() => import('./pages/FederatedNodesView'))
const PublisherTrustView = lazy(() => import('./pages/PublisherTrustView'))
const RemoteControlPage = lazy(() => import('./pages/RemoteControlPage'))

// Settings Section
const ExtensionsPage = lazy(() => import('./pages/ExtensionsPage'))
const McpMarketplacePage = lazy(() => import('./pages/McpMarketplacePage'))
const EmailChannelPage = lazy(() => import('./pages/EmailChannelPage'))
const ModelsPage = lazy(() => import('./pages/ModelsPage'))
const ProvidersPage = lazy(() => import('./pages/ProvidersPage'))
const ConfigPage = lazy(() => import('./pages/ConfigPage'))
const ConfigEntriesPage = lazy(() => import('./pages/ConfigEntriesPage'))
const PluginsPage = lazy(() => import('./pages/PluginsPage'))

// Communication Section
const ChannelsPage = lazy(() => import('./pages/ChannelsPage'))
const CommunicationPage = lazy(() => import('./pages/CommunicationPage'))
const MessagesPage = lazy(() => import('./pages/MessagesPage'))
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'))
const NetworkAccessPage = lazy(() => import('./pages/NetworkAccessPage'))
const SecurityDevicesPage = lazy(() => import('./pages/SecurityDevicesPage'))
const ChannelsTeamsPage = lazy(() => import('./pages/ChannelsTeamsPage'))

// SSH / SFTP / Keychain
const SshHostsPage = lazy(() => import('./pages/SshHostsPage'))
const SshConnectionsPage = lazy(() => import('./pages/SshConnectionsPage'))
const SshKeychainPage = lazy(() => import('./pages/SshKeychainPage'))
const SshKnownHostsPage = lazy(() => import('./pages/SshKnownHostsPage'))
const SshLogsPage = lazy(() => import('./pages/SshLogsPage'))
const SshSftpPage = lazy(() => import('./pages/SshSftpPage'))
const SshProviderPage = lazy(() => import('./pages/SshProviderPage'))

// System Section
const ContextPage = lazy(() => import('./pages/ContextPage'))
const RuntimePage = lazy(() => import('./pages/RuntimePage'))
const SupportPage = lazy(() => import('./pages/SupportPage'))
const SystemHealthPage = lazy(() => import('./pages/SystemHealthPage'))
const DemoModePage = lazy(() => import('./pages/DemoModePage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))
const ContractDocsPage = lazy(() => import('./pages/ContractDocsPage'))

// 404 Not Found
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

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
          <GlobalButtonTooltipProvider>
            <Suspense fallback={<LoadingState />}>
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
          <Route path="/chat/work" element={<WorkPage />} />
          <Route path="/work-list" element={<WorkListPage />} />
          <Route path="/task-list" element={<TaskListPage />} />
          <Route path="/changelog" element={<ChangeLogPage />} />
          <Route path="/wiki" element={<WikiPage />} />
          <Route path="/coding" element={<CodingPage />} />
          <Route path="/chat-report" element={<ChatReportPage />} />
          <Route path="/dispatch-review" element={<DispatchReviewQueuePage />} />
          <Route path="/voice" element={<VoicePage />} />
          <Route path="/external-facts/replay" element={<ExternalFactsReplayPage />} />
          <Route path="/external-facts/policy" element={<ExternalFactsPolicyPage />} />
          <Route path="/external-facts/providers" element={<ExternalFactsProvidersPage />} />
          <Route path="/connectors" element={<ConnectorsPage />} />
          <Route path="/facts/schema" element={<FactsSchemaPage />} />

          {/* Control Section */}
          <Route path="/overview" element={<OverviewPage />} />

          {/* Sessions Section */}
          <Route path="/sessions" element={<SessionsPage />} />

          {/* Observability Section */}
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="/aws" element={<AwsOpsPage />} />
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

          {/* SSH Section */}
          <Route path="/ssh/hosts" element={<SshHostsPage />} />
          <Route path="/ssh/connections" element={<SshConnectionsPage />} />
          <Route path="/ssh/keychain" element={<SshKeychainPage />} />
          <Route path="/ssh/known-hosts" element={<SshKnownHostsPage />} />
          <Route path="/ssh/logs" element={<SshLogsPage />} />
          <Route path="/ssh/sftp" element={<SshSftpPage />} />
          <Route path="/ssh/provider" element={<SshProviderPage />} />

          {/* Communication Section */}
          <Route path="/channels" element={<ChannelsPage />} />
          <Route path="/channels/enterprise-im" element={<Navigate to="/channels#enterprise-im" replace />} />
          <Route path="/channels/email" element={<EmailChannelPage />} />
          <Route path="/channels/teams" element={<ChannelsTeamsPage />} />
          <Route path="/network/access" element={<NetworkAccessPage />} />
          <Route path="/security/devices" element={<SecurityDevicesPage />} />
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
          <Route path="/docs/contracts" element={<ContractDocsPage />} />

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
            </Suspense>
          </GlobalButtonTooltipProvider>
        </SnackbarProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}

export default App
