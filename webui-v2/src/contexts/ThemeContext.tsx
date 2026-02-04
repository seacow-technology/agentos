/**
 * ThemeContext - Theme Mode Management
 *
 * Provides theme mode (light/dark) state and controls across the app
 */

import React, { createContext, useContext, useState, useEffect, useMemo } from 'react'
import { ThemeProvider as MuiThemeProvider } from '@mui/material'
import {
  lightTheme,
  darkTheme,
  githubTheme,
  googleTheme,
  macosTheme,
  draculaTheme,
  nordTheme,
  monokaiTheme,
} from '@/ui/theme/theme'

type ThemeMode = 'light' | 'dark' | 'github' | 'google' | 'macos' | 'dracula' | 'nord' | 'monokai'

interface ThemeContextValue {
  mode: ThemeMode
  toggleTheme: () => void
  setTheme: (mode: ThemeMode) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

export function useThemeMode() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useThemeMode must be used within ThemeProvider')
  }
  return context
}

interface ThemeProviderProps {
  children: React.ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  // Load initial theme from localStorage or default to 'light'
  const [mode, setMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('theme-mode')
    const validThemes: ThemeMode[] = ['light', 'dark', 'github', 'google', 'macos', 'dracula', 'nord', 'monokai']
    if (saved && validThemes.includes(saved as ThemeMode)) {
      return saved as ThemeMode
    }
    return 'light'
  })

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('theme-mode', mode)
    // Add transition class to document for smooth theme changes
    document.documentElement.classList.add('theme-transitioning')

    const timer = setTimeout(() => {
      document.documentElement.classList.remove('theme-transitioning')
    }, 300)

    return () => clearTimeout(timer)
  }, [mode])

  const toggleTheme = () => {
    setMode((prev) => {
      // Cycle through: light → dark → github → light
      if (prev === 'light') return 'dark'
      if (prev === 'dark') return 'github'
      return 'light'
    })
  }

  const setTheme = (newMode: ThemeMode) => {
    setMode(newMode)
  }

  const theme = useMemo(() => {
    const themeMap: Record<ThemeMode, any> = {
      light: lightTheme,
      dark: darkTheme,
      github: githubTheme,
      google: googleTheme,
      macos: macosTheme,
      dracula: draculaTheme,
      nord: nordTheme,
      monokai: monokaiTheme,
    }
    return themeMap[mode]
  }, [mode])

  const value = useMemo(
    () => ({
      mode,
      toggleTheme,
      setTheme,
    }),
    [mode]
  )

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>{children}</MuiThemeProvider>
    </ThemeContext.Provider>
  )
}
