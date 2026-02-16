/**
 * Providers API Client
 *
 * Handles all provider-related API calls following backend API contracts
 */

import { httpClient } from '@platform/http'

// ============================================
// DTOs (matching backend)
// ============================================

export interface ProviderInfo {
  id: string
  label: string
  type: string
  supports_models: boolean
  supports_start: boolean
  supports_auth: string[]
}

export interface ProviderStatusResponse {
  id: string
  type: string
  state: string
  endpoint: string | null
  latency_ms: number | null
  last_ok_at: string | null
  last_error: string | null
  pid: number | null
  pid_exists: boolean | null
  port_listening: boolean | null
  api_responding: boolean | null
}

export interface ProvidersListResponse {
  local: ProviderInfo[]
  cloud: ProviderInfo[]
}

export interface ProvidersStatusResponse {
  ts: string
  providers: ProviderStatusResponse[]
  cache_ttl_ms: number
}

export interface ModelInfoResponse {
  id: string
  label?: string
  name?: string
  context_window?: number | null
  metadata?: Record<string, unknown>
  used?: boolean
}

export interface ModelsListResponse {
  provider_id?: string
  models: ModelInfoResponse[]
  total?: number
  source?: 'live' | 'catalog'
}

export interface ModelPricingRow {
  provider: string
  model: string
  input_per_1m: number
  output_per_1m: number
  currency: string
  source?: string | null
  enabled: boolean
  created_at_ms: number
  updated_at_ms: number
}

export interface ProviderModelsPricingResponse {
  provider_id: string
  ts_ms: number
  pricing: ModelPricingRow[]
}

export interface ModelPricingUpsertRequest {
  input_per_1m: number
  output_per_1m: number
  currency?: string
  source?: string | null
  enabled?: boolean
}

export interface UsedModelsGetResponse {
  provider_id: string
  used_models: string[]
}

export interface SetModelUsedResponse {
  ok: boolean
  provider_id: string
  model_id: string
  used: boolean
  used_models: string[]
}

export interface InstanceConfigRequest {
  instance_id?: string
  base_url: string
  enabled: boolean
  launch?: {
    enabled: boolean
    executable_path: string | null
    args: string[]
    env: Record<string, string>
  }
  metadata?: Record<string, any>
}

export interface InstanceConfigResponse {
  ok: boolean
  instance_key: string
  config: any
}

export interface InstanceInfoResponse {
  id: string
  base_url: string
  enabled: boolean
  launch?: {
    bin?: string
    args?: Record<string, any>
  } | null
  metadata?: Record<string, any>
}

export interface CloudMaskedConfig {
  provider_id: string
  config_id?: string
  label?: string | null
  auth: {
    type: string
    api_key: string
  }
  base_url: string | null
  last_verified_at: string | null
  last_test?: {
    ok: boolean
    at: string
    latency_ms?: number | null
    error?: string | null
  } | null
  last_usage?: {
    status: string
    at?: string | null
    error?: string | null
  } | null
}

export interface CloudConfigGetResponse {
  provider_id: string
  configured: boolean
  config: CloudMaskedConfig | null
}

export interface CloudConfigSetRequest {
  api_key: string
  base_url?: string | null
}

export interface CloudConfigSetResponse {
  ok: boolean
  provider_id: string
  config: CloudMaskedConfig | null
}

export interface CloudConfigDeleteResponse {
  ok: boolean
  provider_id: string
  deleted: boolean
}

export interface CloudConfigRecordMasked extends CloudMaskedConfig {
  config_id: string
  label: string
  active: boolean
}

export interface CloudConfigsListResponse {
  provider_id: string
  active_config_id: string | null
  configs: CloudConfigRecordMasked[]
}

export interface CloudConfigRecordCreateRequest {
  config_id?: string | null
  label?: string | null
  api_key: string
  base_url?: string | null
  make_active?: boolean
}

export interface CloudConfigRecordUpsertRequest {
  label?: string | null
  api_key: string
  base_url?: string | null
  make_active?: boolean
}

export interface CloudConfigRecordDeleteResponse {
  ok: boolean
  provider_id: string
  config_id: string
  deleted: boolean
}

export interface CloudConfigActivateResponse {
  ok: boolean
  provider_id: string
  active_config_id: string
}

export interface CloudConfigTestResponse {
  ok: boolean
  provider_id: string
  config_id: string
  test: {
    ok: boolean
    at: string
    latency_ms?: number | null
    error?: string | null
  }
}

export interface ControlResponse {
  ok: boolean
  provider?: string
  action?: string
  state?: string
  pid?: number
  message: string
}

export interface InstanceControlResponse {
  ok: boolean
  instance_key: string
  status: string
  running: boolean
  old_pid?: number | null
  message?: string
}

export interface InstanceLogsResponse {
  ok: boolean
  instance_key: string
  stream: 'stdout' | 'stderr'
  lines: string[]
}

export interface InstallHintResponse {
  provider_id: string
  platform: string
  suggestion: string
}

// ============================================
// API Client
// ============================================

class ProvidersApiClient {
  private baseUrl = '/api/providers'

  /**
   * P0-17: List all providers (local & cloud)
   * GET /api/providers
   */
  async listProviders(): Promise<ProvidersListResponse> {
    const response = await httpClient.get<ProvidersListResponse>(this.baseUrl)
    return response.data
  }

  /**
   * P0-21: Get provider status for all providers
   * GET /api/providers/status
   */
  async getProvidersStatus(): Promise<ProvidersStatusResponse> {
    const response = await httpClient.get<ProvidersStatusResponse>(`${this.baseUrl}/status`)
    return response.data
  }

  /**
   * P0-21: Refresh provider status (trigger async refresh)
   * POST /api/providers/refresh
   */
  async refreshStatus(providerId?: string): Promise<void> {
    await httpClient.post(`${this.baseUrl}/refresh`, null, {
      params: providerId ? { provider_id: providerId } : undefined
    })
  }

  /**
   * Get models for a provider
   * GET /api/providers/{provider_id}/models
   */
  async getProviderModels(providerId: string): Promise<ModelsListResponse> {
    const response = await httpClient.get<ModelsListResponse>(`${this.baseUrl}/${encodeURIComponent(providerId)}/models`)
    return response.data
  }

  /**
   * Get model pricing for a provider.
   * GET /api/providers/{provider_id}/models/pricing
   */
  async getProviderModelPricing(providerId: string): Promise<ProviderModelsPricingResponse> {
    const response = await httpClient.get<ProviderModelsPricingResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/models/pricing`
    )
    return response.data
  }

  /**
   * Upsert model pricing for provider+model.
   * PUT /api/providers/{provider_id}/models/{model_id}/pricing
   */
  async upsertProviderModelPricing(
    providerId: string,
    modelId: string,
    payload: ModelPricingUpsertRequest
  ): Promise<{ ok: boolean; provider_id: string; model_id: string; pricing: ModelPricingRow }> {
    const response = await httpClient.put<{ ok: boolean; provider_id: string; model_id: string; pricing: ModelPricingRow }>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/pricing`,
      payload
    )
    return response.data
  }

  /**
   * Delete model pricing.
   * DELETE /api/providers/{provider_id}/models/{model_id}/pricing
   */
  async deleteProviderModelPricing(
    providerId: string,
    modelId: string
  ): Promise<{ ok: boolean; provider_id: string; model_id: string; deleted: boolean }> {
    const response = await httpClient.delete<{ ok: boolean; provider_id: string; model_id: string; deleted: boolean }>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/pricing`
    )
    return response.data
  }

  /**
   * Get "used" models for a provider.
   * GET /api/providers/{provider_id}/models/used
   */
  async getUsedModels(providerId: string): Promise<UsedModelsGetResponse> {
    const response = await httpClient.get<UsedModelsGetResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/models/used`
    )
    return response.data
  }

  /**
   * Set a model "used" flag.
   * PUT /api/providers/{provider_id}/models/{model_id}/used
   */
  async setModelUsed(providerId: string, modelId: string, used: boolean): Promise<SetModelUsedResponse> {
    const response = await httpClient.put<SetModelUsedResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/models/${encodeURIComponent(modelId)}/used`,
      { used }
    )
    return response.data
  }

  /**
   * Get masked cloud provider credential config.
   * GET /api/providers/{provider_id}/cloud-config
   */
  async getCloudConfig(providerId: string): Promise<CloudConfigGetResponse> {
    const response = await httpClient.get<CloudConfigGetResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-config`
    )
    return response.data
  }

  /**
   * Set cloud provider credentials.
   * PUT /api/providers/{provider_id}/cloud-config
   */
  async setCloudConfig(providerId: string, payload: CloudConfigSetRequest): Promise<CloudConfigSetResponse> {
    const response = await httpClient.put<CloudConfigSetResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-config`,
      payload
    )
    return response.data
  }

  /**
   * Clear cloud provider credentials.
   * DELETE /api/providers/{provider_id}/cloud-config
   */
  async deleteCloudConfig(providerId: string): Promise<CloudConfigDeleteResponse> {
    const response = await httpClient.delete<CloudConfigDeleteResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-config`
    )
    return response.data
  }

  /**
   * List all credential records for a cloud provider.
   * GET /api/providers/{provider_id}/cloud-configs
   */
  async listCloudConfigs(providerId: string): Promise<CloudConfigsListResponse> {
    const response = await httpClient.get<CloudConfigsListResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs`
    )
    return response.data
  }

  /**
   * Create a new credential record for a cloud provider.
   * POST /api/providers/{provider_id}/cloud-configs
   */
  async createCloudConfig(providerId: string, payload: CloudConfigRecordCreateRequest): Promise<CloudConfigSetResponse> {
    const response = await httpClient.post<CloudConfigSetResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs`,
      payload
    )
    return response.data
  }

  /**
   * Update an existing credential record.
   * PUT /api/providers/{provider_id}/cloud-configs/{config_id}
   */
  async updateCloudConfig(providerId: string, configId: string, payload: CloudConfigRecordUpsertRequest): Promise<{ ok: boolean; provider_id: string; config_id: string }> {
    const response = await httpClient.put<{ ok: boolean; provider_id: string; config_id: string }>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs/${encodeURIComponent(configId)}`,
      payload
    )
    return response.data
  }

  /**
   * Activate a credential record.
   * POST /api/providers/{provider_id}/cloud-configs/{config_id}/activate
   */
  async activateCloudConfig(providerId: string, configId: string): Promise<CloudConfigActivateResponse> {
    const response = await httpClient.post<CloudConfigActivateResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs/${encodeURIComponent(configId)}/activate`
    )
    return response.data
  }

  /**
   * Delete a credential record.
   * DELETE /api/providers/{provider_id}/cloud-configs/{config_id}
   */
  async deleteCloudConfigRecord(providerId: string, configId: string): Promise<CloudConfigRecordDeleteResponse> {
    const response = await httpClient.delete<CloudConfigRecordDeleteResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs/${encodeURIComponent(configId)}`
    )
    return response.data
  }

  /**
   * Test API reachability for a credential record (persists last_test).
   * POST /api/providers/{provider_id}/cloud-configs/{config_id}/test
   */
  async testCloudConfig(providerId: string, configId: string): Promise<CloudConfigTestResponse> {
    const response = await httpClient.post<CloudConfigTestResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/cloud-configs/${encodeURIComponent(configId)}/test`
    )
    return response.data
  }

  /**
   * P0-18: Create provider instance
   * POST /api/providers/{provider_id}/instances
   */
  async createInstance(
    providerId: string,
    config: InstanceConfigRequest
  ): Promise<InstanceConfigResponse> {
    const response = await httpClient.post<InstanceConfigResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances`,
      config
    )
    return response.data
  }

  /**
   * List provider instances
   * GET /api/providers/{provider_id}/instances
   */
  async listInstances(providerId: string): Promise<InstanceInfoResponse[]> {
    const response = await httpClient.get<InstanceInfoResponse[]>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances`
    )
    return response.data
  }

  /**
   * P0-19: Update provider instance configuration
   * PUT /api/providers/{provider_id}/instances/{instance_id}
   */
  async updateInstance(
    providerId: string,
    instanceId: string,
    config: InstanceConfigRequest
  ): Promise<InstanceConfigResponse> {
    const response = await httpClient.put<InstanceConfigResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}`,
      config
    )
    return response.data
  }

  /**
   * Delete provider instance
   * DELETE /api/providers/{provider_id}/instances/{instance_id}
   */
  async deleteInstance(providerId: string, instanceId: string): Promise<{ ok: boolean; instance_key: string }> {
    const response = await httpClient.delete<{ ok: boolean; instance_key: string }>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}`
    )
    return response.data
  }

  /**
   * Start a provider instance
   * POST /api/providers/{provider_id}/instances/{instance_id}/start
   */
  async startInstance(providerId: string, instanceId: string): Promise<InstanceControlResponse> {
    const response = await httpClient.post<InstanceControlResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}/start`
    )
    return response.data
  }

  /**
   * Stop a provider instance
   * POST /api/providers/{provider_id}/instances/{instance_id}/stop
   */
  async stopInstance(providerId: string, instanceId: string, force = false): Promise<InstanceControlResponse> {
    const response = await httpClient.post<InstanceControlResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}/stop`,
      null,
      { params: force ? { force: 'true' } : undefined }
    )
    return response.data
  }

  /**
   * Restart a provider instance
   * POST /api/providers/{provider_id}/instances/{instance_id}/restart
   */
  async restartInstance(providerId: string, instanceId: string): Promise<InstanceControlResponse> {
    const response = await httpClient.post<InstanceControlResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}/restart`
    )
    return response.data
  }

  /**
   * Get recent instance logs from ProcessManager buffers
   * GET /api/providers/{provider_id}/instances/{instance_id}/logs
   */
  async getInstanceLogs(
    providerId: string,
    instanceId: string,
    params?: { lines?: number; stream?: 'stdout' | 'stderr' }
  ): Promise<InstanceLogsResponse> {
    const response = await httpClient.get<InstanceLogsResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/instances/${encodeURIComponent(instanceId)}/logs`,
      { params }
    )
    return response.data
  }

  /**
   * Get installation suggestion text for local provider CLI/app.
   * GET /api/providers/{provider_id}/install-hint
   */
  async getInstallHint(providerId: string): Promise<InstallHintResponse> {
    const response = await httpClient.get<InstallHintResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/install-hint`
    )
    return response.data
  }

  /**
   * P2: Detect executable for a provider
   * GET /api/providers/{provider_id}/executable/detect
   */
  async detectExecutable(providerId: string): Promise<DetectExecutableResponse> {
    const response = await httpClient.get<DetectExecutableResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/executable/detect`
    )
    return response.data
  }

  /**
   * P2: Validate executable path for a provider
   * POST /api/providers/{provider_id}/executable/validate
   */
  async validateExecutable(
    providerId: string,
    path: string
  ): Promise<ValidateExecutableResponse> {
    const response = await httpClient.post<ValidateExecutableResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/executable/validate`,
      { path }
    )
    return response.data
  }

  /**
   * P2: Set executable path for a provider
   * PUT /api/providers/{provider_id}/executable
   */
  async setExecutablePath(
    providerId: string,
    path: string | null,
    autoDetect = true
  ): Promise<{ ok: boolean; message: string }> {
    const response = await httpClient.put<{ ok: boolean; message: string }>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/executable`,
      { path, auto_detect: autoDetect }
    )
    return response.data
  }

  /**
   * P2: Get diagnostics for a provider
   * GET /api/providers/{provider_id}/diagnostics
   */
  async getDiagnostics(providerId: string): Promise<ProviderDiagnosticsResponse> {
    const response = await httpClient.get<ProviderDiagnosticsResponse>(
      `${this.baseUrl}/${encodeURIComponent(providerId)}/diagnostics`
    )
    return response.data
  }
}

// ============================================
// Additional DTOs for new features
// ============================================

export interface DetectExecutableResponse {
  detected: boolean
  path: string | null
  custom_path: string | null
  resolved_path: string | null
  version: string | null
  platform: string
  search_paths: string[]
  is_valid: boolean
  detection_source: string | null
}

export interface ValidateExecutableResponse {
  is_valid: boolean
  path: string
  exists: boolean
  is_executable: boolean
  version: string | null
  error: string | null
}

export interface ProviderDiagnosticsResponse {
  provider_id: string
  platform: string
  detected_executable: string | null
  configured_executable: string | null
  resolved_executable: string | null
  detection_source: string | null
  version: string | null
  supported_actions: string[]
  current_status: string | null
  pid: number | null
  port: number | null
  port_listening: boolean | null
  models_directory: string | null
  models_count: number | null
  last_error: string | null
}

// Singleton instance
export const providersApi = new ProvidersApiClient()
