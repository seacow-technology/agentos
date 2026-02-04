/**
 * Risk Service
 *
 * API functions for Risk Timeline:
 * - Risk Timeline (Phase E - Risk Timeline View)
 * - Risk Scores
 * - Risk Dimensions
 */

import { get } from '@platform/http';

// ============================================================================
// Risk Timeline Types
// ============================================================================

export interface RiskScore {
  timestamp: string;
  overall_score: number;
  execution_risk: number;
  trust_risk: number;
  policy_risk: number;
  capability_risk: number;
}

export interface RiskTimelineData {
  scores: RiskScore[];
  summary: {
    current_risk: number;
    avg_risk: number;
    max_risk: number;
    trend: 'increasing' | 'decreasing' | 'stable';
  };
}

export interface ListRiskTimelineRequest {
  start_time?: string;
  end_time?: string;
  dimension?: string;
  limit?: number;
}

export interface ListRiskTimelineResponse {
  data: RiskTimelineData;
}

// ============================================================================
// Service Functions
// ============================================================================

export const riskService = {
  /**
   * Get risk timeline data
   * Based on v1 API: GET /api/risk/timeline
   */
  async getRiskTimeline(params?: ListRiskTimelineRequest): Promise<ListRiskTimelineResponse> {
    return get('/api/risk/timeline', { params });
  },

  /**
   * Get risk dimensions
   */
  async getRiskDimensions(): Promise<{ dimensions: string[] }> {
    return get('/api/risk/dimensions');
  },

  /**
   * Get current risk status
   */
  async getCurrentRiskStatus(): Promise<{
    overall_risk: number;
    execution_risk: number;
    trust_risk: number;
    policy_risk: number;
    capability_risk: number;
  }> {
    return get('/api/risk/current');
  },
};
