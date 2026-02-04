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
  label: string
  context_window: number | null
}

export interface ModelsListResponse {
  provider_id: string
  models: ModelInfoResponse[]
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

export interface ControlResponse {
  ok: boolean
  provider: string
  action: string
  state: string
  pid?: number
  message: string
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
   * P0-18: Create provider instance
   * POST /api/providers/instances/{provider_id}
   */
  async createInstance(
    providerId: string,
    config: InstanceConfigRequest
  ): Promise<InstanceConfigResponse> {
    const response = await httpClient.post<InstanceConfigResponse>(
      `${this.baseUrl}/instances/${encodeURIComponent(providerId)}`,
      config
    )
    return response.data
  }

  /**
   * P0-19: Update provider instance configuration
   * PUT /api/providers/instances/{provider_id}/{instance_id}
   */
  async updateInstance(
    providerId: string,
    instanceId: string,
    config: InstanceConfigRequest
  ): Promise<InstanceConfigResponse> {
    const response = await httpClient.put<InstanceConfigResponse>(
      `${this.baseUrl}/instances/${encodeURIComponent(providerId)}/${encodeURIComponent(instanceId)}`,
      config
    )
    return response.data
  }

  /**
   * Delete provider instance
   * DELETE /api/providers/instances/{provider_id}/{instance_id}
   */
  async deleteInstance(providerId: string, instanceId: string): Promise<{ ok: boolean; instance_key: string }> {
    const response = await httpClient.delete<{ ok: boolean; instance_key: string }>(
      `${this.baseUrl}/instances/${encodeURIComponent(providerId)}/${encodeURIComponent(instanceId)}`
    )
    return response.data
  }

  /**
   * P0-20: Start Ollama service
   * POST /api/providers/ollama/start
   */
  async startOllama(): Promise<ControlResponse> {
    const response = await httpClient.post<ControlResponse>(`${this.baseUrl}/ollama/start`)
    return response.data
  }

  /**
   * P0-20: Stop Ollama service
   * POST /api/providers/ollama/stop
   */
  async stopOllama(force = false): Promise<ControlResponse> {
    const response = await httpClient.post<ControlResponse>(
      `${this.baseUrl}/ollama/stop`,
      null,
      { params: force ? { force: 'true' } : undefined }
    )
    return response.data
  }

  /**
   * P0-20: Restart Ollama service
   * POST /api/providers/ollama/restart
   */
  async restartOllama(): Promise<ControlResponse> {
    const response = await httpClient.post<ControlResponse>(`${this.baseUrl}/ollama/restart`)
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
