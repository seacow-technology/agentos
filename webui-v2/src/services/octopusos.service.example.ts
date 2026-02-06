/**
 * Example: How to extend generated service code
 *
 * This file demonstrates the recommended pattern for extending
 * auto-generated service functions with custom business logic.
 */

import { agentosServiceGen } from './agentos.service.gen'
import type * as DTO from '@modules/agentos'

/**
 * Extended AgentOS service with custom functions
 *
 * Pattern: Import generated service and spread it, then add extensions
 */
export const agentosService = {
  // Re-export all generated functions
  ...agentosServiceGen,

  // ========================================================================
  // Custom Extensions
  // ========================================================================

  /**
   * List only active projects
   * Wrapper around listProjects with preset filter
   */
  async listActiveProjects(
    params?: Omit<DTO.ListProjectsRequest, 'status'>
  ): Promise<DTO.ListProjectsResponse> {
    return agentosServiceGen.listProjects({
      ...params,
      status: 'active'
    })
  },

  /**
   * List archived projects
   */
  async listArchivedProjects(
    params?: Omit<DTO.ListProjectsRequest, 'status'>
  ): Promise<DTO.ListProjectsResponse> {
    return agentosServiceGen.listProjects({
      ...params,
      status: 'archived'
    })
  },

  /**
   * Get project with additional metrics
   * Combines multiple API calls
   */
  async getProjectWithMetrics(id: string) {
    const project = await agentosServiceGen.getProject(id)

    // Example: fetch additional data
    // const tasks = await agentosServiceGen.listTasks({ project_id: id })
    // const activeTasksCount = tasks.tasks.filter(t => t.status === 'active').length

    return {
      ...project,
      // metrics: { activeTasksCount }
    }
  },

  /**
   * Batch create projects
   * Custom operation not in base API
   */
  async batchCreateProjects(
    projects: DTO.CreateProjectRequest[]
  ): Promise<DTO.CreateProjectResponse[]> {
    return Promise.all(
      projects.map(project => agentosServiceGen.createProject(project))
    )
  }
}

// ============================================================================
// Alternative Pattern: Decorator/Wrapper
// ============================================================================

/**
 * Example: Add logging/monitoring to all service calls
 */
export function withLogging<T extends Record<string, any>>(service: T): T {
  return new Proxy(service, {
    get(target, prop) {
      const original = target[prop as keyof T]
      if (typeof original === 'function') {
        return async (...args: any[]) => {
          console.log(`[Service] Calling ${String(prop)}`, args)
          const start = Date.now()
          try {
            const result = await original.apply(target, args)
            console.log(`[Service] ${String(prop)} completed in ${Date.now() - start}ms`)
            return result
          } catch (error) {
            console.error(`[Service] ${String(prop)} failed`, error)
            throw error
          }
        }
      }
      return original
    }
  })
}

// Usage:
// export const agentosService = withLogging(agentosServiceGen)

// ============================================================================
// Alternative Pattern: Class-based Extension
// ============================================================================

/**
 * Example: OOP-style service extension
 */
export class AgentosService {
  // Delegate to generated service
  private base = agentosServiceGen

  // Re-export methods
  listProjects = this.base.listProjects.bind(this.base)
  getProject = this.base.getProject.bind(this.base)
  createProject = this.base.createProject.bind(this.base)
  updateProject = this.base.updateProject.bind(this.base)
  deleteProject = this.base.deleteProject.bind(this.base)

  // Add state
  private cache = new Map<string, any>()

  // Add custom methods
  async getProjectCached(id: string) {
    if (this.cache.has(id)) {
      return this.cache.get(id)
    }
    const project = await this.base.getProject(id)
    this.cache.set(id, project)
    return project
  }

  clearCache() {
    this.cache.clear()
  }
}

// Usage:
// export const agentosService = new AgentosService()
