import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import './i18n' // Initialize i18n
import { initializeRuntimeConfig, assertRuntimeOriginConsistency } from '@/platform/config/runtimeConfig'

async function bootstrap() {
  await initializeRuntimeConfig()
  assertRuntimeOriginConsistency()

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <BrowserRouter
        // Desktop Product Shell serves WebUI under "/console/*".
        // Support both "/" (dev / standalone WebUI) and "/console" (embedded console).
        basename={window.location.pathname.startsWith('/console') ? '/console' : undefined}
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  )
}

void bootstrap()
