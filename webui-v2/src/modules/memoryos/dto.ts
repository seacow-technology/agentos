/**
 * MemoryOS Module DTOs
 * Covers: Memory Search, Upsert, Timeline, Proposals
 */

import type { PaginationParams } from '../common'

// ========== Memory Items ==========

export interface MemoryItem {
  id: string
  namespace: string
  key: string
  value: string
  source?: string // task_id or session_id
  source_type?: 'task' | 'session' | 'manual'
  created_at: string
  ttl?: number // seconds
  metadata: Record<string, unknown>
}

export interface SearchMemoryRequest extends PaginationParams {
  q?: string
  namespace?: string
}

export type SearchMemoryResponse = MemoryItem[]

export interface UpsertMemoryRequest {
  namespace: string
  key: string
  value: string
  source?: string
  source_type?: 'task' | 'session' | 'manual'
  ttl?: number
  metadata?: Record<string, unknown>
}

export type UpsertMemoryResponse = MemoryItem

export interface GetMemoryRequest {
  item_id: string
}

export type GetMemoryResponse = MemoryItem

// ========== Memory History ==========

export interface MemoryHistoryItem {
  id: string
  value: string
  content: Record<string, unknown>
  confidence: number
  version: number
  is_active: boolean
  supersedes?: string
  superseded_by?: string
  superseded_at?: string
  created_at: string
  updated_at: string
}

export interface GetMemoryHistoryRequest {
  item_id: string
}

export type GetMemoryHistoryResponse = MemoryHistoryItem[]

// ========== Memory Timeline ==========

export interface TimelineItem {
  id: string
  timestamp: string
  key: string
  value: string
  type: string
  source: 'rule_extraction' | 'explicit' | 'system'
  confidence: number
  is_active: boolean
  version: number
  supersedes?: string
  superseded_by?: string
  scope: string
  project_id?: string
  task_id?: string
  metadata?: Record<string, unknown>
}

export interface GetTimelineRequest extends PaginationParams {
  project_id?: string
  task_id?: string
}

export interface GetTimelineResponse {
  items: TimelineItem[]
  total: number
  page: number
  has_more: boolean
}

// ========== Memory Proposals ==========

export interface MemoryProposal {
  id: string
  namespace: string
  key: string
  value: string
  proposed_by: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  reviewed_at?: string
  reviewed_by?: string
  reason?: string
  metadata?: Record<string, unknown>
}

export interface ProposeMemoryRequest {
  namespace: string
  key: string
  value: string
  reason?: string
  metadata?: Record<string, unknown>
}

export interface ProposeMemoryResponse {
  id: string
  status: string
  message: string
}

export interface ListProposalsRequest extends PaginationParams {
  status?: 'pending' | 'approved' | 'rejected'
}

export interface ListProposalsResponse {
  proposals: MemoryProposal[]
  total: number
}

export interface GetProposalRequest {
  id: string
}

export type GetProposalResponse = MemoryProposal

export interface ApproveProposalRequest {
  id: string
}

export interface ApproveProposalResponse {
  id: string
  status: string
  message: string
}

export interface RejectProposalRequest {
  id: string
  reason?: string
}

export interface RejectProposalResponse {
  id: string
  status: string
  message: string
}

// ========== Proposal Stats ==========

export interface ProposalStats {
  total: number
  pending: number
  approved: number
  rejected: number
}

export type GetProposalStatsResponse = ProposalStats
