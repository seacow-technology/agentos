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
import { ClientError } from './errors';

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

function ensureNonHtmlResponse<T>(response: AxiosResponse<T>): void {
  const responseType = response.config.responseType;
  const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
  const isJsonMode = !responseType || responseType === 'json';
  const looksLikeHtmlString =
    typeof response.data === 'string' &&
    /^\s*<!doctype html|^\s*<html/i.test(response.data);

  if (isJsonMode && (contentType.includes('text/html') || looksLikeHtmlString)) {
    throw new ClientError('Non-JSON response received from API endpoint', response.status, {
      contentType,
      preview: String(response.data).slice(0, 200),
      url: response.config.url,
    });
  }
}

/**
 * Type-safe GET request wrapper
 */
export async function get<T = unknown>(
  url: string,
  config?: AxiosRequestConfig
): Promise<T> {
  const response: AxiosResponse<T> = await httpClient.get(url, config);
  ensureNonHtmlResponse(response);
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
  ensureNonHtmlResponse(response);
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
  ensureNonHtmlResponse(response);
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
  ensureNonHtmlResponse(response);
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
  ensureNonHtmlResponse(response);
  return response.data;
}

/**
 * Re-export for convenience
 */
export { httpClient as default };
