/**
 * AgentOS Module DTOs
 * Covers: Projects, Tasks, Repositories, Snapshots
 */

import type { PaginationParams } from '../common'

// ========== Projects ==========

export interface Project {
  project_id: string
  name: string
  description?: string
  status: 'active' | 'archived' | 'deleted'
  tags: string[]
  default_repo_id?: string
  default_workdir?: string
  settings?: ProjectSettings
  created_at: string
  updated_at?: string
  created_by?: string
  repos_count?: number
  recent_tasks_count?: number
}

export interface ProjectSettings {
  [key: string]: unknown
}

export interface ProjectSummary {
  project_id: string
  name: string
  description?: string
  status: string
  tags: string[]
  repo_count: number
  created_at: string
  updated_at?: string
}

export interface ProjectDetail extends ProjectSummary {
  workspace_root?: string
  default_repo_id?: string
  default_workdir?: string
  settings?: ProjectSettings
  repos: RepoSummary[]
  repos_count: number
  recent_tasks_count?: number
}

export interface ListProjectsRequest extends PaginationParams {
  search?: string
  status?: 'active' | 'archived' | 'deleted'
}

export interface ListProjectsResponse {
  projects: ProjectSummary[]
  total: number
  limit: number
  offset: number
}

export interface GetProjectResponse {
  project_id: string
  name: string
  description?: string
  status: string
  tags: string[]
  default_repo_id?: string
  default_workdir?: string
  settings?: ProjectSettings
  created_at: string
  updated_at?: string
  created_by?: string
  repos: RepoSummary[]
  repos_count: number
  recent_tasks_count?: number
}

export interface CreateProjectRequest {
  name: string
  description?: string
  tags?: string[]
  default_workdir?: string
  settings?: Record<string, unknown>
}

export interface CreateProjectResponse {
  project_id: string
  name: string
  description?: string
  status: string
  tags: string[]
  default_workdir?: string
  settings?: ProjectSettings
  created_at: string
  updated_at?: string
  repos: RepoSummary[]
  repos_count: number
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  tags?: string[]
  default_workdir?: string
  settings?: Record<string, unknown>
}

export interface UpdateProjectResponse extends GetProjectResponse {}

export interface ArchiveProjectResponse {
  message: string
  project_id: string
  status: string
}

export interface DeleteProjectResponse {
  message: string
  project_id: string
}

// ========== Repositories ==========

export interface RepoSummary {
  repo_id: string
  name: string
  remote_url?: string
  role: string
  is_writable: boolean
  workspace_relpath: string
  default_branch: string
  last_active?: string
  created_at: string
  updated_at: string
}

export interface RepoDetail extends RepoSummary {
  auth_profile?: string
  metadata: Record<string, unknown>
  task_count?: number
}

export interface ListReposRequest {
  project_id: string
  role?: string
}

export type ListReposResponse = RepoSummary[]

export interface GetRepoRequest {
  project_id: string
  repo_id: string
}

export type GetRepoResponse = RepoDetail

export interface AddRepoRequest {
  name: string
  remote_url?: string
  workspace_relpath: string
  role?: string
  is_writable?: boolean
  default_branch?: string
  auth_profile?: string
  metadata?: Record<string, unknown>
}

export type AddRepoResponse = RepoDetail

export interface UpdateRepoRequest {
  name?: string
  is_writable?: boolean
  default_branch?: string
  auth_profile?: string
  metadata?: Record<string, unknown>
}

export type UpdateRepoResponse = RepoDetail

export interface DeleteRepoResponse {
  message: string
}

// ========== Tasks ==========

export interface Task {
  task_id: string
  title: string
  status: string
  session_id: string
  project_id?: string
  created_at?: string
  updated_at?: string
  created_by?: string
  metadata: Record<string, unknown>
  spec_frozen: number
  route_plan_json?: string
  requirements_json?: string
  selected_instance_id?: string
  router_version?: string
  repo_id?: string
  workdir?: string
}

export interface TaskSummary {
  task_id: string
  title: string
  status: string
  session_id?: string
  project_id?: string
  created_at: string
  updated_at?: string
  metadata: Record<string, unknown>
}

export interface TaskCreateRequest {
  title: string
  session_id?: string
  project_id?: string
  created_by?: string
  metadata?: Record<string, unknown>
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
  metadata: Record<string, unknown>
  spec_frozen: number
  route_plan_json?: string
  requirements_json?: string
  selected_instance_id?: string
  router_version?: string
  repo_id?: string
  workdir?: string
}

export interface ListTasksRequest extends PaginationParams {
  project_id?: string
  session_id?: string
  status?: string
  sort?: string
}

export interface ListTasksResponse {
  tasks: TaskSummary[]
  total: number
  limit: number
  offset: number
}

export interface TaskBatchItem {
  title: string
  project_id?: string
  created_by?: string
  metadata?: Record<string, unknown>
}

export interface TaskBatchCreateRequest {
  tasks: TaskBatchItem[]
}

export interface TaskBatchCreateResponse {
  total: number
  successful: number
  failed: number
  tasks: Task[]
  errors: Array<{
    index: number
    title: string
    error: string
  }>
}

export interface CreateTaskAndStartRequest extends TaskCreateRequest {}

export interface CreateTaskAndStartResponse {
  task: Task
  launched: boolean
  message: string
}

// ========== Task Routing ==========

export interface RoutePlanResponse {
  task_id: string
  selected: string
  fallback: string[]
  scores: Record<string, number>
  reasons: string[]
  router_version: string
  timestamp: string
  requirements?: Record<string, unknown>
}

export interface RouteOverrideRequest {
  instance_id: string
}

// ========== Task Graph ==========

export interface TaskGraphNode {
  task_id: string
  title: string
  status: string
  repos: string[]
  created_at: string
}

export interface TaskGraphEdge {
  from: string
  to: string
  type: string
  reason?: string
}

export interface RepoInfo {
  repo_id: string
  name: string
  role: string
  color: string
}

export interface TaskGraphResponse {
  project_id: string
  nodes: TaskGraphNode[]
  edges: TaskGraphEdge[]
  repos: RepoInfo[]
}

// ========== Repository Tasks ==========

export interface TaskSummaryForRepo {
  task_id: string
  title: string
  status: string
  created_at: string
  files_changed: number
  lines_added: number
  lines_deleted: number
  commit_hash?: string
}

export interface GetRepoTasksRequest extends PaginationParams {
  project_id: string
  repo_id: string
}

export type GetRepoTasksResponse = TaskSummaryForRepo[]

// ========== Snapshots ==========

export interface SnapshotRepo {
  repo_id: string
  name: string
  remote_url?: string
  workspace_relpath: string
  role: string
  commit_hash?: string
}

export interface SnapshotTasksSummary {
  total: number
  completed: number
  failed: number
  running: number
}

export interface ProjectSnapshot {
  snapshot_id: string
  timestamp: string
  project: Record<string, unknown>
  repos: SnapshotRepo[]
  tasks_summary: SnapshotTasksSummary
  settings_hash: string
  metadata: Record<string, unknown>
}

export interface CreateSnapshotResponse extends ProjectSnapshot {}

export interface ListSnapshotsRequest extends PaginationParams {
  project_id: string
}

export interface SnapshotSummary {
  snapshot_id: string
  created_at: string
}

export interface ListSnapshotsResponse {
  snapshots: SnapshotSummary[]
  total: number
}

export interface GetSnapshotResponse extends ProjectSnapshot {}
