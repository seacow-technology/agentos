/**
 * Execution Plans API Client
 *
 * Handles all execution plan-related API calls
 */

import { httpClient } from '@platform/http'

// ============================================
// DTOs
// ============================================

export interface ExecutionPlanStep {
  step_id: string
  description: string
  status: string
  started_at?: string
  completed_at?: string
}

export interface ExecutionPlan {
  id: string
  name: string
  description?: string
  status: string
  priority: string
  steps: number
  created_at: string
  estimated_time?: string
  executed_at?: string
}

export interface ExecutionPlansListResponse {
  plans: ExecutionPlan[]
  total: number
  limit: number
  offset: number
}

export interface ExecutionPlanDetailResponse {
  plan: ExecutionPlan
  steps: ExecutionPlanStep[]
}

export interface ExecutionPlanListFilters {
  status?: string
  priority?: string
  limit?: number
  offset?: number
  sort?: string
}

// ============================================
// API Client
// ============================================

class ExecutionPlansApiClient {
  private baseUrl = '/api/execution-plans'

  /**
   * List execution plans with optional filters
   * GET /api/execution-plans
   */
  async listPlans(filters?: ExecutionPlanListFilters): Promise<ExecutionPlansListResponse> {
    const response = await httpClient.get<ExecutionPlansListResponse>(this.baseUrl, {
      params: filters
    })
    return response.data
  }

  /**
   * Get execution plan details by ID
   * GET /api/execution-plans/{plan_id}
   */
  async getPlan(planId: string): Promise<ExecutionPlanDetailResponse> {
    const response = await httpClient.get<ExecutionPlanDetailResponse>(`${this.baseUrl}/${encodeURIComponent(planId)}`)
    return response.data
  }
}

// Singleton instance
export const executionPlansApi = new ExecutionPlansApiClient()
