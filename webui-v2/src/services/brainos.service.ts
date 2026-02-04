/**
 * BrainOS Service
 *
 * API functions for BrainOS:
 * - Knowledge management
 * - Decision comparison
 * - Review queue
 * - Brain governance
 * - Intent analysis
 * - Info need metrics
 */

import { get, post, put, del } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface KnowledgeSource {
  id: string;
  name: string;
  type: string;
  status: string;
  created_at: string;
}

export interface ListKnowledgeSourcesRequest {
  type?: string;
  status?: string;
  page?: number;
  limit?: number;
}

export interface ListKnowledgeSourcesResponse {
  sources: KnowledgeSource[];
  total: number;
}

export interface QueryKnowledgeRequest {
  query: string;
  limit?: number;
  filters?: Record<string, unknown>;
}

export interface QueryKnowledgeResponse {
  results: Array<{
    id: string;
    content: string;
    score: number;
    metadata?: Record<string, unknown>;
  }>;
  total: number;
}

export interface DecisionComparison {
  id: string;
  decision_a: Record<string, unknown>;
  decision_b: Record<string, unknown>;
  differences: Array<Record<string, unknown>>;
  created_at: string;
}

export interface CreateDecisionComparisonRequest {
  decision_a_id: string;
  decision_b_id: string;
}

export interface CreateDecisionComparisonResponse {
  comparison: DecisionComparison;
}

export interface ListDecisionComparisonsRequest {
  page?: number;
  limit?: number;
}

export interface ListDecisionComparisonsResponse {
  comparisons: DecisionComparison[];
  total: number;
}

export interface ReviewQueueItem {
  id: string;
  proposal_type: string;
  content: string;
  status: 'pending' | 'approved' | 'rejected' | 'deferred';
  created_at: string;
  updated_at?: string;
}

export interface ListReviewQueueRequest {
  status?: 'pending' | 'approved' | 'rejected' | 'deferred';
  page?: number;
  limit?: number;
}

export interface ListReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
}

export interface GetReviewQueueItemResponse {
  item: ReviewQueueItem;
}

export interface ApproveReviewItemRequest {
  reason?: string;
}

export interface ApproveReviewItemResponse {
  item: ReviewQueueItem;
}

export interface RejectReviewItemRequest {
  reason: string;
}

export interface RejectReviewItemResponse {
  item: ReviewQueueItem;
}

export interface DeferReviewItemRequest {
  reason?: string;
  defer_until?: string;
}

export interface DeferReviewItemResponse {
  item: ReviewQueueItem;
}

export interface Intent {
  id: string;
  intent_type: string;
  confidence: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface GetIntentResponse {
  intent: Intent;
}

export interface ExplainIntentResponse {
  explanation: string;
  factors: Array<Record<string, unknown>>;
}

export interface CompareIntentsResponse {
  differences: Array<Record<string, unknown>>;
  similarity_score: number;
}

export interface MergeIntentProposalRequest {
  target_intent_id: string;
  merge_strategy?: string;
}

export interface MergeIntentProposalResponse {
  proposal_id: string;
}

export interface InfoNeedMetric {
  id: string;
  metric_name: string;
  value: number;
  timestamp: string;
}

export interface GetInfoNeedMetricsRequest {
  start_time?: string;
  end_time?: string;
  metric_names?: string[];
}

export interface GetInfoNeedMetricsResponse {
  metrics: InfoNeedMetric[];
  summary: Record<string, unknown>;
}

export interface BrainGovernanceStatus {
  total_proposals: number;
  pending_reviews: number;
  approved_count: number;
  rejected_count: number;
}

export interface GetBrainGovernanceStatusResponse {
  status: BrainGovernanceStatus;
}

// Governance Decision Types
export interface GovernanceDecisionRule {
  rule_id: string;
  rule_name: string;
  action: 'ALLOW' | 'WARN' | 'BLOCK' | 'REQUIRE_SIGNOFF';
  rationale: string;
}

export interface IntegrityCheck {
  passed: boolean;
  computed_hash: string;
  stored_hash: string;
  algorithm: string;
}

export interface Signoff {
  signed_by: string;
  sign_timestamp: string;
  sign_note: string;
}

export interface ReplayData {
  then_state?: Record<string, unknown>;
  now_state?: Record<string, unknown>;
  changed_facts?: string[];
}

export interface GovernanceDecision {
  decision_id: string;
  decision_type: 'NAVIGATION' | 'COMPARE' | 'HEALTH';
  seed: string;
  timestamp: string;
  status: 'PENDING' | 'APPROVED' | 'BLOCKED' | 'SIGNED' | 'FAILED';
  final_verdict: 'ALLOW' | 'WARN' | 'BLOCK' | 'REQUIRE_SIGNOFF';
  confidence_score?: number;
  rules_triggered: GovernanceDecisionRule[];
  integrity_check?: IntegrityCheck;
  signoff?: Signoff;
  snapshot_ref?: string;
  audit_trail?: Record<string, unknown>;
}

export interface ListGovernanceDecisionsRequest {
  seed?: string;
  decision_type?: 'NAVIGATION' | 'COMPARE' | 'HEALTH';
  status?: 'PENDING' | 'APPROVED' | 'BLOCKED' | 'SIGNED' | 'FAILED';
  limit?: number;
}

export interface ListGovernanceDecisionsResponse {
  records: GovernanceDecision[];
  count: number;
}

export interface GetGovernanceDecisionResponse {
  decision: GovernanceDecision;
  integrity_verified: boolean;
}

export interface ReplayDecisionResponse {
  decision: GovernanceDecision;
  integrity_check: IntegrityCheck;
  replay_timestamp: string;
  warnings: Array<{ level: string; message: string; details?: string }>;
  audit_trail: Record<string, unknown>;
  signoff?: Signoff;
  snapshot?: Record<string, unknown>;
  rules_triggered: GovernanceDecisionRule[];
  then_state?: Record<string, unknown>;
  now_state?: Record<string, unknown>;
  changed_facts?: string[];
}

export interface SignoffDecisionRequest {
  signed_by: string;
  note: string;
}

export interface SignoffDecisionResponse {
  signoff_id: string;
  decision_id: string;
  signed_by: string;
  timestamp: string;
  note: string;
  new_status: string;
}

export interface KnowledgeHealthIssue {
  id: string;
  type: 'orphaned_node' | 'broken_link' | 'stale_knowledge' | 'duplicate_entry';
  description: string;
  severity: 'low' | 'medium' | 'high';
  created_at: string;
}

export interface KnowledgeHealth {
  index_health_score: number;
  orphaned_nodes: number;
  broken_links: number;
  stale_knowledge: number;
  duplicate_entries: number;
  embedding_quality: number;
  vector_coverage: number;
  retrieval_accuracy: number;
  issues?: KnowledgeHealthIssue[];
}

export interface GetKnowledgeHealthResponse {
  health: KnowledgeHealth;
}

export interface BrainDashboardData {
  knowledge_sources_count: number;
  memory_entries_count: number;
  index_coverage: number; // percentage 0-100
  avg_query_time: number; // milliseconds
  rag_success_rate: number; // percentage 0-100
  embedding_calls_count: number;
  vector_index_size: number; // bytes
  index_service_status: 'healthy' | 'degraded' | 'offline';
  embedding_service_status: 'healthy' | 'degraded' | 'offline';
  retrieval_service_status: 'healthy' | 'degraded' | 'offline';
}

export interface GetBrainDashboardResponse {
  dashboard: BrainDashboardData;
}

// ============================================================================
// Service Functions
// ============================================================================

export const brainosService = {
  // Knowledge Management
  async listKnowledgeSources(params?: ListKnowledgeSourcesRequest): Promise<ListKnowledgeSourcesResponse> {
    return get('/api/knowledge/sources', { params });
  },

  async queryKnowledge(data: QueryKnowledgeRequest): Promise<QueryKnowledgeResponse> {
    return post('/api/knowledge/query', data);
  },

  async getKnowledgeSource(id: string): Promise<{ source: KnowledgeSource }> {
    return get(`/api/knowledge/sources/${id}`);
  },

  async createKnowledgeSource(data: { name: string; type: string; config?: Record<string, unknown> }): Promise<{ source: KnowledgeSource }> {
    return post('/api/knowledge/sources', data);
  },

  async updateKnowledgeSource(id: string, data: Partial<{ name: string; config: Record<string, unknown> }>): Promise<{ source: KnowledgeSource }> {
    return put(`/api/knowledge/sources/${id}`, data);
  },

  async deleteKnowledgeSource(id: string): Promise<void> {
    return del(`/api/knowledge/sources/${id}`);
  },

  // Decision Comparison
  async listDecisionComparisons(params?: ListDecisionComparisonsRequest): Promise<ListDecisionComparisonsResponse> {
    return get('/api/v3/decision-comparison', { params });
  },

  async createDecisionComparison(data: CreateDecisionComparisonRequest): Promise<CreateDecisionComparisonResponse> {
    return post('/api/v3/decision-comparison', data);
  },

  async getDecisionComparison(id: string): Promise<{ comparison: DecisionComparison }> {
    return get(`/api/v3/decision-comparison/${id}`);
  },

  // Review Queue
  async listReviewQueue(params?: ListReviewQueueRequest): Promise<ListReviewQueueResponse> {
    return get('/api/v3/review-queue', { params });
  },

  async getReviewQueueItem(id: string): Promise<GetReviewQueueItemResponse> {
    return get(`/api/v3/review-queue/${id}`);
  },

  async approveReviewItem(id: string, data?: ApproveReviewItemRequest): Promise<ApproveReviewItemResponse> {
    return post(`/api/v3/review-queue/${id}/approve`, data);
  },

  async rejectReviewItem(id: string, data: RejectReviewItemRequest): Promise<RejectReviewItemResponse> {
    return post(`/api/v3/review-queue/${id}/reject`, data);
  },

  async deferReviewItem(id: string, data?: DeferReviewItemRequest): Promise<DeferReviewItemResponse> {
    return post(`/api/v3/review-queue/${id}/defer`, data);
  },

  // Brain Governance
  async getBrainGovernanceStatus(): Promise<GetBrainGovernanceStatusResponse> {
    return get('/api/brain/governance/status');
  },

  // Governance Decisions
  async listGovernanceDecisions(params?: ListGovernanceDecisionsRequest): Promise<ListGovernanceDecisionsResponse> {
    const response = await get<{ ok: boolean; data: { records: GovernanceDecision[]; count: number }; error: string | null }>(
      '/api/brain/governance/decisions',
      { params }
    );
    if (!response.ok || !response.data) {
      throw new Error(response.error || 'Failed to load governance decisions');
    }
    return response.data;
  },

  async getGovernanceDecision(decisionId: string): Promise<GetGovernanceDecisionResponse> {
    const response = await get<{ ok: boolean; data: GovernanceDecision & { integrity_verified: boolean }; error: string | null }>(
      `/api/brain/governance/decisions/${decisionId}`
    );
    if (!response.ok || !response.data) {
      throw new Error(response.error || 'Failed to load decision detail');
    }
    return {
      decision: response.data,
      integrity_verified: response.data.integrity_verified || false,
    };
  },

  async replayGovernanceDecision(decisionId: string): Promise<ReplayDecisionResponse> {
    const response = await get<{ ok: boolean; data: ReplayDecisionResponse; error: string | null }>(
      `/api/brain/governance/decisions/${decisionId}/replay`
    );
    if (!response.ok || !response.data) {
      throw new Error(response.error || 'Failed to load decision replay');
    }
    return response.data;
  },

  async signoffGovernanceDecision(decisionId: string, data: SignoffDecisionRequest): Promise<SignoffDecisionResponse> {
    const response = await post<{ ok: boolean; data: SignoffDecisionResponse; error: string | null }>(
      `/api/brain/governance/decisions/${decisionId}/signoff`,
      data
    );
    if (!response.ok || !response.data) {
      throw new Error(response.error || 'Failed to sign off decision');
    }
    return response.data;
  },

  async getBrainGovernanceDashboard(): Promise<Record<string, unknown>> {
    return get('/api/brain/governance/dashboard');
  },

  // Intent Analysis
  async getIntent(id: string): Promise<GetIntentResponse> {
    return get(`/api/intent/${id}`);
  },

  async explainIntent(id: string): Promise<ExplainIntentResponse> {
    return get(`/api/intent/${id}/explain`);
  },

  async compareIntents(id: string, otherId: string): Promise<CompareIntentsResponse> {
    return get(`/api/intent/${id}/diff/${otherId}`);
  },

  async createMergeProposal(id: string, data: MergeIntentProposalRequest): Promise<MergeIntentProposalResponse> {
    return post(`/api/intent/${id}/merge-proposal`, data);
  },

  // Info Need Metrics
  async getInfoNeedMetrics(params?: GetInfoNeedMetricsRequest): Promise<GetInfoNeedMetricsResponse> {
    return get('/api/info-need-metrics/summary', { params });
  },

  async getInfoNeedMetricsSummary(): Promise<Record<string, unknown>> {
    return get('/api/info-need-metrics/summary');
  },

  // Knowledge Health
  async getKnowledgeHealth(): Promise<GetKnowledgeHealthResponse> {
    return get('/api/brain/knowledge-health');
  },

  // Brain Dashboard
  async getBrainDashboard(): Promise<GetBrainDashboardResponse> {
    return get('/api/brain/dashboard');
  },

  // Brain Stats (V1 compatibility)
  async getBrainStats(): Promise<{
    ok: boolean;
    data: {
      entities: number;
      edges: number;
      evidence: number;
      last_build: {
        graph_version: string;
        source_commit: string;
        built_at: number;
        duration_ms: number;
      } | null;
      coverage: {
        doc_refs_pct: number;
        dep_graph_pct: number;
        git_coverage: boolean;
        doc_coverage: boolean;
        code_coverage: boolean;
      };
      blind_spots: any[];
    };
  }> {
    return get('/api/brain/stats');
  },

  // Brain Coverage (V1 compatibility)
  async getBrainCoverage(): Promise<{
    ok: boolean;
    data: {
      total_files: number;
      covered_files: number;
      code_coverage: number;
      doc_coverage: number;
      dependency_coverage: number;
      git_covered_files: number;
      doc_covered_files: number;
      dep_covered_files: number;
      uncovered_files: string[];
      evidence_distribution: Record<string, number>;
      graph_version: string;
      computed_at: string;
    };
  }> {
    return get('/api/brain/coverage');
  },

  // Brain Blind Spots (V1 compatibility)
  async getBrainBlindSpots(maxResults: number = 10): Promise<{
    ok: boolean;
    data: {
      total_blind_spots: number;
      by_type: Record<string, number>;
      by_severity: {
        high: number;
        medium: number;
        low: number;
      };
      blind_spots: Array<{
        entity_name: string;
        entity_key: string;
        severity: number;
        reason: string;
        type: string;
      }>;
      graph_version: string;
      computed_at: string;
    };
  }> {
    return get('/api/brain/blind-spots', { params: { max_results: maxResults } });
  },

  // Build Brain Index
  async buildBrainIndex(force: boolean = false): Promise<{ ok: boolean; error?: string }> {
    return post('/api/brain/build', { force });
  },

  // Subgraph Query
  async getSubgraph(nodeId: string, depth: number): Promise<{
    nodes: Array<{
      id: string;
      entity_type: string;
      entity_key: string;
      entity_name: string;
      evidence_count: number;
      coverage_sources: string[];
      evidence_density: number;
      is_blind_spot: boolean;
      blind_spot_severity?: number;
      blind_spot_type?: string;
      blind_spot_reason?: string;
      in_degree: number;
      out_degree: number;
      distance_from_seed: number;
      missing_connections_count?: number;
      gap_types?: string[];
      visual: {
        color: string;
        size: number;
        border_color: string;
        border_width: number;
        border_style: string;
        shape: string;
        label: string;
        tooltip: string;
      };
    }>;
    edges: Array<{
      source: string;
      target: string;
      type: string;
      evidence_count: number;
      confidence: number;
      visual: {
        width: number;
        color: string;
        style: string;
      };
    }>;
    metadata: {
      node_count: number;
      edge_count: number;
      blind_spot_count: number;
      gap_anchor_count: number;
      avg_evidence_density: number;
    };
  }> {
    return get('/api/brain/subgraph', {
      params: { node_id: nodeId, depth }
    });
  },

  // Context Manager
  async getContextManager(sessionId: string): Promise<{
    session_id: string;
    state: string;
    updated_at: string;
    tokens: {
      prompt: number;
      completion: number;
      context_window: number;
      used: number;
      available: number;
    };
    rag: Record<string, unknown>;
    memory: Record<string, unknown>;
  }> {
    return get('/api/context/status', { params: { session_id: sessionId } });
  },

  async clearContext(sessionId: string): Promise<{ ok: boolean; message?: string }> {
    return post('/api/context/detach', null, { params: { session_id: sessionId } });
  },

  async refreshContext(sessionId: string): Promise<{ ok: boolean; state?: string; message?: string }> {
    return post('/api/context/refresh', { session_id: sessionId });
  },

  async attachContext(sessionId: string, config: { memory?: { enabled: boolean; namespace: string }; rag?: { enabled: boolean } }): Promise<{ ok: boolean; message?: string }> {
    return post('/api/context/attach', { session_id: sessionId, ...config });
  },

  async listSessions(limit = 10): Promise<Array<{ id: string; title?: string; created_at?: string }>> {
    const response = await get<{ sessions?: Array<{ id: string; title?: string; created_at?: string }> }>('/api/sessions', { params: { limit } });
    return response.sessions || [];
  },
};
