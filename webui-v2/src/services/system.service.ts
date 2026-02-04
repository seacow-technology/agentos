/**
 * System Service
 *
 * API functions for system-level operations:
 * - Configuration management
 * - Provider management (Ollama, LM Studio, etc.)
 * - Model management (download, list, etc.)
 * - Health checks
 * - Runtime information
 * - Secrets management
 * - Support utilities
 * - Auth & CSRF
 * - History & Logging
 * - Share & Preview
 * - Snippets
 * - Budget configuration
 * - Mode monitoring
 * - Demo mode
 * - Metrics
 */

import { get, post, put, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

// Configuration
export interface Config {
  [key: string]: unknown;
}

export interface GetConfigResponse {
  config: Config;
}

export interface UpdateConfigRequest {
  config: Partial<Config>;
}

export interface UpdateConfigResponse {
  config: Config;
}

// Provider Management
export interface Provider {
  id: string;
  name: string;
  type: 'ollama' | 'lmstudio' | 'openai' | 'anthropic';
  status: 'running' | 'stopped' | 'error';
  url?: string;
}

export interface ListProvidersResponse {
  providers: Provider[];
}

export interface GetProviderResponse {
  provider: Provider;
}

export interface ProviderInstance {
  id: string;
  provider_id: string;
  name: string;
  config: Record<string, unknown>;
  status: string;
}

export interface ListProviderInstancesResponse {
  instances: ProviderInstance[];
  total: number;
}

export interface GetProviderInstanceResponse {
  instance: ProviderInstance;
}

export interface CreateProviderInstanceRequest {
  name: string;
  config: Record<string, unknown>;
}

export interface CreateProviderInstanceResponse {
  instance: ProviderInstance;
}

export interface UpdateProviderInstanceRequest {
  name?: string;
  config?: Record<string, unknown>;
}

export interface UpdateProviderInstanceResponse {
  instance: ProviderInstance;
}

export interface StartProviderResponse {
  provider: Provider;
}

export interface StopProviderResponse {
  provider: Provider;
}

export interface RestartProviderResponse {
  provider: Provider;
}

// Model Management
export interface Model {
  id: string;
  name: string;
  size?: number;
  status: 'available' | 'downloading' | 'installed';
  provider_id?: string;
}

export interface ListModelsRequest {
  provider_id?: string;
  status?: string;
}

export interface ListModelsResponse {
  models: Model[];
  total: number;
}

export interface GetModelResponse {
  model: Model;
}

export interface PullModelRequest {
  model_name: string;
  provider_id?: string;
}

export interface PullModelResponse {
  model: Model;
  task_id?: string;
}

export interface GetModelPullProgressResponse {
  progress: number;
  status: string;
  message?: string;
}

// Health & Status
export interface HealthCheckResponse {
  status: 'ok' | 'degraded' | 'error' | 'warn';
  components: Record<string, { status: string; message?: string }>;
  timestamp: string;
  uptime_seconds?: number;
  metrics?: Record<string, any>;
}

export interface GetRuntimeInfoResponse {
  version: string;
  uptime: number;
  environment: string;
  features: string[];
  pid: number;
}

// Overview Dashboard
export interface OverviewMetrics {
  // Top stat cards
  total_tasks: number;
  active_agents: number;
  success_rate: string;

  // System status metrics
  uptime_seconds: number;
  cpu: string;
  memory: string;

  // Recent activity metrics
  tasks: number;
  agents: number;
  skills: number;

  // Resource usage metrics
  disk_usage: string;
  network_usage: string;
  database_size: string;
}

export interface OverviewResponse {
  status: string;
  timestamp: string;
  uptime_seconds: number;
  metrics: OverviewMetrics;
}

// Secrets Management
export interface SecretStatus {
  provider: string;
  configured: boolean;
  valid: boolean;
}

export interface AllSecretsStatusResponse {
  secrets: SecretStatus[];
}

export interface SecretStatusResponse {
  status: SecretStatus;
}

export interface SaveSecretRequest {
  provider: string;
  secret_value: string;
}

export interface SaveSecretResponse {
  success: boolean;
  provider: string;
}

export interface DeleteSecretResponse {
  success: boolean;
  provider: string;
}

// Support
export interface SupportRequest {
  subject: string;
  message: string;
  category?: string;
}

export interface SupportResponse {
  ticket_id: string;
  status: string;
}

// Auth
export interface AuthProfile {
  id: string;
  name: string;
  provider: string;
  status: string;
}

export interface ListAuthProfilesResponse {
  profiles: AuthProfile[];
}

export interface GetAuthProfileResponse {
  profile: AuthProfile;
}

export interface ValidateAuthProfileResponse {
  valid: boolean;
  message?: string;
}

export interface GetCSRFTokenResponse {
  token: string;
}

// History & Logging
export interface HistoryItem {
  id: string;
  title: string;
  timestamp: string;
  pinned: boolean;
}

export interface ListHistoryRequest {
  page?: number;
  limit?: number;
}

export interface ListHistoryResponse {
  items: HistoryItem[];
  total: number;
}

export interface GetHistoryItemResponse {
  item: HistoryItem;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  context?: Record<string, unknown>;
}

export interface ListLogsRequest {
  level?: string;
  limit?: number;
}

export interface ListLogsResponse {
  logs: LogEntry[];
  total: number;
}

// Share & Preview
export interface ShareData {
  id: string;
  content: Record<string, unknown>;
  expires_at?: string;
  created_at: string;
}

export interface CreateShareRequest {
  content: Record<string, unknown>;
  expires_in?: number;
}

export interface CreateShareResponse {
  share: ShareData;
  share_url: string;
}

export interface GetShareResponse {
  share: ShareData;
}

export interface GetShareStatsResponse {
  total_shares: number;
  active_shares: number;
}

export interface PreviewSession {
  id: string;
  content: string;
  created_at: string;
}

export interface CreatePreviewRequest {
  content: string;
  metadata?: Record<string, unknown>;
}

export interface CreatePreviewResponse {
  session: PreviewSession;
  preview_url: string;
}

export interface GetPreviewMetaResponse {
  session: PreviewSession;
  metadata: Record<string, unknown>;
}

// Snippets
export interface Snippet {
  id: string;
  title: string;
  content: string;
  language?: string;
  tags?: string[];
  created_at: string;
}

export interface ListSnippetsRequest {
  tags?: string[];
  language?: string;
  page?: number;
  limit?: number;
}

export interface ListSnippetsResponse {
  snippets: Snippet[];
  total: number;
}

export interface GetSnippetResponse {
  snippet: Snippet;
}

export interface CreateSnippetRequest {
  title: string;
  content: string;
  language?: string;
  tags?: string[];
}

export interface CreateSnippetResponse {
  snippet: Snippet;
}

export interface UpdateSnippetRequest {
  title?: string;
  content?: string;
  language?: string;
  tags?: string[];
}

export interface UpdateSnippetResponse {
  snippet: Snippet;
}

// Budget Configuration - V1 Compatible Types
export interface BudgetAllocation {
  window_tokens: number;
  rag_tokens: number;
  memory_tokens: number;
  summary_tokens: number;
  system_tokens: number;
}

export interface BudgetConfigV1 {
  max_tokens: number;
  auto_derive: boolean;
  allocation: BudgetAllocation;
  safety_margin: number;
  generation_max_tokens: number;
  safe_threshold: number;
  critical_threshold: number;
}

// V2 UI Types (for component compatibility)
export interface BudgetConfig {
  id: string;
  name: string;
  max_tokens: number;
  auto_derive: boolean;
  allocation: BudgetAllocation;
  safety_margin: number;
  generation_max_tokens: number;
  safe_threshold: number;
  critical_threshold: number;
}

export interface ListBudgetConfigsResponse {
  configs: BudgetConfig[];
}

export interface GetBudgetConfigResponse {
  config: BudgetConfig;
}

export interface CreateBudgetConfigRequest {
  name: string;
  max_tokens: number;
  auto_derive?: boolean;
  window_tokens?: number;
  rag_tokens?: number;
  memory_tokens?: number;
  summary_tokens?: number;
  system_tokens?: number;
  safety_margin?: number;
  generation_max_tokens?: number;
}

export interface CreateBudgetConfigResponse {
  config: BudgetConfig;
}

export interface UpdateBudgetConfigRequest {
  max_tokens?: number;
  auto_derive?: boolean;
  window_tokens?: number;
  rag_tokens?: number;
  memory_tokens?: number;
  summary_tokens?: number;
  system_tokens?: number;
  safety_margin?: number;
  generation_max_tokens?: number;
}

export interface UpdateBudgetConfigResponse {
  config: BudgetConfig;
}

// Mode Monitoring
export interface ModeAlert {
  id: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  created_at: string;
}

export interface GetModeAlertsResponse {
  alerts: ModeAlert[];
  total: number;
}

export interface ModeStats {
  current_mode: string;
  uptime: number;
  alerts_count: number;
}

export interface GetModeStatsResponse {
  stats: ModeStats;
}

export interface ClearModeAlertsResponse {
  cleared_count: number;
}

// Demo Mode
export interface DemoModeStatus {
  enabled: boolean;
  scenarios: string[];
}

export interface GetDemoModeStatusResponse {
  demo_mode: DemoModeStatus;
}

export interface EnableDemoModeRequest {
  scenarios?: string[];
}

export interface EnableDemoModeResponse {
  demo_mode: DemoModeStatus;
}

export interface DisableDemoModeResponse {
  demo_mode: DemoModeStatus;
}

export interface GetDemoHealthResponse {
  status: string;
  scenarios_status: Record<string, string>;
}

// Metrics
export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_rx: number;
  network_tx: number;
}

export interface GetMetricsResponse {
  metrics: SystemMetrics;
  timestamp: string;
}

export interface GetMetricsJsonResponse {
  metrics: Record<string, unknown>;
  timestamp: string;
}

// Config Entries Management
export interface ConfigEntry {
  id: number;
  key: string;
  value: string;
  type: 'String' | 'Integer' | 'Boolean' | 'JSON';
  scope: string;
  description: string;
  lastModified: string;
}

export interface ListConfigEntriesRequest {
  search?: string;
  scope?: string;
  type?: string;
  page?: number;
  limit?: number;
}

export interface ListConfigEntriesResponse {
  entries: ConfigEntry[];
  total: number;
}

export interface GetConfigEntryResponse {
  entry: ConfigEntry;
}

export interface CreateConfigEntryRequest {
  key: string;
  value: string;
  type: 'String' | 'Integer' | 'Boolean' | 'JSON';
  scope?: string;
  description?: string;
}

export interface CreateConfigEntryResponse {
  entry: ConfigEntry;
}

export interface UpdateConfigEntryRequest {
  value?: string;
  type?: 'String' | 'Integer' | 'Boolean' | 'JSON';
  scope?: string;
  description?: string;
}

export interface UpdateConfigEntryResponse {
  entry: ConfigEntry;
}

export interface ConfigEntryVersion {
  id: number;
  entry_id: number;
  version: number;
  value: string;
  type: 'String' | 'Integer' | 'Boolean' | 'JSON';
  changed_by: string;
  changed_at: string;
  change_reason?: string;
}

export interface ListConfigVersionsResponse {
  versions: ConfigEntryVersion[];
  total: number;
}

export interface ConfigVersionDiff {
  entry_id: number;
  entry_key: string;
  from_version: number;
  to_version: number;
  from_value: string;
  to_value: string;
  from_type: string;
  to_type: string;
  changed_at: string;
  changed_by: string;
  diff_lines: Array<{
    type: 'added' | 'removed' | 'unchanged';
    content: string;
  }>;
}

export interface GetConfigDiffResponse {
  diff: ConfigVersionDiff;
}

// ============================================================================
// Service Functions
// ============================================================================

export const systemService = {
  // Configuration
  async getConfig(): Promise<GetConfigResponse> {
    return get('/api/config');
  },

  async updateConfig(data: UpdateConfigRequest): Promise<UpdateConfigResponse> {
    return put('/api/config', data);
  },

  // Provider Management
  async listProviders(): Promise<ListProvidersResponse> {
    return get('/api/providers');
  },

  async getProvider(id: string): Promise<GetProviderResponse> {
    return get(`/api/providers/${id}`);
  },

  async startProvider(id: string): Promise<StartProviderResponse> {
    return post(`/api/providers/${id}/start`);
  },

  async stopProvider(id: string): Promise<StopProviderResponse> {
    return post(`/api/providers/${id}/stop`);
  },

  async restartProvider(id: string): Promise<RestartProviderResponse> {
    return post(`/api/providers/${id}/restart`);
  },

  async getProviderStatus(id: string): Promise<{ status: Record<string, unknown> }> {
    return get(`/api/providers/${id}/status`);
  },

  // Provider Instances
  async listProviderInstances(providerId?: string): Promise<ListProviderInstancesResponse> {
    return get('/api/providers/instances', { params: { provider_id: providerId } });
  },

  async getProviderInstance(providerId: string, instanceId: string): Promise<GetProviderInstanceResponse> {
    return get(`/api/providers/instances/${providerId}/${instanceId}`);
  },

  async createProviderInstance(providerId: string, data: CreateProviderInstanceRequest): Promise<CreateProviderInstanceResponse> {
    return post(`/api/providers/instances/${providerId}`, data);
  },

  async updateProviderInstance(providerId: string, instanceId: string, data: UpdateProviderInstanceRequest): Promise<UpdateProviderInstanceResponse> {
    return put(`/api/providers/instances/${providerId}/${instanceId}`, data);
  },

  async deleteProviderInstance(providerId: string, instanceId: string): Promise<void> {
    return del(`/api/providers/instances/${providerId}/${instanceId}`);
  },

  // Model Management
  async listModels(params?: ListModelsRequest): Promise<ListModelsResponse> {
    return get('/api/models/list', { params });
  },

  async getModel(id: string): Promise<GetModelResponse> {
    return get(`/api/models/${id}`);
  },

  async pullModel(data: PullModelRequest): Promise<PullModelResponse> {
    return post('/api/models/pull', data);
  },

  async getModelPullProgress(taskId: string): Promise<GetModelPullProgressResponse> {
    return get(`/api/models/pull/${taskId}/progress`);
  },

  async deleteModel(id: string): Promise<void> {
    return del(`/api/models/${id}`);
  },

  // Health & Status
  async healthCheck(): Promise<HealthCheckResponse> {
    return get('/api/health');
  },

  async getRuntimeInfo(): Promise<GetRuntimeInfoResponse> {
    return get('/api/runtime/info');
  },

  async getOverview(): Promise<OverviewResponse> {
    return get('/api/overview');
  },

  async selfCheck(): Promise<{ status: string; checks: Record<string, unknown> }> {
    return get('/api/selfcheck');
  },

  // Secrets Management
  async getAllSecretsStatus(): Promise<AllSecretsStatusResponse> {
    return get('/api/secrets/status');
  },

  async getSecretStatus(provider: string): Promise<SecretStatusResponse> {
    return get(`/api/secrets/status/${provider}`);
  },

  async saveSecret(data: SaveSecretRequest): Promise<SaveSecretResponse> {
    return post('/api/secrets', data);
  },

  async deleteSecret(provider: string): Promise<DeleteSecretResponse> {
    return del(`/api/secrets/${provider}`);
  },

  // Support
  async submitSupportRequest(data: SupportRequest): Promise<SupportResponse> {
    return post('/api/support', data);
  },

  // Auth
  async listAuthProfiles(): Promise<ListAuthProfilesResponse> {
    return get('/api/auth/profiles');
  },

  async getAuthProfile(id: string): Promise<GetAuthProfileResponse> {
    return get(`/api/auth/profiles/${id}`);
  },

  async validateAuthProfile(id: string): Promise<ValidateAuthProfileResponse> {
    return post(`/api/auth/profiles/${id}/validate`);
  },

  async getCSRFToken(): Promise<GetCSRFTokenResponse> {
    return get('/api/csrf-token');
  },

  // History
  async listHistory(params?: ListHistoryRequest): Promise<ListHistoryResponse> {
    return get('/api/history', { params });
  },

  async getPinnedHistory(): Promise<ListHistoryResponse> {
    return get('/api/history/pinned');
  },

  async getHistoryItem(id: string): Promise<GetHistoryItemResponse> {
    return get(`/api/history/${id}`);
  },

  async pinHistoryItem(id: string): Promise<{ item: HistoryItem }> {
    return post(`/api/history/${id}/pin`);
  },

  async unpinHistoryItem(id: string): Promise<void> {
    return del(`/api/history/${id}/pin`);
  },

  // Logging
  async listLogs(params?: ListLogsRequest): Promise<ListLogsResponse> {
    return get('/api/logs', { params });
  },

  // Share
  async createShare(data: CreateShareRequest): Promise<CreateShareResponse> {
    return post('/api/share', data);
  },

  async getShare(id: string): Promise<GetShareResponse> {
    return get(`/api/share/${id}`);
  },

  async deleteShare(id: string): Promise<void> {
    return del(`/api/share/${id}`);
  },

  async getShareStats(): Promise<GetShareStatsResponse> {
    return get('/api/shares/stats');
  },

  // Preview
  async createPreview(data: CreatePreviewRequest): Promise<CreatePreviewResponse> {
    return post('/api/preview', data);
  },

  async getPreview(sessionId: string): Promise<string> {
    return get(`/api/preview/${sessionId}`);
  },

  async getPreviewMeta(sessionId: string): Promise<GetPreviewMetaResponse> {
    return get(`/api/preview/${sessionId}/meta`);
  },

  async deletePreview(sessionId: string): Promise<void> {
    return del(`/api/preview/${sessionId}`);
  },

  // Snippets
  async listSnippets(params?: ListSnippetsRequest): Promise<ListSnippetsResponse> {
    return get('/api/snippets', { params });
  },

  async getSnippet(id: string): Promise<GetSnippetResponse> {
    return get(`/api/snippets/${id}`);
  },

  async createSnippet(data: CreateSnippetRequest): Promise<CreateSnippetResponse> {
    return post('/api/snippets', data);
  },

  async updateSnippet(id: string, data: UpdateSnippetRequest): Promise<UpdateSnippetResponse> {
    return put(`/api/snippets/${id}`, data);
  },

  async deleteSnippet(id: string): Promise<void> {
    return del(`/api/snippets/${id}`);
  },

  // Budget Configuration - V1 Compatibility Layer
  async listBudgetConfigs(): Promise<ListBudgetConfigsResponse> {
    // V1 uses /api/budget/global (singleton), wrap as array for V2 UI
    const response = await get<BudgetConfigV1>('/api/budget/global');
    const config: BudgetConfig = {
      id: 'global',
      name: 'Global Budget Configuration',
      max_tokens: response.max_tokens,
      auto_derive: response.auto_derive,
      allocation: response.allocation,
      safety_margin: response.safety_margin,
      generation_max_tokens: response.generation_max_tokens,
      safe_threshold: response.safe_threshold,
      critical_threshold: response.critical_threshold,
    };
    return { configs: [config] };
  },

  async getBudgetConfig(_id: string): Promise<GetBudgetConfigResponse> {
    // V1 only has global config, ignore id parameter
    const response = await get<BudgetConfigV1>('/api/budget/global');
    const config: BudgetConfig = {
      id: 'global',
      name: 'Global Budget Configuration',
      max_tokens: response.max_tokens,
      auto_derive: response.auto_derive,
      allocation: response.allocation,
      safety_margin: response.safety_margin,
      generation_max_tokens: response.generation_max_tokens,
      safe_threshold: response.safe_threshold,
      critical_threshold: response.critical_threshold,
    };
    return { config };
  },

  async updateBudgetConfig(_id: string, data: UpdateBudgetConfigRequest): Promise<UpdateBudgetConfigResponse> {
    // V1 uses /api/budget/global (no ID), update global config
    const response = await put<BudgetConfigV1>('/api/budget/global', data);
    const config: BudgetConfig = {
      id: 'global',
      name: 'Global Budget Configuration',
      max_tokens: response.max_tokens,
      auto_derive: response.auto_derive,
      allocation: response.allocation,
      safety_margin: response.safety_margin,
      generation_max_tokens: response.generation_max_tokens,
      safe_threshold: response.safe_threshold,
      critical_threshold: response.critical_threshold,
    };
    return { config };
  },

  async deleteBudgetConfig(_id: string): Promise<void> {
    // V1 does not support deleting global config
    throw new Error('Cannot delete global budget configuration');
  },

  // Mode Monitoring
  async getModeAlerts(): Promise<GetModeAlertsResponse> {
    return get('/api/mode/alerts');
  },

  async getModeStats(): Promise<GetModeStatsResponse> {
    return get('/api/mode/stats');
  },

  async clearModeAlerts(): Promise<ClearModeAlertsResponse> {
    return post('/api/mode/alerts/clear');
  },

  // Demo Mode
  async getDemoModeStatus(): Promise<GetDemoModeStatusResponse> {
    return get('/api/demo-mode/status');
  },

  async enableDemoMode(data?: EnableDemoModeRequest): Promise<EnableDemoModeResponse> {
    return post('/api/demo-mode/enable', data);
  },

  async disableDemoMode(): Promise<DisableDemoModeResponse> {
    return post('/api/demo-mode/disable');
  },

  async getDemoHealth(): Promise<GetDemoHealthResponse> {
    return get('/api/demo-health');
  },

  // Metrics
  async getMetrics(): Promise<GetMetricsResponse> {
    return get('/api/metrics');
  },

  async getMetricsJson(): Promise<GetMetricsJsonResponse> {
    return get('/api/metrics/json');
  },

  // Runtime Operations
  async fixPermissions(): Promise<{ ok: boolean; message: string; fixed_files: string[] }> {
    return post('/api/runtime/fix-permissions');
  },

  async runSelfCheck(params?: { session_id?: string; include_network?: boolean; include_context?: boolean }): Promise<{
    summary: string;
    ts: string;
    items: Array<{
      id: string;
      group: string;
      name: string;
      status: string;
      detail: string;
      hint?: string;
      actions: Array<{
        label: string;
        method?: string;
        path?: string;
        ui?: string;
      }>;
    }>;
    version: string;
  }> {
    return post('/api/selfcheck', params || {});
  },

  // Context Management
  async getContext(): Promise<{ context: Record<string, unknown> }> {
    return get('/api/context');
  },

  async updateContext(data: Record<string, unknown>): Promise<{ context: Record<string, unknown> }> {
    return put('/api/context', data);
  },

  // Events
  async listEvents(params?: { type?: string; limit?: number }): Promise<{ events: Array<Record<string, unknown>>; total: number }> {
    return get('/api/events', { params });
  },

  // Content Management
  async listContent(params?: { type?: string; status?: string; search?: string; limit?: number; offset?: number }): Promise<{ content: Array<Record<string, unknown>>; total: number }> {
    return get('/api/content', { params });
  },

  async getContent(id: string): Promise<{ content: Record<string, unknown> }> {
    return get(`/api/content/${id}`);
  },

  async createContent(data: { type: string; name: string; version: string; source_uri?: string; metadata?: Record<string, unknown>; release_notes?: string }): Promise<{ ok: boolean; data?: Record<string, unknown>; error?: string }> {
    return post('/api/content', data);
  },

  async updateContent(id: string, data: { action?: string; confirm?: boolean; [key: string]: unknown }): Promise<{ ok: boolean; data?: Record<string, unknown>; error?: string }> {
    const action = data.action;
    if (action === 'activate') {
      return post(`/api/content/${id}/activate?confirm=${data.confirm}`, {});
    } else if (action === 'deprecate') {
      return post(`/api/content/${id}/deprecate?confirm=${data.confirm}`, {});
    } else if (action === 'freeze') {
      return post(`/api/content/${id}/freeze?confirm=${data.confirm}`, {});
    }
    return put(`/api/content/${id}`, data);
  },

  // Answers
  async getAnswers(params?: { query?: string; limit?: number }): Promise<{ answers: Array<Record<string, unknown>> }> {
    return get('/api/answers', { params });
  },

  // Answer Packs
  async listAnswerPacks(params?: { search?: string; status?: string; limit?: number; offset?: number }): Promise<{ ok: boolean; data: Array<Record<string, unknown>>; total: number; error?: string }> {
    return get('/api/answers/packs', { params });
  },

  async getAnswerPack(id: string): Promise<{ ok: boolean; data?: { id: string; name: string; status: string; items: Array<{ question: string; answer: string; type?: string }>; metadata?: Record<string, unknown>; created_at: string; updated_at: string }; error?: string }> {
    return get(`/api/answers/packs/${id}`);
  },

  async createAnswerPack(data: { name: string; description?: string; answers: Array<{ question: string; answer: string; type?: string }> }): Promise<{ ok: boolean; data?: Record<string, unknown>; error?: string; message?: string }> {
    return post('/api/answers/packs', data);
  },

  async validateAnswerPack(id: string): Promise<{ ok: boolean; data?: { valid: boolean; errors?: string[]; warnings?: string[] }; error?: string }> {
    return post(`/api/answers/packs/${id}/validate`, {});
  },

  async getAnswerPackRelated(id: string): Promise<{ ok: boolean; data?: Array<Record<string, unknown>>; error?: string }> {
    return get(`/api/answers/packs/${id}/related`);
  },

  // Contracts
  async listContracts(): Promise<{ contracts: Array<Record<string, unknown>> }> {
    return get('/api/contracts');
  },

  // Dryrun
  async executeDryrun(data: { operation: string; params: Record<string, unknown> }): Promise<{ result: Record<string, unknown> }> {
    return post('/api/dryrun', data);
  },

  // Chat Commands
  async listChatCommands(): Promise<{ commands: Array<{ name: string; description: string }> }> {
    return get('/api/commands');
  },

  // Config Entries Management
  async listConfigEntries(params?: ListConfigEntriesRequest): Promise<ListConfigEntriesResponse> {
    return get('/api/config/entries', { params });
  },

  async getConfigEntry(id: number): Promise<GetConfigEntryResponse> {
    return get(`/api/config/entries/${id}`);
  },

  async createConfigEntry(data: CreateConfigEntryRequest): Promise<CreateConfigEntryResponse> {
    return post('/api/config/entries', data);
  },

  async updateConfigEntry(id: number, data: UpdateConfigEntryRequest): Promise<UpdateConfigEntryResponse> {
    return put(`/api/config/entries/${id}`, data);
  },

  async deleteConfigEntry(id: number): Promise<void> {
    return del(`/api/config/entries/${id}`);
  },

  async listConfigVersions(id: number): Promise<ListConfigVersionsResponse> {
    return get(`/api/config/entries/${id}/versions`);
  },

  async getConfigDiff(id: number, fromVersion: number, toVersion: number): Promise<GetConfigDiffResponse> {
    return get(`/api/config/entries/${id}/diff`, {
      params: { from: fromVersion, to: toVersion },
    });
  },
};
