/**
 * MemoryOS Service
 *
 * API functions for MemoryOS:
 * - Memory search and management
 * - Memory timeline
 * - Memory proposals (approve/reject)
 * - Memory history
 */

import { get, post } from '@platform/http';

// ============================================================================
// Temporary Types (Will be replaced by @modules imports in A8)
// ============================================================================

export interface MemoryItem {
  id: string;
  content: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  relevance?: number; // 0.0 - 1.0, optional relevance score
}

export interface MemorySearchRequest {
  query?: string;
  limit?: number;
  offset?: number;
}

export interface MemorySearchResponse {
  results: MemoryItem[];
  total: number;
}

export interface MemoryUpsertRequest {
  id?: string;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface MemoryUpsertResponse {
  item: MemoryItem;
}

export interface GetMemoryItemResponse {
  item: MemoryItem;
}

export interface MemoryHistory {
  id: string;
  item_id: string;
  content: string;
  version: number;
  created_at: string;
}

export interface GetMemoryHistoryResponse {
  history: MemoryHistory[];
}

export interface MemoryTimelineEvent {
  id: string;
  event_type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface GetMemoryTimelineRequest {
  start_time?: string;
  end_time?: string;
  event_type?: string;
  limit?: number;
}

export interface GetMemoryTimelineResponse {
  events: MemoryTimelineEvent[];
  total: number;
}

export interface MemoryProposal {
  id: string;
  proposal_type: string;
  content: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  updated_at?: string;
}

export interface CreateMemoryProposalRequest {
  agent_id: string;
  memory_item: {
    key: string;
    value: string;
    namespace?: string;
    metadata?: Record<string, unknown>;
  };
  reason?: string;
}

export interface CreateMemoryProposalResponse {
  proposal_id: string;
  status: string;
}

export interface ListMemoryProposalsRequest {
  status?: 'pending' | 'approved' | 'rejected';
  page?: number;
  limit?: number;
}

export interface ListMemoryProposalsResponse {
  proposals: MemoryProposal[];
  total: number;
}

export interface GetMemoryProposalResponse {
  proposal: MemoryProposal;
}

export interface ApproveMemoryProposalRequest {
  reason?: string;
}

export interface ApproveMemoryProposalResponse {
  proposal: MemoryProposal;
}

export interface RejectMemoryProposalRequest {
  reason?: string;
}

export interface RejectMemoryProposalResponse {
  proposal: MemoryProposal;
}

export interface GetMemoryProposalsStatsResponse {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

// Phase 6.1 Memory Entries
export interface MemoryEntry {
  id: string;
  content: string;
  type: 'fact' | 'preference' | 'context' | 'relationship';
  importance: 'high' | 'medium' | 'low';
  source: string;
  createdAt: string;
  accessCount: number;
}

export interface GetMemoryEntriesResponse {
  data: MemoryEntry[];
  total: number;
}

// ============================================================================
// Service Functions
// ============================================================================

export const memoryosService = {
  // Memory Search & Management
  async searchMemory(params?: MemorySearchRequest): Promise<MemorySearchResponse> {
    return get('/api/memory/search', { params });
  },

  async upsertMemory(data: MemoryUpsertRequest): Promise<MemoryUpsertResponse> {
    return post('/api/memory/upsert', data);
  },

  async getMemoryItem(id: string): Promise<GetMemoryItemResponse> {
    return get(`/api/memory/${id}`);
  },

  async getMemoryHistory(id: string): Promise<GetMemoryHistoryResponse> {
    return get(`/api/memory/${id}/history`);
  },

  // Memory Timeline
  async getMemoryTimeline(params?: GetMemoryTimelineRequest): Promise<GetMemoryTimelineResponse> {
    return get('/api/memory/timeline', { params });
  },

  // Memory Proposals
  async createMemoryProposal(data: CreateMemoryProposalRequest): Promise<CreateMemoryProposalResponse> {
    return post('/api/memory/propose', data);
  },

  async listMemoryProposals(params?: ListMemoryProposalsRequest): Promise<ListMemoryProposalsResponse> {
    return get('/api/memory/proposals', { params });
  },

  async getMemoryProposal(id: string): Promise<GetMemoryProposalResponse> {
    return get(`/api/memory/proposals/${id}`);
  },

  async approveMemoryProposal(id: string, data?: ApproveMemoryProposalRequest): Promise<ApproveMemoryProposalResponse> {
    return post(`/api/memory/proposals/${id}/approve`, data);
  },

  async rejectMemoryProposal(id: string, data?: RejectMemoryProposalRequest): Promise<RejectMemoryProposalResponse> {
    return post(`/api/memory/proposals/${id}/reject`, data);
  },

  async getMemoryProposalsStats(): Promise<GetMemoryProposalsStatsResponse> {
    return get('/api/memory/proposals/stats');
  },

  // Phase 6.1 Memory Entries
  async getMemoryEntries(): Promise<GetMemoryEntriesResponse> {
    return get('/api/memory/entries');
  },
};
