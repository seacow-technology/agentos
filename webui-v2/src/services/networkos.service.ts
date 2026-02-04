/**
 * NetworkOS Service
 *
 * API functions for NetworkOS:
 * - Capability governance
 * - Governance dashboard
 * - Guardian management
 * - Execution policies
 * - Evidence tracking
 */

import { httpClient, get, post, put, patch, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface Capability {
  id: string;
  name: string;
  description?: string;
  status: 'active' | 'inactive' | 'pending';
  trust_score?: number;
  created_at: string;
}

export interface ListCapabilitiesRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListCapabilitiesResponse {
  capabilities: Capability[];
  total: number;
}

export interface GetCapabilityResponse {
  capability: Capability;
}

export interface CreateCapabilityRequest {
  name: string;
  description?: string;
  config?: Record<string, unknown>;
}

export interface CreateCapabilityResponse {
  capability: Capability;
}

export interface UpdateCapabilityRequest {
  name?: string;
  description?: string;
  status?: string;
  config?: Record<string, unknown>;
}

export interface UpdateCapabilityResponse {
  capability: Capability;
}

export interface GovernanceDashboard {
  total_capabilities: number;
  active_capabilities: number;
  pending_reviews: number;
  trust_score_avg: number;
  recent_events: Array<Record<string, unknown>>;
}

export interface GetGovernanceDashboardResponse {
  dashboard: GovernanceDashboard;
}

export interface GovernanceRule {
  id: string;
  rule_type: string;
  config: Record<string, unknown>;
  enabled: boolean;
}

export interface ListGovernanceRulesResponse {
  rules: GovernanceRule[];
  total: number;
}

export interface Guardian {
  id: string;
  name: string;
  type: string;
  status: 'active' | 'inactive';
  config: Record<string, unknown>;
}

export interface ListGuardiansRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListGuardiansResponse {
  guardians: Guardian[];
  total: number;
}

export interface GetGuardianResponse {
  guardian: Guardian;
}

export interface GuardianAssignment {
  id: string;
  task_id: string;
  guardian_id: string;
  status: string;
  created_at: string;
}

export interface ListGuardianAssignmentsResponse {
  assignments: GuardianAssignment[];
  total: number;
}

export interface GetGuardianAssignmentResponse {
  assignment: GuardianAssignment;
}

export interface GuardianVerdict {
  id: string;
  assignment_id: string;
  verdict: 'approved' | 'rejected' | 'pending';
  reason?: string;
  created_at: string;
}

export interface ListGuardianVerdictsResponse {
  verdicts: GuardianVerdict[];
  total: number;
}

export interface GetGuardianVerdictResponse {
  verdict: GuardianVerdict;
}

export interface ExecutionPolicy {
  id: string;
  name: string;
  policy_type: string;
  rules: Record<string, unknown>;
  enabled: boolean;
}

export interface ListExecutionPoliciesRequest {
  enabled?: boolean;
  page?: number;
  limit?: number;
}

export interface ListExecutionPoliciesResponse {
  policies: ExecutionPolicy[];
  total: number;
}

export interface Evidence {
  id: string;
  evidence_type: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface CreateEvidenceRequest {
  evidence_type: string;
  data: Record<string, unknown>;
}

export interface CreateEvidenceResponse {
  evidence: Evidence;
}

export interface ListEvidenceRequest {
  evidence_type?: string;
  page?: number;
  limit?: number;
}

export interface ListEvidenceResponse {
  evidence: Evidence[];
  total: number;
}

// Governance Findings Types
export interface GovernanceFinding {
  id: string;
  finding_id: string;
  type: 'policy_violation' | 'trust_anomaly' | 'privilege_abuse' | 'audit_failure';
  severity: 'high' | 'medium' | 'low';
  entity: string;
  description: string;
  discovered_at: string;
  status: 'open' | 'investigating' | 'resolved';
  metadata?: Record<string, unknown>;
}

export interface ListGovernanceFindingsRequest {
  type?: string;
  severity?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListGovernanceFindingsResponse {
  findings: GovernanceFinding[];
  total: number;
}

export interface GetGovernanceFindingResponse {
  finding: GovernanceFinding;
}

// Federated Nodes Types
export interface FederatedNode {
  id: string;
  name: string;
  address: string;
  status: 'connected' | 'disconnected' | 'pending' | 'error';
  trust_level: number;
  last_heartbeat?: string;
  connected_at?: string;
  capabilities?: string[];
  metadata?: Record<string, unknown>;
}

export interface ListFederatedNodesRequest {
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListFederatedNodesResponse {
  nodes: FederatedNode[];
  total: number;
}

export interface GetFederatedNodeResponse {
  node: FederatedNode;
}

export interface ConnectNodeRequest {
  address: string;
  config?: Record<string, unknown>;
}

export interface ConnectNodeResponse {
  node: FederatedNode;
}

// Trust Tier Types
export interface TrustTierPolicy {
  risk_level: string;
  requires_admin_token: boolean;
  default_quota_profile: {
    calls_per_minute: number;
    max_concurrent: number;
    max_runtime_ms: number;
  };
}

export interface TrustTierInfo {
  tier: string;
  name: string;
  capabilities: string[];
  count: number;
  default_policy: TrustTierPolicy;
}

export interface ListTrustTiersResponse {
  tiers: TrustTierInfo[];
}

export interface GetTrustTierResponse {
  tier: TrustTierInfo;
}

// Trust Trajectory Types
export interface TrustState {
  extension_id: string;
  action_id: string;
  current_state: 'EARNING' | 'STABLE' | 'DEGRADING';
  consecutive_successes: number;
  consecutive_failures: number;
  policy_rejections: number;
  high_risk_events: number;
  state_entered_at_ms: number;
  last_event_at_ms: number;
  updated_at_ms: number;
}

export interface TrustTransition {
  transition_id: string;
  extension_id: string;
  action_id: string;
  old_state: 'EARNING' | 'STABLE' | 'DEGRADING';
  new_state: 'EARNING' | 'STABLE' | 'DEGRADING';
  trigger_event: string;
  explain: string;
  risk_context_json: string;
  policy_context_json: string;
  created_at_ms: number;
}

export interface TrustScorePoint {
  timestamp: string;
  trust_score: number;
  state: 'EARNING' | 'STABLE' | 'DEGRADING';
  event?: string;
}

export interface TrustTrajectory {
  entity_id: string;
  current_state: TrustState;
  score_history: TrustScorePoint[];
  transitions: TrustTransition[];
  stats: {
    total_transitions: number;
    time_in_current_state_hours: number;
    success_rate: number;
    policy_violation_count: number;
  };
}

export interface GetTrustTrajectoryRequest {
  entityId: string;
  timeRange?: '7d' | '30d' | '90d' | 'all';
}

export interface GetTrustTrajectoryResponse {
  trajectory: TrustTrajectory;
}

// Security Findings Types
export interface SecurityFinding {
  id: string;
  finding_id: string;
  title: string;
  description?: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: 'vulnerability' | 'misconfiguration' | 'compliance' | 'policy';
  status: 'new' | 'acknowledged' | 'in_progress' | 'resolved' | 'dismissed';
  discovered_at: string;
  updated_at?: string;
  source?: string;
  evidence?: string;
  recommendation?: string;
  impact?: string;
}

// Evolution Decision Types
export interface EvolutionDecision {
  decision_id: string;
  extension_id: string;
  action_id: string;
  action: 'PROMOTE' | 'FREEZE' | 'REVOKE' | 'NONE';
  risk_score: number;
  trust_tier: string;
  trust_trajectory: string;
  explanation: string;
  causal_chain: string[];
  review_level: 'NONE' | 'STANDARD' | 'HIGH_PRIORITY' | 'CRITICAL';
  conditions_met: string[];
  evidence: Record<string, unknown>;
  consequences: string[];
  requires_review: boolean;
  status?: 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'EXECUTED';
  proposed_at?: string;
  decided_at?: string;
  meta: {
    created_at: number;
    expires_at: number | null;
  };
}

export interface ListEvolutionDecisionsRequest {
  status?: 'PROPOSED' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | 'all';
  action?: 'PROMOTE' | 'FREEZE' | 'REVOKE' | 'NONE';
  page?: number;
  limit?: number;
}

export interface ListEvolutionDecisionsResponse {
  decisions: EvolutionDecision[];
  total: number;
}

export interface GetEvolutionDecisionResponse {
  decision: EvolutionDecision;
}

// Marketplace Registry Types
export interface MarketplaceCapability {
  id: string;
  name: string;
  publisher: string;
  version: string;
  status: 'active' | 'inactive' | 'pending';
  submitted_at: string;
  review_status: 'pending' | 'approved' | 'rejected';
  description?: string;
  tags?: string[];
}

export interface ListMarketplaceCapabilitiesRequest {
  review_status?: 'pending' | 'approved' | 'rejected' | 'all';
  page?: number;
  limit?: number;
}

export interface ListMarketplaceCapabilitiesResponse {
  capabilities: MarketplaceCapability[];
  total: number;
}

export interface GetMarketplaceCapabilityResponse {
  capability: MarketplaceCapability;
}

export interface ApproveCapabilityRequest {
  notes?: string;
}

export interface RejectCapabilityRequest {
  reason: string;
  notes?: string;
}

// Publisher Trust Types
export interface Publisher {
  publisher_id: string;
  name: string;
  trust_level: 'verified' | 'trusted' | 'unverified' | 'suspended';
  trust_score: number;
  capability_count: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_risk_score: number;
  registered_at: number;
  last_activity_at: number;
}

export interface PublisherDetail extends Publisher {
  capabilities: Array<Record<string, unknown>>;
}

export interface ListPublishersRequest {
  sort_by?: string;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface ListPublishersResponse {
  publishers: Publisher[];
  total: number;
}

export interface GetPublisherResponse {
  publisher: PublisherDetail;
}

export interface UpdatePublisherTrustResponse {
  publisher: Publisher;
}

// Remote Control Types
export interface RemoteConnection {
  conn_id: string;
  remote_node: string;
  status: 'active' | 'idle' | 'terminated';
  established_at: string;
  last_activity_at: string;
  command_count: number;
  metadata?: Record<string, unknown>;
}

export interface RemoteConnectionDetail extends RemoteConnection {
  command_history: Array<{
    command_id: string;
    command: string;
    executed_at: string;
    status: 'success' | 'failed' | 'timeout';
    result?: string;
    error?: string;
  }>;
}

export interface ListRemoteConnectionsRequest {
  status?: 'active' | 'idle' | 'terminated' | 'all';
  page?: number;
  limit?: number;
}

export interface ListRemoteConnectionsResponse {
  connections: RemoteConnection[];
  total: number;
}

export interface GetRemoteConnectionResponse {
  connection: RemoteConnectionDetail;
}

export interface ExecuteRemoteCommandRequest {
  command: string;
}

export interface ExecuteRemoteCommandResponse {
  command_id: string;
  status: 'success' | 'failed' | 'timeout';
  result?: string;
  error?: string;
  executed_at: string;
}

// ============================================================================
// Service Functions
// ============================================================================

export const networkosService = {
  // Capability Governance
  async listCapabilities(params?: ListCapabilitiesRequest): Promise<ListCapabilitiesResponse> {
    return get('/api/capability', { params });
  },

  async getCapability(id: string): Promise<GetCapabilityResponse> {
    return get(`/api/capability/${id}`);
  },

  async createCapability(data: CreateCapabilityRequest): Promise<CreateCapabilityResponse> {
    return post('/api/capability', data);
  },

  async updateCapability(id: string, data: UpdateCapabilityRequest): Promise<UpdateCapabilityResponse> {
    return put(`/api/capability/${id}`, data);
  },

  async deleteCapability(id: string): Promise<void> {
    return del(`/api/capability/${id}`);
  },

  async getCapabilityStatus(id: string): Promise<{ status: Record<string, unknown> }> {
    return get(`/api/capability/${id}/status`);
  },

  async enableCapability(id: string): Promise<UpdateCapabilityResponse> {
    return post(`/api/capability/${id}/enable`);
  },

  async disableCapability(id: string): Promise<UpdateCapabilityResponse> {
    return post(`/api/capability/${id}/disable`);
  },

  // Governance Dashboard
  async getGovernanceDashboard(): Promise<GetGovernanceDashboardResponse> {
    return get('/api/governance/dashboard');
  },

  async getGovernanceStatus(): Promise<{ status: Record<string, unknown> }> {
    return get('/api/governance/status');
  },

  async listGovernanceRules(): Promise<ListGovernanceRulesResponse> {
    return get('/api/governance/rules');
  },

  async getGovernanceRule(id: string): Promise<{ rule: GovernanceRule }> {
    return get(`/api/governance/rules/${id}`);
  },

  async updateGovernanceRule(id: string, data: Partial<GovernanceRule>): Promise<{ rule: GovernanceRule }> {
    return put(`/api/governance/rules/${id}`, data);
  },

  // Governance Findings
  async listGovernanceFindings(params?: ListGovernanceFindingsRequest): Promise<ListGovernanceFindingsResponse> {
    return get('/api/governance/findings', { params });
  },

  async getGovernanceFinding(id: string): Promise<GetGovernanceFindingResponse> {
    return get(`/api/governance/findings/${id}`);
  },

  async updateGovernanceFinding(id: string, data: Partial<GovernanceFinding>): Promise<GetGovernanceFindingResponse> {
    return put(`/api/governance/findings/${id}`, data);
  },

  async deleteGovernanceFinding(id: string): Promise<void> {
    return del(`/api/governance/findings/${id}`);
  },

  // Guardian Management
  async listGuardians(params?: ListGuardiansRequest): Promise<ListGuardiansResponse> {
    return get('/api/guardians', { params });
  },

  async getGuardian(id: string): Promise<GetGuardianResponse> {
    return get(`/api/guardians/${id}`);
  },

  async getTaskAssignments(taskId: string): Promise<ListGuardianAssignmentsResponse> {
    return get(`/api/guardians/tasks/${taskId}/assignments`);
  },

  async getGuardianAssignment(id: string): Promise<GetGuardianAssignmentResponse> {
    return get(`/api/guardians/assignments/${id}`);
  },

  async getTaskVerdicts(taskId: string): Promise<ListGuardianVerdictsResponse> {
    return get(`/api/guardians/tasks/${taskId}/verdicts`);
  },

  async getGuardianVerdict(id: string): Promise<GetGuardianVerdictResponse> {
    return get(`/api/guardians/verdicts/${id}`);
  },

  // Execution Policies
  async listExecutionPolicies(params?: ListExecutionPoliciesRequest): Promise<ListExecutionPoliciesResponse> {
    return get('/api/execution/policies', { params });
  },

  async getExecutionPolicy(id: string): Promise<{ policy: ExecutionPolicy }> {
    return get(`/api/execution/policies/${id}`);
  },

  async createExecutionPolicy(data: { name: string; policy_type: string; rules: Record<string, unknown> }): Promise<{ policy: ExecutionPolicy }> {
    return post('/api/execution/policies', data);
  },

  async updateExecutionPolicy(id: string, data: Partial<ExecutionPolicy>): Promise<{ policy: ExecutionPolicy }> {
    return put(`/api/execution/policies/${id}`, data);
  },

  async deleteExecutionPolicy(id: string): Promise<void> {
    return del(`/api/execution/policies/${id}`);
  },

  // Evidence Tracking
  async createEvidence(data: CreateEvidenceRequest): Promise<CreateEvidenceResponse> {
    return post('/api/evidence', data);
  },

  async listEvidence(params?: ListEvidenceRequest): Promise<ListEvidenceResponse> {
    return get('/api/evidence', { params });
  },

  async getEvidence(id: string): Promise<{ evidence: Evidence }> {
    return get(`/api/evidence/${id}`);
  },

  // Trust Trajectory
  async getTrustTrajectory(params: GetTrustTrajectoryRequest): Promise<GetTrustTrajectoryResponse> {
    const { entityId, timeRange = '30d' } = params;
    return get(`/api/trust/trajectory/${entityId}`, {
      params: { time_range: timeRange },
    });
  },

  async listTrustStates(params?: { state?: string; page?: number; limit?: number }): Promise<{ states: TrustState[]; total: number }> {
    return get('/api/trust/states', { params });
  },

  async getTrustTransitions(entityId: string, params?: { page?: number; limit?: number }): Promise<{ transitions: TrustTransition[]; total: number }> {
    return get(`/api/trust/transitions/${entityId}`, { params });
  },

  // Trust Tiers
  async listTrustTiers(): Promise<ListTrustTiersResponse> {
    return get('/api/governance/trust-tiers');
  },

  async getTrustTier(tierId: string): Promise<GetTrustTierResponse> {
    const response = await httpClient.get('/api/governance/trust-tiers') as ListTrustTiersResponse;
    const tier = response.tiers.find(t => t.tier === tierId);
    if (!tier) {
      throw new Error(`Trust tier ${tierId} not found`);
    }
    return { tier };
  },

  // Security Findings
  async listFindings(params?: {
    severity?: string;
    status?: string;
    category?: string;
    offset?: number;
    limit?: number;
  }): Promise<{ findings: SecurityFinding[]; total: number }> {
    // Backend endpoint is /api/lead/findings
    const response = await get<{ findings: any[]; total: number }>('/api/lead/findings', { params });
    return response;
  },

  async getFinding(findingId: string): Promise<{ finding: SecurityFinding }> {
    return get(`/api/lead/findings/${findingId}`);
  },

  async updateFindingStatus(
    findingId: string,
    status: 'new' | 'acknowledged' | 'in_progress' | 'resolved' | 'dismissed',
    comment?: string
  ): Promise<{ finding: SecurityFinding }> {
    return patch(`/api/lead/findings/${findingId}/status`, { status, comment });
  },

  // Evolution Decisions
  async listEvolutionDecisions(params?: ListEvolutionDecisionsRequest): Promise<ListEvolutionDecisionsResponse> {
    return get('/api/governance/evolution-decisions', { params });
  },

  async getEvolutionDecision(decisionId: string): Promise<GetEvolutionDecisionResponse> {
    return get(`/api/governance/evolution-decisions/${decisionId}`);
  },

  // Marketplace Registry
  async listMarketplaceCapabilities(params?: ListMarketplaceCapabilitiesRequest): Promise<ListMarketplaceCapabilitiesResponse> {
    return get('/api/marketplace/capabilities', { params });
  },

  async getMarketplaceCapability(capabilityId: string): Promise<GetMarketplaceCapabilityResponse> {
    return get(`/api/marketplace/capabilities/${capabilityId}`);
  },

  async approveCapability(capabilityId: string, data?: ApproveCapabilityRequest): Promise<{ success: boolean }> {
    return post(`/api/marketplace/capabilities/${capabilityId}/approve`, data || {});
  },

  async rejectCapability(capabilityId: string, data: RejectCapabilityRequest): Promise<{ success: boolean }> {
    return post(`/api/marketplace/capabilities/${capabilityId}/reject`, data);
  },

  // Federated Nodes
  async listFederatedNodes(params?: ListFederatedNodesRequest): Promise<ListFederatedNodesResponse> {
    return get('/api/federation/nodes', { params });
  },

  async getFederatedNode(nodeId: string): Promise<GetFederatedNodeResponse> {
    return get(`/api/federation/nodes/${nodeId}`);
  },

  async connectNode(nodeId: string, config?: ConnectNodeRequest): Promise<ConnectNodeResponse> {
    return post(`/api/federation/nodes/${nodeId}/connect`, config || {});
  },

  async disconnectNode(nodeId: string): Promise<void> {
    return post(`/api/federation/nodes/${nodeId}/disconnect`);
  },

  // Publisher Trust Management
  async listPublishers(params?: ListPublishersRequest): Promise<ListPublishersResponse> {
    return get('/api/marketplace/publishers', { params });
  },

  async getPublisher(publisherId: string): Promise<GetPublisherResponse> {
    return get(`/api/marketplace/publishers/${publisherId}`);
  },

  async updatePublisherTrust(publisherId: string): Promise<UpdatePublisherTrustResponse> {
    return patch(`/api/marketplace/publishers/${publisherId}/trust`, {});
  },

  // Remote Control Management
  async listRemoteConnections(params?: { status?: string; page?: number; limit?: number }): Promise<ListRemoteConnectionsResponse> {
    return get('/api/remote/connections', { params });
  },

  async getRemoteConnection(connId: string): Promise<GetRemoteConnectionResponse> {
    return get(`/api/remote/connections/${connId}`);
  },

  async executeRemoteCommand(connId: string, command: ExecuteRemoteCommandRequest): Promise<ExecuteRemoteCommandResponse> {
    return post(`/api/remote/connections/${connId}/execute`, command);
  },

  async terminateRemoteConnection(connId: string): Promise<void> {
    return del(`/api/remote/connections/${connId}`);
  },
};
