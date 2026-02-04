/**
 * Platform HTTP Layer - Public API
 *
 * Export all public HTTP utilities and types.
 */

// HTTP Client
export { httpClient, get, post, put, patch, del } from './httpClient';
export { httpClient as default } from './httpClient';

// Error Types
export {
  ApiError,
  NetworkError,
  AuthError,
  ServerError,
  ValidationError,
  ClientError,
  TimeoutError,
} from './errors';

// Re-export Axios types for convenience
export type { AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
