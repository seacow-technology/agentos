/// <reference types="vite/client" />

/**
 * Platform HTTP Layer - Axios Interceptors
 *
 * Request and response interceptors for unified behavior:
 * - Auto-inject auth tokens
 * - Unified error handling and transformation
 * - Logging and monitoring hooks
 */

import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
import { getAuthHeader } from '@platform/auth/adminToken';
import {
  ApiError,
  NetworkError,
  AuthError,
  ServerError,
  ValidationError,
  ClientError,
  TimeoutError,
} from './errors';

/**
 * Get CSRF token from cookie
 */
function getCSRFToken(): string | null {
  const name = 'csrf_token=';
  const decodedCookie = decodeURIComponent(document.cookie);
  const cookies = decodedCookie.split(';');

  for (let i = 0; i < cookies.length; i++) {
    let cookie = cookies[i].trim();
    if (cookie.indexOf(name) === 0) {
      return cookie.substring(name.length, cookie.length);
    }
  }

  return null;
}

/**
 * Check if method requires CSRF protection
 */
function requiresCSRFProtection(method?: string): boolean {
  if (!method) return false;
  const protectedMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
  return protectedMethods.includes(method.toUpperCase());
}

/**
 * Install request interceptor
 * Adds authentication headers, CSRF token, and logging
 */
export function installRequestInterceptor(axiosInstance: AxiosInstance): void {
  axiosInstance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      // Auto-inject authorization header if token exists
      const authHeader = getAuthHeader();
      if (authHeader && !config.headers.Authorization) {
        config.headers.Authorization = authHeader;
      }

      // Auto-inject CSRF token for state-changing requests
      if (requiresCSRFProtection(config.method)) {
        const csrfToken = getCSRFToken();
        if (csrfToken && !config.headers['X-CSRF-Token']) {
          config.headers['X-CSRF-Token'] = csrfToken;
          if (import.meta.env.DEV) {
            // console.log('[Platform/HTTP] 🔐 CSRF token injected:', csrfToken.substring(0, 8) + '...');
          }
        } else if (!csrfToken) {
          console.warn('[Platform/HTTP] No CSRF token found in cookie. Request may fail.');
        }
      }

      // Log request in development mode
      if (import.meta.env.DEV) {
        // console.log('[Platform/HTTP] Request:', {
        //   method: config.method?.toUpperCase(),
        //   url: config.url,
        //   hasAuth: !!authHeader,
        //   hasCSRF: !!getCSRFToken(),
        // });
      }

      return config;
    },
    (error: AxiosError) => {
      console.error('[Platform/HTTP] Request interceptor error:', error);
      return Promise.reject(error);
    }
  );
}

/**
 * Install response interceptor
 * Handles success responses and transforms errors
 */
export function installResponseInterceptor(axiosInstance: AxiosInstance): void {
  axiosInstance.interceptors.response.use(
    // Success handler - return data directly
    (response: AxiosResponse) => {
      if (import.meta.env.DEV) {
        const logData: any = {
          status: response.status,
          url: response.config.url,
        };

        // 🔍 Log response data for non-2xx responses (especially 403 CSRF errors)
        if (response.status >= 400) {
          logData.responseData = response.data;
        }

        // console.log('[Platform/HTTP] Response:', logData);
      }
      return response;
    },

    // Error handler - transform to unified error types
    (error: AxiosError) => {
      const transformedError = transformError(error);

      if (import.meta.env.DEV) {
        console.error('[Platform/HTTP] Response error:', {
          type: transformedError.name,
          code: transformedError.code,
          status: transformedError.status,
          message: transformedError.message,
          // 🔍 Include response data for debugging (especially CSRF errors)
          responseData: error.response?.data,
        });
      }

      return Promise.reject(transformedError);
    }
  );
}

/**
 * Transform Axios errors to unified ApiError types
 */
function transformError(error: AxiosError): ApiError {
  // Network errors (no response received)
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      return new TimeoutError('Request timeout - server did not respond in time', {
        originalError: error.message,
      });
    }

    return new NetworkError('Network error - unable to reach server', {
      originalError: error.message,
      code: error.code,
    });
  }

  // Server responded with error status
  const { status, data } = error.response;
  const message = extractErrorMessage(data);

  // Authentication errors (401, 403)
  if (status === 401 || status === 403) {
    // TODO: Trigger logout/redirect in future iteration
    console.warn('[Platform/HTTP] Auth error - user may need to re-authenticate');
    return new AuthError(message || 'Authentication required', status, data);
  }

  // Validation errors (400, 422)
  if (status === 400 || status === 422) {
    return new ValidationError(message || 'Invalid request data', status, data);
  }

  // Other client errors (4xx)
  if (status >= 400 && status < 500) {
    return new ClientError(message || `Client error (${status})`, status, data);
  }

  // Server errors (5xx)
  if (status >= 500) {
    return new ServerError(message || `Server error (${status})`, status, data);
  }

  // Fallback for unexpected status codes
  return new ApiError(message || 'Unknown error occurred', 'UNKNOWN_ERROR', status, data);
}

/**
 * Extract error message from response data
 */
function extractErrorMessage(data: unknown): string | undefined {
  if (!data) return undefined;

  // Try common error message fields
  if (typeof data === 'object' && data !== null) {
    const obj = data as Record<string, unknown>;

    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.error === 'string') return obj.error;
    if (typeof obj.detail === 'string') return obj.detail;

    // Handle nested error objects
    if (obj.error && typeof obj.error === 'object') {
      const nested = obj.error as Record<string, unknown>;
      if (typeof nested.message === 'string') return nested.message;
    }
  }

  // Fallback to string representation
  if (typeof data === 'string') return data;

  return undefined;
}
