/**
 * SkillOS Module DTOs
 * Covers: Skills Registry, Import, Enable/Disable
 */

import type { ApiResponse } from '../common'

// ========== Skills ==========

export interface Skill {
  skill_id: string
  name: string
  version: string
  status: 'enabled' | 'disabled' | 'imported_disabled'
  manifest_json: Record<string, unknown>
  source_type?: 'local' | 'github'
  source_ref?: string
  created_at?: number
  updated_at?: number
  [key: string]: unknown
}

export interface ListSkillsRequest {
  status?: 'enabled' | 'disabled' | 'imported_disabled' | 'all'
}

export interface ListSkillsResponse extends ApiResponse<Skill[]> {}

export interface GetSkillRequest {
  skill_id: string
}

export interface GetSkillResponse extends ApiResponse<Skill> {}

// ========== Import ==========

export interface ImportLocalRequest {
  type: 'local'
  path: string
}

export interface ImportGitHubRequest {
  type: 'github'
  owner: string
  repo: string
  ref?: string
  subdir?: string
}

export type ImportSkillRequest = ImportLocalRequest | ImportGitHubRequest

export interface ImportResponse {
  skill_id: string
  status: string
  message: string
}

// ========== Status Change ==========

export interface EnableSkillRequest {
  skill_id: string
}

export interface DisableSkillRequest {
  skill_id: string
}

export interface StatusResponse {
  skill_id: string
  status: string
  message: string
}
