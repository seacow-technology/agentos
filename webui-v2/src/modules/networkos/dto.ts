/**
 * NetworkOS Module DTOs
 * Covers: Federation, trust, cross-system communication
 * Note: Placeholder for future implementation
 */

// TODO: Add NetworkOS DTOs when backend APIs are finalized
export interface FederatedTrust {
  id: string
  remote_system: string
  trust_level: number
  created_at: string
}

export interface CrossSystemMessage {
  id: string
  from_system: string
  to_system: string
  payload: unknown
  status: string
  created_at: string
}

// ========== API Request/Response Types ==========

export interface ListCapabilitiesRequest {
  status?: string
}

export interface Capability {
  id: string
  name: string
  type: string
  status: string
  created_at: string
}

export type ListCapabilitiesResponse = Capability[]

export interface GetCapabilityRequest {
  id: string
}

export type GetCapabilityResponse = Capability

export interface GovernanceDashboard {
  total_policies: number
  active_policies: number
  violations: number
  last_updated: string
}

export type GetGovernanceDashboardResponse = GovernanceDashboard

export interface ListGuardiansRequest {
  status?: string
}

export interface Guardian {
  id: string
  name: string
  status: string
  created_at: string
}

export type ListGuardiansResponse = Guardian[]

export interface ListExecutionPoliciesRequest {
  status?: string
}

export interface ExecutionPolicy {
  id: string
  name: string
  rules: Record<string, unknown>
  status: string
  created_at: string
}

export type ListExecutionPoliciesResponse = ExecutionPolicy[]
