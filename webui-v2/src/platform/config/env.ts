/// <reference types="vite/client" />

/**
 * Platform Configuration - Environment Variables
 *
 * Centralized environment variable access for the platform layer.
 * All config values should be read from here, not directly from import.meta.env.
 */

interface PlatformConfig {
  /** Backend API base URL (default: http://localhost:8080) */
  apiBaseUrl: string;

  /** Request timeout in milliseconds (default: 30000) */
  apiTimeout: number;

  /** Enable mock mode for development (default: false) */
  enableMock: boolean;

  /** Enable demo mode (default: true) */
  enableDemoMode: boolean;

  /** Development server port (default: 5174) */
  devPort: number;
}

/**
 * Parse and validate environment variables
 */
function parseEnv(): PlatformConfig {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
  const apiTimeout = parseInt(import.meta.env.VITE_API_TIMEOUT || '30000', 10);
  const enableMock = import.meta.env.VITE_ENABLE_MOCK === 'true';
  const enableDemoMode = import.meta.env.VITE_ENABLE_DEMO_MODE === 'true';
  const devPort = parseInt(import.meta.env.VITE_DEV_PORT || '5174', 10);

  // Validate critical values
  if (isNaN(apiTimeout) || apiTimeout <= 0) {
    console.warn('Invalid VITE_API_TIMEOUT, using default 30000ms');
  }

  return {
    apiBaseUrl,
    apiTimeout: isNaN(apiTimeout) ? 30000 : apiTimeout,
    enableMock,
    enableDemoMode,
    devPort: isNaN(devPort) ? 5174 : devPort,
  };
}

/**
 * Platform configuration singleton
 */
export const config: PlatformConfig = parseEnv();

/**
 * Check if running in development mode
 */
export const isDev = import.meta.env.DEV;

/**
 * Check if running in production mode
 */
export const isProd = import.meta.env.PROD;

/**
 * Log configuration on initialization (dev only)
 */
if (isDev) {
  console.log('[Platform] Configuration loaded:', {
    apiBaseUrl: config.apiBaseUrl,
    apiTimeout: config.apiTimeout,
    enableMock: config.enableMock,
    enableDemoMode: config.enableDemoMode,
  });
}
