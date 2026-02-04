/**
 * Tasks API Client
 *
 * Handles all task-related API calls following backend API contracts
 */

import { httpClient } from '@platform/http'

// ============================================
// DTOs (matching backend)
// ============================================

export interface TaskMetadata {
  [key: string]: any
}

export interface TaskSummary {
  task_id: string
  title: string
  status: string
  session_id?: string
  project_id?: string
  created_at: string
  updated_at?: string
  metadata: TaskMetadata
}

export interface TaskResponse {
  task_id: string
  title: string
  status: string
  session_id: string
  project_id?: string
  created_at?: string
  updated_at?: string
  created_by?: string
  metadata: TaskMetadata
  spec_frozen: number
  route_plan_json?: string
  requirements_json?: string
  selected_instance_id?: string
  router_version?: string
  repo_id?: string
  workdir?: string
}

export interface TasksListResponse {
  tasks: TaskSummary[]
  total: number
  limit: number
  offset: number
}

export interface TaskCreateRequest {
  title: string
  project_id?: string
  created_by?: string
  metadata?: TaskMetadata
}

export interface TaskBatchItem {
  title: string
  project_id?: string
  created_by?: string
  metadata?: TaskMetadata
}

export interface TaskBatchCreateRequest {
  tasks: TaskBatchItem[]
}

export interface TaskBatchCreateResponse {
  total: number
  successful: number
  failed: number
  tasks: TaskResponse[]
  errors: Array<{
    index: number
    title: string
    error: string
  }>
}

export interface TaskListFilters {
  project_id?: string
  session_id?: string
  status?: string
  limit?: number
  offset?: number
  sort?: string
}

// ============================================
// API Client
// ============================================

class TasksApiClient {
  private baseUrl = '/api/tasks'

  /**
   * Create a new task in DRAFT state
   * POST /api/tasks
   */
  async createTask(request: TaskCreateRequest): Promise<TaskResponse> {
    const response = await httpClient.post<TaskResponse>(this.baseUrl, request)
    return response.data
  }

  /**
   * Create and immediately start a task
   * POST /api/tasks/create_and_start
   */
  async createAndStartTask(request: TaskCreateRequest): Promise<{
    task: TaskResponse
    launched: boolean
    message: string
  }> {
    const response = await httpClient.post<{
      task: TaskResponse
      launched: boolean
      message: string
    }>(`${this.baseUrl}/create_and_start`, request)
    return response.data
  }

  /**
   * Batch create tasks
   * POST /api/tasks/batch
   */
  async createTasksBatch(request: TaskBatchCreateRequest): Promise<TaskBatchCreateResponse> {
    const response = await httpClient.post<TaskBatchCreateResponse>(`${this.baseUrl}/batch`, request)
    return response.data
  }

  /**
   * List tasks with optional filters
   * GET /api/tasks
   */
  async listTasks(filters?: TaskListFilters): Promise<TasksListResponse> {
    const response = await httpClient.get<TasksListResponse>(this.baseUrl, {
      params: filters
    })
    return response.data
  }

  /**
   * Get task details by ID
   * GET /api/tasks/{task_id}
   */
  async getTask(taskId: string): Promise<TaskResponse> {
    const response = await httpClient.get<TaskResponse>(`${this.baseUrl}/${encodeURIComponent(taskId)}`)
    return response.data
  }

  /**
   * Get task routing plan
   * GET /api/tasks/{task_id}/route
   */
  async getTaskRoute(taskId: string): Promise<any> {
    const response = await httpClient.get<any>(`${this.baseUrl}/${encodeURIComponent(taskId)}/route`)
    return response.data
  }

  /**
   * Override task routing (manual instance selection)
   * POST /api/tasks/{task_id}/route
   */
  async overrideTaskRoute(taskId: string, instanceId: string): Promise<any> {
    const response = await httpClient.post<any>(
      `${this.baseUrl}/${encodeURIComponent(taskId)}/route`,
      { instance_id: instanceId }
    )
    return response.data
  }
}

// Singleton instance
export const tasksApi = new TasksApiClient()
