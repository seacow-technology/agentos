/**
 * Platform HTTP Layer - Unified HTTP Client
 *
 * Singleton Axios instance with pre-configured:
 * - Base URL and timeout
 * - Request/response interceptors
 * - Auth token injection
 * - Unified error handling
 *
 * All API calls MUST go through this client.
 * DO NOT use axios or fetch directly in UI or service layers.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { config } from '@platform/config/env';
import { installRequestInterceptor, installResponseInterceptor } from './interceptors';

/**
 * Create and configure the Axios instance
 */
function createHttpClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: config.apiBaseUrl,
    timeout: config.apiTimeout,
    // ✅ Enable credentials (cookies, auth headers) for cross-origin requests
    // Required for session cookies and CSRF tokens
    withCredentials: true,
    headers: {
      'Content-Type': 'application/json',
    },
    // Don't throw on non-2xx status codes, let interceptor handle it
    validateStatus: () => true,
  });

  // Install interceptors
  installRequestInterceptor(instance);
  installResponseInterceptor(instance);

  return instance;
}

/**
 * Singleton HTTP client instance
 */
export const httpClient: AxiosInstance = createHttpClient();

/**
 * Type-safe GET request wrapper
 */
export async function get<T = unknown>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.get(url, config);
  return response.data;
}

/**
 * Type-safe POST request wrapper
 */
export async function post<T = unknown, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.post(url, data, config);
  return response.data;
}

/**
 * Type-safe PUT request wrapper
 */
export async function put<T = unknown, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.put(url, data, config);
  return response.data;
}

/**
 * Type-safe PATCH request wrapper
 */
export async function patch<T = unknown, D = unknown>(
  url: string,
  data?: D,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.patch(url, data, config);
  return response.data;
}

/**
 * Type-safe DELETE request wrapper
 */
export async function del<T = unknown>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.delete(url, config);
  return response.data;
}

/**
 * Re-export for convenience
 */
export { httpClient as default };
