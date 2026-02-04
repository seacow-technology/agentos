/**
 * Usage Examples - How to use DTO types in Services layer
 *
 * This file demonstrates best practices for importing and using DTO types.
 * It will NOT be included in production build.
 */

// ============================================================================
// Example 1: Import from namespace (Recommended)
// ============================================================================

import type { AgentOS, MemoryOS, SkillOS, System } from '@modules'
import type { PaginationParams, ApiResponse } from '@modules/common'

// Use types with namespace prefix for clarity
async function exampleServiceWithNamespace(params: AgentOS.ListProjectsRequest): Promise<AgentOS.ListProjectsResponse> {
  // Implementation would use httpClient here
  return {
    projects: [],
    total: 0,
    limit: params.limit || 50,
    offset: params.offset || 0,
  }
}

// ============================================================================
// Example 2: Direct import (Alternative)
// ============================================================================

// For frequently used types, you can import directly
import type {
  Project,
  Task,
  ListProjectsRequest,
  TaskCreateRequest,
} from '@modules/agentos'

async function exampleServiceDirect(request: TaskCreateRequest): Promise<Task> {
  // Implementation
  return {
    task_id: 'task_123',
    title: request.title,
    status: 'draft',
    session_id: 'session_123',
    metadata: request.metadata || {},
    spec_frozen: 0,
  }
}

// ============================================================================
// Example 3: Using enums
// ============================================================================

import { TaskStatus, ProjectStatus } from '@modules/common'

function getTasksByStatus(status: TaskStatus): Promise<AgentOS.Task[]> {
  // Using enum for type-safe status values
  console.log('Filtering by status:', status)
  if (status === TaskStatus.COMPLETED) {
    // ...
  }
  return Promise.resolve([])
}

function filterProjects(status: ProjectStatus): Promise<AgentOS.Project[]> {
  // Type-safe project status filtering
  console.log('Filtering projects:', status)
  return Promise.resolve([])
}

// ============================================================================
// Example 4: Pagination with sorting
// ============================================================================

import type { PaginationWithSortParams } from '@modules/common'

async function listTasksWithSort(params: PaginationWithSortParams & { project_id?: string }): Promise<AgentOS.ListTasksResponse> {
  // Combine pagination + sort + custom filters
  console.log('Sorting:', params.sortBy, params.sortOrder)
  return {
    tasks: [],
    total: 0,
    limit: params.limit || 50,
    offset: params.offset || 0,
  }
}

// ============================================================================
// Example 5: API Response wrapping
// ============================================================================

async function getSkillWithErrorHandling(skill_id: string): Promise<ApiResponse<SkillOS.Skill>> {
  try {
    // Fetch skill
    const skill: SkillOS.Skill = {
      skill_id,
      name: 'Example Skill',
      version: '1.0.0',
      status: 'enabled',
      manifest_json: {},
    }

    return {
      ok: true,
      data: skill,
    }
  } catch (error) {
    return {
      ok: false,
      error: {
        code: 'SKILL_NOT_FOUND',
        message: `Skill ${skill_id} not found`,
        details: error,
      },
    }
  }
}

// ============================================================================
// Example 6: Memory operations
// ============================================================================

async function searchMemory(params: MemoryOS.SearchMemoryRequest): Promise<MemoryOS.SearchMemoryResponse> {
  // Search memory with filters
  return []
}

async function proposeMemory(request: MemoryOS.ProposeMemoryRequest): Promise<MemoryOS.ProposeMemoryResponse> {
  // Propose new memory item
  return {
    id: 'proposal_123',
    status: 'pending',
    message: 'Memory proposal created',
  }
}

// ============================================================================
// Example 7: Provider management
// ============================================================================

async function listProviders(): Promise<System.ProvidersListResponse> {
  return {
    local: [],
    cloud: [],
  }
}

async function getProviderStatus(provider_id: string): Promise<System.ProviderStatusResponse> {
  return {
    id: provider_id,
    type: 'local',
    state: 'running',
    endpoint: 'http://localhost:11434',
  }
}

// ============================================================================
// Example 8: Batch operations
// ============================================================================

async function createTasksBatch(req: AgentOS.TaskBatchCreateRequest): Promise<AgentOS.TaskBatchCreateResponse> {
  // Create multiple tasks at once
  console.log('Creating batch:', req.tasks.length, 'tasks')
  return {
    total: req.tasks.length,
    successful: 0,
    failed: 0,
    tasks: [],
    errors: [],
  }
}

// ============================================================================
// Example 9: Type guards (Runtime type checking)
// ============================================================================

function isProject(obj: unknown): obj is AgentOS.Project {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'project_id' in obj &&
    'name' in obj &&
    'status' in obj
  )
}

function isTask(obj: unknown): obj is AgentOS.Task {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'task_id' in obj &&
    'title' in obj &&
    'status' in obj
  )
}

// ============================================================================
// Example 10: Composing types
// ============================================================================

// Combine pagination with custom filters
type ProjectListParams = PaginationParams & {
  search?: string
  status?: ProjectStatus
  tags?: string[]
}

async function advancedProjectList(params: ProjectListParams): Promise<AgentOS.ListProjectsResponse> {
  // Advanced filtering with custom params
  return {
    projects: [],
    total: 0,
    limit: params.limit || 50,
    offset: params.offset || 0,
  }
}

// ============================================================================
// Export examples for reference
// ============================================================================

export {
  exampleServiceWithNamespace,
  exampleServiceDirect,
  getTasksByStatus,
  filterProjects,
  listTasksWithSort,
  getSkillWithErrorHandling,
  searchMemory,
  proposeMemory,
  listProviders,
  getProviderStatus,
  createTasksBatch,
  isProject,
  isTask,
  advancedProjectList,
}
