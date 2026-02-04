/**
 * Common pagination types
 */

export interface PaginationParams {
  page?: number
  limit?: number
  offset?: number
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  limit: number
  offset: number
  hasMore?: boolean
}

/**
 * Sort order parameters
 */
export interface SortParams {
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

/**
 * Combined pagination and sorting
 */
export type PaginationWithSortParams = PaginationParams & SortParams
