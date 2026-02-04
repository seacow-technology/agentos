/**
 * Capability Dashboard Types
 *
 * Types for AgentOS v3 Capability Governance Dashboard
 * API: GET /api/capability/dashboard/stats
 */

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface DomainStats {
  count: number
  active_agents: number
}

export interface InvocationStats {
  total_invocations: number
  allowed: number
  denied: number
}

export interface CapabilityDashboardStats {
  domains: Record<string, DomainStats>
  today_stats: InvocationStats
  risk_distribution: Record<RiskLevel, number>
}

export interface CapabilityDashboardResponse {
  ok: boolean
  data: CapabilityDashboardStats | null
  error: string | null
}
