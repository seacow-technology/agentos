/**
 * CommunicationOS Service
 *
 * API functions for CommunicationOS:
 * - Channels management
 * - Channels marketplace
 * - Communication sessions
 * - Voice/Twilio integration
 * - MCP (Model Context Protocol) servers
 * - MCP marketplace
 */

import { get, post, put, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface Channel {
  id: string;
  name: string;
  type: string;
  status: 'active' | 'inactive' | 'error';
  config: Record<string, unknown>;
  created_at: string;
}

export interface ListChannelsRequest {
  type?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListChannelsResponse {
  channels: Channel[];
  total: number;
}

export interface GetChannelResponse {
  channel: Channel;
}

export interface CreateChannelRequest {
  name: string;
  type: string;
  config: Record<string, unknown>;
}

export interface CreateChannelResponse {
  channel: Channel;
}

export interface UpdateChannelRequest {
  name?: string;
  config?: Record<string, unknown>;
}

export interface UpdateChannelResponse {
  channel: Channel;
}

export interface ChannelMarketplaceItem {
  id: string;
  name: string;
  description?: string;
  type: string;
  status: 'available' | 'installed' | 'disabled';
  version: string;
}

export interface ListChannelMarketplaceRequest {
  type?: string;
  status?: string;
}

export interface ListChannelMarketplaceResponse {
  items: ChannelMarketplaceItem[];
  total: number;
}

export interface GetChannelMarketplaceItemResponse {
  item: ChannelMarketplaceItem;
}

export interface GetChannelConfigResponse {
  config: Record<string, unknown>;
}

export interface UpdateChannelConfigRequest {
  config: Record<string, unknown>;
}

export interface UpdateChannelConfigResponse {
  config: Record<string, unknown>;
}

export interface EnableChannelResponse {
  channel: ChannelMarketplaceItem;
}

export interface DisableChannelResponse {
  channel: ChannelMarketplaceItem;
}

export interface TestChannelRequest {
  test_message?: string;
  test_config?: Record<string, unknown>;
}

export interface TestChannelResponse {
  success: boolean;
  message: string;
  details?: Record<string, unknown>;
}

export interface ChannelEvent {
  id: string;
  channel_id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
}

export interface ListChannelEventsRequest {
  event_type?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  limit?: number;
}

export interface ListChannelEventsResponse {
  events: ChannelEvent[];
  total: number;
}

export interface CommunicationSession {
  id: string;
  channel_id: string;
  status: 'active' | 'completed' | 'failed';
  started_at: string;
  ended_at?: string;
}

export interface ListCommunicationSessionsRequest {
  channel_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListCommunicationSessionsResponse {
  sessions: CommunicationSession[];
  total: number;
}

export interface GetCommunicationSessionResponse {
  session: CommunicationSession;
}

export interface VoiceSession {
  id: string;
  phone_number?: string;
  status: 'active' | 'completed' | 'failed';
  started_at: string;
  ended_at?: string;
}

export interface ListVoiceSessionsRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListVoiceSessionsResponse {
  sessions: VoiceSession[];
  total: number;
}

export interface MCPServer {
  id: string;
  name: string;
  url: string;
  status: 'connected' | 'disconnected' | 'error';
  capabilities: string[];
}

export interface ListMCPServersResponse {
  servers: MCPServer[];
  total: number;
}

export interface GetMCPServerResponse {
  server: MCPServer;
}

export interface RefreshMCPServersResponse {
  refreshed_count: number;
  servers: MCPServer[];
}

export interface MCPMarketplaceItem {
  package_id: string;
  name: string;
  description?: string;
  version: string;
  author: string;
  tools_count?: number;
  transport: string;
  recommended_trust_tier: string;
  requires_admin_token: boolean;
  is_connected: boolean;
  tags: string[];
  downloads?: string;
}

export interface ListMCPMarketplaceRequest {
  search?: string;
  tag?: string;
  connected_only?: boolean;
}

export interface ListMCPMarketplaceResponse {
  packages: MCPMarketplaceItem[];
  total: number;
}

export interface MCPTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  side_effects: string[];
  requires_confirmation: boolean;
}

export interface MCPPackageDetail {
  package_id: string;
  name: string;
  version: string;
  author: string;
  description: string;
  long_description?: string;
  tools: MCPTool[];
  declared_side_effects: string[];
  transport: string;
  connection_template?: Record<string, unknown>;
  recommended_trust_tier: string;
  recommended_quota_profile?: string;
  requires_admin_token: boolean;
  homepage?: string;
  repository?: string;
  license?: string;
  tags: string[];
  is_connected: boolean;
  connected_at?: string;
}

export interface MCPGovernancePreview {
  package_id: string;
  inferred_trust_tier: string;
  inferred_risk_level: string;
  default_quota: {
    calls_per_minute: number;
    max_concurrent: number;
    max_runtime_ms: number;
  };
  requires_admin_token_for: string[];
  gate_warnings: string[];
  audit_level: string;
}

export interface AttachMCPPackageRequest {
  package_id: string;
  override_trust_tier?: string;
  custom_config?: Record<string, unknown>;
}

export interface AttachMCPPackageResponse {
  server_id: string;
  status: string;
  enabled: boolean;
  trust_tier: string;
  audit_id: string;
  warnings: string[];
  next_steps: string[];
}

// ============================================================================
// Service Functions
// ============================================================================

export const communicationosService = {
  // Channels Management
  async listChannels(params?: ListChannelsRequest): Promise<ListChannelsResponse> {
    return get('/api/channels', { params });
  },

  async getChannel(id: string): Promise<GetChannelResponse> {
    return get(`/api/channels/${id}`);
  },

  async createChannel(data: CreateChannelRequest): Promise<CreateChannelResponse> {
    return post('/api/channels', data);
  },

  async updateChannel(id: string, data: UpdateChannelRequest): Promise<UpdateChannelResponse> {
    return put(`/api/channels/${id}`, data);
  },

  async deleteChannel(id: string): Promise<void> {
    return del(`/api/channels/${id}`);
  },

  async getChannelStatus(id: string): Promise<{ status: Record<string, unknown> }> {
    return get(`/api/channels/${id}/status`);
  },

  // Channels Marketplace
  async listChannelMarketplace(params?: ListChannelMarketplaceRequest): Promise<ListChannelMarketplaceResponse> {
    return get('/api/channels-marketplace', { params });
  },

  async getChannelMarketplaceItem(id: string): Promise<GetChannelMarketplaceItemResponse> {
    return get(`/api/channels-marketplace/${id}`);
  },

  async getChannelConfig(id: string): Promise<GetChannelConfigResponse> {
    return get(`/api/channels-marketplace/${id}/config`);
  },

  async updateChannelConfig(id: string, data: UpdateChannelConfigRequest): Promise<UpdateChannelConfigResponse> {
    return put(`/api/channels-marketplace/${id}/config`, data);
  },

  async enableChannel(id: string): Promise<EnableChannelResponse> {
    return post(`/api/channels-marketplace/${id}/enable`);
  },

  async disableChannel(id: string): Promise<DisableChannelResponse> {
    return post(`/api/channels-marketplace/${id}/disable`);
  },

  async testChannel(id: string, data?: TestChannelRequest): Promise<TestChannelResponse> {
    return post(`/api/channels-marketplace/${id}/test`, data);
  },

  async getChannelEvents(id: string, params?: ListChannelEventsRequest): Promise<ListChannelEventsResponse> {
    return get(`/api/channels-marketplace/${id}/events`, { params });
  },

  // Communication Sessions
  async listCommunicationSessions(params?: ListCommunicationSessionsRequest): Promise<ListCommunicationSessionsResponse> {
    return get('/api/communication/sessions', { params });
  },

  async getCommunicationSession(id: string): Promise<GetCommunicationSessionResponse> {
    return get(`/api/communication/sessions/${id}`);
  },

  // Voice/Twilio Integration
  async listVoiceSessions(params?: ListVoiceSessionsRequest): Promise<ListVoiceSessionsResponse> {
    return get('/api/voice/sessions', { params });
  },

  async getVoiceSession(id: string): Promise<{ session: VoiceSession }> {
    return get(`/api/voice/sessions/${id}`);
  },

  async startVoiceCall(data: { phone_number: string; config?: Record<string, unknown> }): Promise<{ session: VoiceSession }> {
    return post('/api/voice/call', data);
  },

  async endVoiceCall(sessionId: string): Promise<void> {
    return post(`/api/voice/sessions/${sessionId}/end`);
  },

  // MCP Servers Management
  async listMCPServers(): Promise<ListMCPServersResponse> {
    return get('/api/mcp/servers');
  },

  async getMCPServer(id: string): Promise<GetMCPServerResponse> {
    return get(`/api/mcp/servers/${id}`);
  },

  async refreshMCPServers(): Promise<RefreshMCPServersResponse> {
    return post('/api/mcp/servers/refresh');
  },

  async connectMCPServer(id: string): Promise<{ server: MCPServer }> {
    return post(`/api/mcp/servers/${id}/connect`);
  },

  async disconnectMCPServer(id: string): Promise<void> {
    return post(`/api/mcp/servers/${id}/disconnect`);
  },

  // MCP Marketplace
  async listMCPMarketplace(params?: ListMCPMarketplaceRequest): Promise<ListMCPMarketplaceResponse> {
    return get('/api/mcp/marketplace/packages', { params });
  },

  async getMCPMarketplaceItem(packageId: string): Promise<{ ok: boolean; data: MCPPackageDetail }> {
    return get(`/api/mcp/marketplace/packages/${packageId}`);
  },

  async getMCPGovernancePreview(packageId: string): Promise<{ ok: boolean; data: MCPGovernancePreview }> {
    return get(`/api/mcp/marketplace/governance-preview/${packageId}`);
  },

  async attachMCPPackage(data: AttachMCPPackageRequest): Promise<{ ok: boolean; data: AttachMCPPackageResponse }> {
    return post('/api/mcp/marketplace/attach', data);
  },

  async uninstallMCPPackage(packageId: string): Promise<{ ok: boolean; data: { audit_id: string; warnings: string[] } }> {
    return del(`/api/communicationos/mcp/packages/${packageId}/uninstall`);
  },

  // Communication Audit & Control API (CommunicationOS Core)
  async getNetworkMode(): Promise<{
    current_state: { mode: string; updated_at: string; updated_by?: string };
    recent_history: any[];
    available_modes: string[];
  }> {
    return get('/api/communication/mode');
  },

  async setNetworkMode(data: {
    mode: string;
    reason?: string;
    updated_by?: string;
  }): Promise<{
    previous_mode: string;
    new_mode: string;
    changed: boolean;
    timestamp: string;
    updated_by?: string;
    reason?: string;
  }> {
    return put('/api/communication/mode', data);
  },

  async getCommunicationStatus(): Promise<{
    status: string;
    network_mode: string;
    connectors: Record<string, any>;
    statistics: Record<string, any>;
    timestamp: string;
  }> {
    return get('/api/communication/status');
  },

  async getCommunicationPolicy(): Promise<Record<string, any>> {
    return get('/api/communication/policy');
  },

  async listCommunicationAudits(params?: {
    connector_type?: string;
    operation?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }): Promise<{
    audits: Array<{
      id: string;
      request_id: string;
      connector_type: string;
      operation: string;
      status: string;
      risk_level?: string;
      created_at: string;
    }>;
    total: number;
    filters_applied: Record<string, any>;
  }> {
    return get('/api/communication/audits', { params });
  },

  async getCommunicationAuditDetail(auditId: string): Promise<{
    id: string;
    request_id: string;
    connector_type: string;
    operation: string;
    request_summary: Record<string, any>;
    response_summary?: Record<string, any>;
    status: string;
    metadata: Record<string, any>;
    created_at: string;
  }> {
    return get(`/api/communication/audits/${auditId}`);
  },
};
