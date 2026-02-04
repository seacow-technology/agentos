/**
 * System Module DTOs
 * Covers: Config, Providers, Models, Migrations
 */

// ========== Config ==========

export interface ConfigResponse {
  version: string
  python_version: string
  environment: Record<string, unknown>
  settings: Record<string, unknown>
}

export interface MigrationInfo {
  version: string
  description: string
  filename: string
}

export interface MigrationsStatusResponse {
  current_version?: string
  latest_version?: string
  pending_count: number
  migrations: MigrationInfo[]
  needs_migration: boolean
  db_path: string
}

export interface MigrateRequest {
  target_version?: string
}

export interface MigrateResponse {
  success: boolean
  message: string
  from_version?: string
  to_version?: string
  migrations_executed: number
}

// ========== Providers ==========

export interface ProviderInfo {
  id: string
  label: string
  type: 'local' | 'cloud'
  supports_models: boolean
  supports_start?: boolean
  supports_auth?: string[]
}

export interface ProviderStatusResponse {
  id: string
  type: string
  state: string
  endpoint?: string
  latency_ms?: number
  last_ok_at?: string
  last_error?: string
  // Health check details
  pid?: number
  pid_exists?: boolean
  port_listening?: boolean
  api_responding?: boolean
}

export interface ModelInfoResponse {
  id: string
  label: string
  context_window?: number
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

export interface ModelsListRequest {
  provider_id: string
}

export interface ModelsListResponse {
  provider_id: string
  models: ModelInfoResponse[]
}

// ========== Local Provider Detection ==========

export interface LocalDetectResultResponse {
  id: string
  cli_found: boolean
  service_reachable: boolean
  endpoint: string
  models_count: number
  details: Record<string, unknown>
  state: string
}

export interface LocalDetectResponse {
  ts: string
  results: LocalDetectResultResponse[]
}

// ========== Runtime Management ==========

export interface RuntimeActionResponse {
  status: string
  message: string
  pid?: number
  endpoint?: string
}

export interface RuntimeStatusResponse {
  provider_id: string
  is_running: boolean
  pid?: number
  command?: string
  started_at?: string
  endpoint?: string
}

// ========== Cloud Configuration ==========

export interface CloudConfigRequest {
  provider_id: string
  auth: Record<string, string> // {"type": "api_key", "api_key": "..."}
  base_url?: string
}

export interface CloudConfigResponse {
  ok: boolean
  message?: string
}

export interface CloudTestRequest {
  provider_id: string
}

export interface CloudTestResponse {
  ok: boolean
  state?: string
  latency_ms?: number
  models_count?: number
  error?: string
}

// ========== Provider Instances ==========

export interface ProviderInstance {
  instance_id: string
  provider_id: string
  label: string
  type: 'local' | 'cloud'
  state: string
  endpoint?: string
  auth_configured: boolean
  is_default: boolean
  created_at: string
  updated_at?: string
  metadata?: Record<string, unknown>
}

export interface ListInstancesRequest {
  provider_id?: string
  type?: 'local' | 'cloud'
}

export type ListInstancesResponse = ProviderInstance[]

export interface CreateInstanceRequest {
  provider_id: string
  label: string
  endpoint?: string
  auth?: Record<string, string>
  is_default?: boolean
  metadata?: Record<string, unknown>
}

export type CreateInstanceResponse = ProviderInstance

export interface UpdateInstanceRequest {
  label?: string
  endpoint?: string
  auth?: Record<string, string>
  is_default?: boolean
  metadata?: Record<string, unknown>
}

export type UpdateInstanceResponse = ProviderInstance

export interface DeleteInstanceResponse {
  message: string
}

// ========== Provider Lifecycle ==========

export interface StartProviderRequest {
  instance_id: string
}

export type StartProviderResponse = RuntimeActionResponse

export interface StopProviderRequest {
  instance_id: string
}

export type StopProviderResponse = RuntimeActionResponse

export interface RestartProviderRequest {
  instance_id: string
}

export type RestartProviderResponse = RuntimeActionResponse

export interface GetProviderStatusRequest {
  instance_id: string
}

export type GetProviderStatusResponse = ProviderStatusResponse

// ========== Models ==========

export interface Model {
  id: string
  name: string
  provider_id: string
  instance_id?: string
  context_window?: number
  capabilities?: string[]
  metadata?: Record<string, unknown>
}

export interface ListModelsRequest {
  provider_id?: string
  instance_id?: string
}

export type ListModelsResponse = Model[]

export interface GetModelRequest {
  model_id: string
}

export type GetModelResponse = Model

export interface PullModelRequest {
  provider_id: string
  model_name: string
}

export interface PullModelResponse {
  status: string
  message: string
  progress?: number
}

export interface DeleteModelRequest {
  provider_id: string
  model_name: string
}

export interface DeleteModelResponse {
  status: string
  message: string
}

// ========== Health Check ==========

export interface HealthCheckResponse {
  status: string
  timestamp: string
  version?: string
}

// ========== Demo Mode ==========

export interface DemoModeStatusResponse {
  enabled: boolean
  timestamp?: string
}

export interface ToggleDemoModeRequest {
  enabled: boolean
}

export interface ToggleDemoModeResponse {
  enabled: boolean
  message?: string
}
