/**
 * AppOS Module DTOs
 * Covers: Applications, extensions, plugins
 * Note: Placeholder for future implementation
 */

// TODO: Add AppOS DTOs when backend APIs are finalized
export interface Application {
  id: string
  name: string
  version: string
  status: string
  created_at: string
}

export interface Extension {
  id: string
  app_id: string
  name: string
  enabled: boolean
  created_at: string
}

// ========== API Request/Response Types ==========

export interface ListAppsRequest {
  status?: string
}

export type ListAppsResponse = Application[]

export interface GetAppRequest {
  id: string
}

export type GetAppResponse = Application
