import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const VERSION_FILE = path.resolve(__dirname, '..', '..', 'VERSION')
const releaseVersion = (() => {
  try {
    if (!fs.existsSync(VERSION_FILE)) return '0.0'
    return fs.readFileSync(VERSION_FILE, 'utf-8').trim() || '0.0'
  } catch {
    return '0.0'
  }
})()
const buildVersion = releaseVersion
const productName = 'OctopusOS'
const webuiName = 'OctopusOS WebUI'
const backendOrigin = (process.env.OCTOPUS_BACKEND_ORIGIN || '').trim()
const publicOrigin = (process.env.OCTOPUS_PUBLIC_ORIGIN || '').trim()

function resolvePortFromOrigin(origin: string): number | undefined {
  if (!origin) return undefined
  try {
    const parsed = new URL(origin)
    if (!parsed.port) return undefined
    const port = Number(parsed.port)
    return Number.isFinite(port) ? port : undefined
  } catch {
    return undefined
  }
}

const explicitPort = resolvePortFromOrigin(publicOrigin)
const proxyConfig = backendOrigin
  ? {
      '/api': {
        target: backendOrigin,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: backendOrigin,
        ws: true,
        changeOrigin: true,
        secure: false,
      },
    }
  : undefined

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_PRODUCT_NAME__: JSON.stringify(productName),
    __APP_WEBUI_NAME__: JSON.stringify(webuiName),
    __APP_RELEASE_VERSION__: JSON.stringify(releaseVersion),
    __APP_BUILD_VERSION__: JSON.stringify(buildVersion),
  },

  // Runtime port/proxy comes from origin env, not hardcoded ports.
  server: {
    port: explicitPort,
    strictPort: false,
    host: true,
    open: false,
    proxy: proxyConfig,
  },

  // Path aliases
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@layouts': path.resolve(__dirname, './src/layouts'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@services': path.resolve(__dirname, './src/services'),
      '@platform': path.resolve(__dirname, './src/platform'),
      '@modules': path.resolve(__dirname, './src/modules'),
    },
  },

  // Build output
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'ui-text': [path.resolve(__dirname, './src/ui/text/index.ts')],
          vendor: ['react', 'react-dom', 'react-router-dom'],
          'mui-core': ['@mui/material'],
          'mui-icons': ['@mui/icons-material'],
          'mui-x': ['@mui/x-data-grid'],
          emotion: ['@emotion/react', '@emotion/styled'],
          charts: ['recharts'],
          markdown: ['react-markdown', 'remark-gfm', 'rehype-raw'],
          i18n: ['i18next', 'react-i18next'],
          virtualized: ['react-virtuoso'],
        },
      },
    },
  },
})
