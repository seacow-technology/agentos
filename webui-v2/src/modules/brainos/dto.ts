/**
 * BrainOS Module DTOs
 * Covers: Brain cache, governance, decision-making
 * Note: Placeholder for future implementation
 */

// TODO: Add BrainOS DTOs when backend APIs are finalized
export interface BrainCache {
  id: string
  key: string
  value: unknown
  created_at: string
  expires_at?: string
}

export interface BrainGovernance {
  id: string
  policy: string
  status: string
  created_at: string
}

// ========== API Request/Response Types ==========

export interface ListKnowledgeSourcesRequest {
  type?: string
}

export interface KnowledgeSource {
  id: string
  name: string
  type: string
  status: string
  created_at: string
}

export type ListKnowledgeSourcesResponse = KnowledgeSource[]

export interface CreateKnowledgeSourceRequest {
  name: string
  type: string
  config: Record<string, unknown>
}

export type CreateKnowledgeSourceResponse = KnowledgeSource

export interface GetDecisionComparisonRequest {
  decision_id: string
}

export interface DecisionComparison {
  decision_id: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  diff: string[]
}

export type GetDecisionComparisonResponse = DecisionComparison

export interface ListReviewQueueRequest {
  status?: string
}

export interface ReviewQueueItem {
  id: string
  type: string
  status: string
  created_at: string
}

export type ListReviewQueueResponse = ReviewQueueItem[]

export interface InfoNeedMetrics {
  total_queries: number
  resolved: number
  unresolved: number
  avg_resolution_time: number
}

export type GetInfoNeedMetricsResponse = InfoNeedMetrics
