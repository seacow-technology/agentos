/**
 * Platform Auth Layer - Admin Token Management
 *
 * Manages Admin Token storage and retrieval.
 * Uses localStorage for persistence across sessions.
 *
 * Note: This is a minimal implementation. Token refresh logic
 * and advanced auth flows will be added in future iterations.
 */

const TOKEN_STORAGE_KEY = 'agentos_admin_token';

/**
 * Get the current admin token from storage
 * @returns The token string or null if not present
 */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch (error) {
    console.error('[Platform/Auth] Failed to get token:', error);
    return null;
  }
}

/**
 * Save admin token to storage
 * @param token - The token string to save
 */
export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    console.log('[Platform/Auth] Token saved successfully');
  } catch (error) {
    console.error('[Platform/Auth] Failed to set token:', error);
    throw new Error('Failed to save authentication token');
  }
}

/**
 * Clear admin token from storage
 */
export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    console.log('[Platform/Auth] Token cleared');
  } catch (error) {
    console.error('[Platform/Auth] Failed to clear token:', error);
  }
}

/**
 * Check if user has a valid token
 * Note: This only checks presence, not validity.
 * Token validation happens on the backend.
 *
 * @returns true if token exists, false otherwise
 */
export function hasToken(): boolean {
  const token = getToken();
  return token !== null && token.length > 0;
}

/**
 * Get authorization header value
 * @returns Authorization header string or null if no token
 */
export function getAuthHeader(): string | null {
  const token = getToken();
  return token ? `Bearer ${token}` : null;
}
