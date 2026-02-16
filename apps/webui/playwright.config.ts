import { defineConfig, devices } from '@playwright/test'
import { BASE_URL } from './tests/e2e/utils/env'
import { existsSync } from 'node:fs'

// Playwright webServer runs via `bash -lc`, which may resolve `python3` to a system Python
// that does not have our deps (FastAPI/Uvicorn). Prefer a known Homebrew Python on macOS,
// with env overrides for portability.
const PYTHON_EXEC = (() => {
  const env = (process.env.OCTOPUSOS_EXEC || process.env.E2E_PYTHON_EXEC || '').trim()
  if (env) return env
  if (process.platform === 'darwin') {
    if (existsSync('/opt/homebrew/bin/python3')) return '/opt/homebrew/bin/python3'
    if (existsSync('/usr/local/bin/python3')) return '/usr/local/bin/python3'
  }
  return 'python3'
})()

/**
 * Phase 7 Playwright Configuration
 * - Trace on failure
 * - Screenshot on failure
 * - Video optional
 * - Concurrent workers
 * - Retry on failure
 */
export default defineConfig({
  testDir: './tests/e2e',

  // Maximum time one test can run
  timeout: 30 * 1000,

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Number of parallel workers
  workers: process.env.CI ? 2 : 4,
  globalSetup: './tests/e2e/global-setup.ts',

  // Reporter to use
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['json', { outputFile: 'test-results.json' }],
    ['line']
  ],

  use: {
    // Base URL for navigation
    baseURL: (process.env.CI && process.env.CI !== 'false')
      ? 'http://127.0.0.1:63567'
      : (process.env.BASE_URL || BASE_URL),

    // Collect trace on failure
    trace: 'retain-on-failure',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video recording - disabled by default, enable on demand
    video: process.env.RECORD_VIDEO === 'true' ? 'on' : 'off',

    // HAR recording for Phase 7.3.1 - capture all HTTP traffic
    // Conditionally enable HAR recording
    ...(process.env.RECORD_HAR === 'true' ? {
      recordHar: {
        path: 'gate_results/phase7.3.1/har/test.har',
        mode: 'full' as const,
        content: 'embed' as const,
      },
    } : {}),

    // Navigation timeout
    navigationTimeout: 15 * 1000,

    // Action timeout
    actionTimeout: 10 * 1000,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'webkit-smoke',
      testMatch: /specs\/webkit-smoke\.spec\.ts/,
      use: { ...devices['Desktop Safari'] },
    },
  ],

  webServer: process.env.E2E_NO_WEBSERVER
    ? undefined
    : (() => {
      const isCI = !!process.env.CI && process.env.CI !== 'false'
      const webUrl = isCI
        ? 'http://127.0.0.1:63567'
        : (process.env.BASE_URL || BASE_URL)
      const apiOrigin = isCI
        ? 'http://127.0.0.1:59117'
        : (process.env.E2E_API_ORIGIN || process.env.OCTOPUS_BACKEND_ORIGIN || 'http://127.0.0.1:59117')

      // Extract port to force a deterministic dev server port.
      const webPort = (() => {
        try {
          return new URL(webUrl).port || '63567'
        } catch {
          return '63567'
        }
      })()

      const apiPort = (() => {
        try {
          return new URL(apiOrigin).port || '59117'
        } catch {
          return '59117'
        }
      })()

      const reuse = !isCI

      return [
        {
          // Backend (compat demo mode). Keep it explicit so UI demos are deterministic.
          command: `bash -lc "lsof -tiTCP:${apiPort} -sTCP:LISTEN | xargs kill -9 >/dev/null 2>&1 || true; env OCTOPUSOS_COMPAT_DEMO=1 ${PYTHON_EXEC} -m uvicorn octopusos.webui.app:app --host 127.0.0.1 --port ${apiPort}"`,
          url: `${apiOrigin}/api/governance/trust-tiers`,
          reuseExistingServer: reuse,
          timeout: 120 * 1000,
        },
        {
          // Frontend (Vite dev server) with /api proxy to backend.
          command: `bash -lc "lsof -tiTCP:${webPort} -sTCP:LISTEN | xargs kill -9 >/dev/null 2>&1 || true; env OCTOPUS_BACKEND_ORIGIN='${apiOrigin}' OCTOPUS_PUBLIC_ORIGIN='${webUrl}' npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort"`,
          url: webUrl,
          reuseExistingServer: reuse,
          timeout: 120 * 1000,
        },
      ]
    })(),
})
