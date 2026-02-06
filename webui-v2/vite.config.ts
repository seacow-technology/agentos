import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'

const VERSION_FILE = path.resolve(__dirname, '..', '..', 'VERSION')
const releaseVersion = fs.readFileSync(VERSION_FILE, 'utf-8').trim() || '0.0'
const buildVersion = releaseVersion
const productName = 'AgentOS'
const webuiName = 'AgentOS WebUI'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_PRODUCT_NAME__: JSON.stringify(productName),
    __APP_WEBUI_NAME__: JSON.stringify(webuiName),
    __APP_RELEASE_VERSION__: JSON.stringify(releaseVersion),
    __APP_BUILD_VERSION__: JSON.stringify(buildVersion),
  },

  // Fixed port for v2
  server: {
    port: 5174,
    strictPort: true,
    host: true,
    open: false,
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
          'vendor': ['react', 'react-dom', 'react-router-dom'],
          'mui': ['@mui/material', '@mui/icons-material'],
        },
      },
    },
  },
})
