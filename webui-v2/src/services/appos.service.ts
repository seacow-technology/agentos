/**
 * AppOS Service
 *
 * API functions for AppOS:
 * - Application management
 * - App lifecycle (start/stop/restart)
 * - App status and health
 */

import { get, post, put, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface App {
  id: string;
  name: string;
  description?: string;
  version: string;
  status: 'running' | 'stopped' | 'error';
  created_at: string;
}

export interface ListAppsRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListAppsResponse {
  apps: App[];
  total: number;
}

export interface GetAppResponse {
  app: App;
}

export interface CreateAppRequest {
  name: string;
  description?: string;
  version?: string;
  config?: Record<string, unknown>;
}

export interface CreateAppResponse {
  app: App;
}

export interface UpdateAppRequest {
  name?: string;
  description?: string;
  version?: string;
  config?: Record<string, unknown>;
}

export interface UpdateAppResponse {
  app: App;
}

export interface GetAppStatusResponse {
  status: string;
  health: 'healthy' | 'unhealthy' | 'unknown';
  metrics: Record<string, unknown>;
  last_check: string;
}

export interface StartAppResponse {
  app: App;
  started_at: string;
}

export interface StopAppResponse {
  app: App;
  stopped_at: string;
}

export interface RestartAppResponse {
  app: App;
  restarted_at: string;
}

export interface GetAppLogsRequest {
  lines?: number;
  since?: string;
}

export interface GetAppLogsResponse {
  logs: string[];
  total_lines: number;
}

// ============================================================================
// Service Functions
// ============================================================================

export const apposService = {
  // App Management
  async listApps(params?: ListAppsRequest): Promise<ListAppsResponse> {
    return get('/api/apps', { params });
  },

  async getApp(id: string): Promise<GetAppResponse> {
    return get(`/api/apps/${id}`);
  },

  async createApp(data: CreateAppRequest): Promise<CreateAppResponse> {
    return post('/api/apps', data);
  },

  async updateApp(id: string, data: UpdateAppRequest): Promise<UpdateAppResponse> {
    return put(`/api/apps/${id}`, data);
  },

  async deleteApp(id: string): Promise<void> {
    return del(`/api/apps/${id}`);
  },

  // App Status & Health
  async getAppStatus(id: string): Promise<GetAppStatusResponse> {
    return get(`/api/apps/${id}/status`);
  },

  async getAppHealth(id: string): Promise<{ health: string; details: Record<string, unknown> }> {
    return get(`/api/apps/${id}/health`);
  },

  // App Lifecycle
  async startApp(id: string): Promise<StartAppResponse> {
    return post(`/api/apps/${id}/start`);
  },

  async stopApp(id: string): Promise<StopAppResponse> {
    return post(`/api/apps/${id}/stop`);
  },

  async restartApp(id: string): Promise<RestartAppResponse> {
    return post(`/api/apps/${id}/restart`);
  },

  // App Logs
  async getAppLogs(id: string, params?: GetAppLogsRequest): Promise<GetAppLogsResponse> {
    return get(`/api/apps/${id}/logs`, { params });
  },
};
