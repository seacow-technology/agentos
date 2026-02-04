/**
 * AgentOS Semantic Tokens - Surface Layering System
 *
 * 🎯 Purpose: Define semantic surface layers for dark/light modes
 *
 * Key Insight: Dark mode isn't "more black", it's "more structured".
 * Light mode relies on shadows for depth, dark mode relies on surface brightness gradients.
 *
 * Layer Hierarchy (from back to front):
 * 1. canvas   - Page background (deepest)
 * 2. surface  - Scrollable content area
 * 3. paper    - Cards, panels (primary structural element)
 * 4. section  - Nested containers inside cards (density control)
 * 5. elevated - Important cards, dialogs, popovers (highest)
 */

export const agentosTokens = {
  /**
   * Light Mode Surfaces
   * Strategy: Mirror dark mode logic - layered brightness with clear contrast
   *
   * Layer Hierarchy (matching dark mode structure):
   * canvas (lightest base) → surface → paper (main content) → elevated (highest importance)
   * Each layer has clear visual distinction
   */
  light: {
    bg: {
      canvas: '#F5F7FA',           // Soft blue-gray (page background, base layer)
      surface: '#FAFBFC',          // Very light gray (scrollable area, slightly elevated)
      paper: '#FFFFFF',            // Pure white (cards, primary content - most important)
      section: '#F9FAFB',          // Off-white (nested containers, slight depth)
      elevated: '#FFFFFF',         // Pure white (dialogs, popovers - use shadow for distinction)
      overlayScrim: 'rgba(0,0,0,0.32)', // Dialog backdrop
    },
    border: {
      subtle: 'rgba(0,0,0,0.12)',  // Card borders (increased from 0.08 for clarity)
      strong: 'rgba(0,0,0,0.20)',  // Hover/active borders (increased from 0.12)
    },
    text: {
      primary: '#1C1B1F',          // MD3 On Surface (high contrast)
      secondary: '#49454F',        // MD3 On Surface Variant (medium contrast)
      tertiary: 'rgba(28,27,31,0.60)', // Lower emphasis
      disabled: 'rgba(28,27,31,0.38)', // Disabled state
    },
    divider: 'rgba(0,0,0,0.12)',   // Divider lines (increased from 0.12)
  },

  /**
   * Dark Mode Surfaces
   * Strategy: Brightness gradients for structure, borders instead of shadows
   *
   * Color Philosophy:
   * - Base is deep blue-black (#0B0F14), not pure black
   * - Each layer is slightly lighter (not darker!)
   * - Borders use white alpha (rgba(255,255,255,0.x))
   * - Dividers are "light lines", not "dark lines"
   */
  dark: {
    bg: {
      canvas: '#0B0F14',           // Deep blue-black page background
      surface: '#0E141B',          // Slightly lighter scrollable area
      paper: '#121A23',            // Card background (main structural layer)
      section: '#0F1720',          // Nested containers (between surface and paper)
      elevated: '#162233',         // Important cards, dialogs (brightest)
      overlayScrim: 'rgba(0,0,0,0.55)', // Dialog backdrop
    },
    border: {
      subtle: 'rgba(255,255,255,0.06)',  // Default card borders
      strong: 'rgba(255,255,255,0.10)',  // Hover/active borders
    },
    text: {
      primary: 'rgba(255,255,255,0.92)',   // High contrast text
      secondary: 'rgba(255,255,255,0.68)', // Medium contrast
      tertiary: 'rgba(255,255,255,0.48)',  // Low contrast
      disabled: 'rgba(255,255,255,0.32)',  // Disabled state
    },
    divider: 'rgba(255,255,255,0.08)', // Light divider lines (not dark!)
  },

  /**
   * Status Colors (Semantic)
   * Dark mode uses desaturated + brighter versions
   */
  status: {
    light: {
      success: '#2E7D32',          // Green
      warning: '#E65100',          // Orange
      error: '#B3261E',            // Red
      info: '#2196F3',             // Blue
    },
    dark: {
      success: '#34D399',          // Desaturated green
      warning: '#FBBF24',          // Desaturated amber
      error: '#FB7185',            // Desaturated red
      info: '#60A5FA',             // Desaturated blue
    },
  },

  /**
   * Status Background Colors (for Chips, badges)
   * Alpha overlays on background
   */
  statusBg: {
    light: {
      success: 'rgba(46,125,50,0.10)',
      warning: 'rgba(230,81,0,0.10)',
      error: 'rgba(179,38,30,0.10)',
      info: 'rgba(33,150,243,0.10)',
    },
    dark: {
      success: 'rgba(52,211,153,0.12)',
      warning: 'rgba(251,191,36,0.14)',
      error: 'rgba(251,113,133,0.14)',
      info: 'rgba(96,165,250,0.12)',
    },
  },

  /**
   * Elevation Strategy
   * Light: Enhanced box-shadow for clear depth perception (matching dark mode's structural clarity)
   * Dark: border + subtle inner highlight (no shadow)
   */
  elevation: {
    light: {
      none: 'none',
      soft: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',     // Subtle card shadow
      medium: '0 4px 6px rgba(0,0,0,0.12), 0 2px 4px rgba(0,0,0,0.08)',   // Moderate elevation
      high: '0 10px 15px rgba(0,0,0,0.16), 0 4px 6px rgba(0,0,0,0.10)',  // Dialog/modal shadow
    },
    dark: {
      none: 'none',
      // Dark mode doesn't use box-shadow, relies on borders + highlight
      soft: 'none',
      medium: 'none',
      high: 'none',
    },
  },

  /**
   * Surface Highlight (Dark mode only)
   * Subtle inner glow at top of cards to simulate light source
   */
  surfaceHighlight: {
    dark: 'inset 0 1px 0 rgba(255,255,255,0.04)',
  },

  /**
   * GitHub Theme (Light)
   * Strategy: Clean, professional, high-contrast design
   * Inspired by GitHub's interface design
   */
  github: {
    bg: {
      canvas: '#F6F8FA',           // Light gray (page background, sidebar)
      surface: '#FFFFFF',          // Pure white (main content area)
      paper: '#FFFFFF',            // Pure white (cards, primary content)
      section: '#F6F8FA',          // Light gray (nested containers)
      elevated: '#FFFFFF',         // Pure white (dialogs, use shadow)
      overlayScrim: 'rgba(0,0,0,0.28)', // Dialog backdrop
    },
    border: {
      subtle: '#D0D7DE',           // Medium gray border
      strong: '#8C959F',           // Darker gray for hover/active
    },
    text: {
      primary: '#24292F',          // Dark gray (high contrast)
      secondary: '#57606A',        // Medium gray
      tertiary: '#6E7781',         // Light gray
      disabled: '#8C959F',         // Disabled state
    },
    divider: '#D0D7DE',            // Medium gray divider
    status: {
      success: '#1A7F37',          // GitHub green
      warning: '#BF8700',          // GitHub orange
      error: '#CF222E',            // GitHub red
      info: '#0969DA',             // GitHub blue
    },
    statusBg: {
      success: 'rgba(26,127,55,0.10)',
      warning: 'rgba(191,135,0,0.10)',
      error: 'rgba(207,34,46,0.10)',
      info: 'rgba(9,105,218,0.10)',
    },
    elevation: {
      none: 'none',
      soft: '0 1px 0 rgba(27,31,36,0.04), 0 0 0 1px rgba(27,31,36,0.04)',     // Subtle shadow
      medium: '0 3px 6px rgba(140,149,159,0.15)',   // Medium shadow
      high: '0 8px 24px rgba(140,149,159,0.20)',    // Dialog shadow
    },
    brand: {
      primary: '#0969DA',          // GitHub blue
      primaryDark: '#0550AE',      // Darker blue for hover
      primaryLight: '#218BFF',     // Lighter blue for active
    },
  },

  /**
   * Google Material Theme (Light)
   * Strategy: Bright, colorful, Material Design
   * Inspired by Google's Material Design
   */
  google: {
    bg: {
      canvas: '#F1F3F4',           // Light gray (Google gray 100)
      surface: '#FFFFFF',          // Pure white
      paper: '#FFFFFF',            // Pure white
      section: '#F8F9FA',          // Very light gray
      elevated: '#FFFFFF',         // Pure white
      overlayScrim: 'rgba(0,0,0,0.32)',
    },
    border: {
      subtle: '#DADCE0',           // Google gray 300
      strong: '#BDC1C6',           // Google gray 400
    },
    text: {
      primary: '#202124',          // Google gray 900
      secondary: '#5F6368',        // Google gray 700
      tertiary: '#80868B',         // Google gray 600
      disabled: '#9AA0A6',         // Google gray 500
    },
    divider: '#E8EAED',            // Google gray 200
    status: {
      success: '#1E8E3E',          // Google green
      warning: '#F9AB00',          // Google yellow
      error: '#D93025',            // Google red
      info: '#1A73E8',             // Google blue
    },
    statusBg: {
      success: 'rgba(30,142,62,0.10)',
      warning: 'rgba(249,171,0,0.10)',
      error: 'rgba(217,48,37,0.10)',
      info: 'rgba(26,115,232,0.10)',
    },
    elevation: {
      none: 'none',
      soft: '0 1px 2px 0 rgba(60,64,67,0.30), 0 1px 3px 1px rgba(60,64,67,0.15)',
      medium: '0 1px 3px 0 rgba(60,64,67,0.30), 0 4px 8px 3px rgba(60,64,67,0.15)',
      high: '0 8px 12px 6px rgba(60,64,67,0.15), 0 4px 4px 0 rgba(60,64,67,0.30)',
    },
    brand: {
      primary: '#1A73E8',          // Google blue
      primaryDark: '#1557B0',      // Darker
      primaryLight: '#4285F4',     // Lighter (classic Google blue)
    },
  },

  /**
   * macOS Theme (Light)
   * Strategy: Clean, minimal, Apple-style
   * Inspired by macOS Big Sur/Monterey
   */
  macos: {
    bg: {
      canvas: '#F5F5F7',           // Apple light gray
      surface: '#FFFFFF',          // Pure white
      paper: '#FFFFFF',            // Pure white
      section: '#FAFAFA',          // Very light gray
      elevated: '#FFFFFF',         // Pure white
      overlayScrim: 'rgba(0,0,0,0.30)',
    },
    border: {
      subtle: '#D2D2D7',           // Apple divider
      strong: '#AEAEB2',           // Darker gray
    },
    text: {
      primary: '#1D1D1F',          // Apple black
      secondary: '#6E6E73',        // Apple gray
      tertiary: '#86868B',         // Lighter gray
      disabled: '#C7C7CC',         // Very light gray
    },
    divider: '#E5E5EA',            // Apple light divider
    status: {
      success: '#34C759',          // Apple green
      warning: '#FF9500',          // Apple orange
      error: '#FF3B30',            // Apple red
      info: '#007AFF',             // Apple blue
    },
    statusBg: {
      success: 'rgba(52,199,89,0.10)',
      warning: 'rgba(255,149,0,0.10)',
      error: 'rgba(255,59,48,0.10)',
      info: 'rgba(0,122,255,0.10)',
    },
    elevation: {
      none: 'none',
      soft: '0 2px 8px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
      medium: '0 4px 16px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)',
      high: '0 8px 32px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.06)',
    },
    brand: {
      primary: '#007AFF',          // Apple blue
      primaryDark: '#0051D5',      // Darker
      primaryLight: '#409CFF',     // Lighter
    },
  },

  /**
   * Dracula Theme (Dark)
   * Strategy: Purple-dominated dark theme
   * Popular among developers
   */
  dracula: {
    bg: {
      canvas: '#1E1F29',           // Darker background
      surface: '#21222C',          // Dark gray
      paper: '#282A36',            // Dracula background
      section: '#242530',          // Between surface and paper
      elevated: '#2F3241',         // Elevated surface
      overlayScrim: 'rgba(0,0,0,0.60)',
    },
    border: {
      subtle: 'rgba(189,147,249,0.12)',  // Purple tint
      strong: 'rgba(189,147,249,0.20)',
    },
    text: {
      primary: '#F8F8F2',          // Dracula foreground
      secondary: '#A0A0A0',        // Gray
      tertiary: '#6E6C7E',         // Comment gray
      disabled: 'rgba(248,248,242,0.38)',
    },
    divider: 'rgba(189,147,249,0.12)',
    status: {
      success: '#50FA7B',          // Dracula green
      warning: '#FFB86C',          // Dracula orange
      error: '#FF5555',            // Dracula red
      info: '#8BE9FD',             // Dracula cyan
    },
    statusBg: {
      success: 'rgba(80,250,123,0.12)',
      warning: 'rgba(255,184,108,0.12)',
      error: 'rgba(255,85,85,0.12)',
      info: 'rgba(139,233,253,0.12)',
    },
    elevation: {
      none: 'none',
      soft: 'none',
      medium: 'none',
      high: 'none',
    },
    brand: {
      primary: '#BD93F9',          // Dracula purple
      primaryDark: '#9B6FE5',      // Darker purple
      primaryLight: '#D5B3FF',     // Lighter purple
    },
  },

  /**
   * Nord Theme (Dark)
   * Strategy: Cool, arctic-inspired dark theme
   * Popular Nordic color palette
   */
  nord: {
    bg: {
      canvas: '#242933',           // Nord polar night 0
      surface: '#2E3440',          // Nord polar night 1
      paper: '#3B4252',            // Nord polar night 2
      section: '#343A48',          // Between surface and paper
      elevated: '#434C5E',         // Nord polar night 3
      overlayScrim: 'rgba(0,0,0,0.55)',
    },
    border: {
      subtle: 'rgba(136,192,208,0.12)',  // Nord frost tint
      strong: 'rgba(136,192,208,0.20)',
    },
    text: {
      primary: '#ECEFF4',          // Nord snow storm 3
      secondary: '#D8DEE9',        // Nord snow storm 1
      tertiary: '#A6AEBF',         // Muted
      disabled: 'rgba(236,239,244,0.38)',
    },
    divider: 'rgba(136,192,208,0.10)',
    status: {
      success: '#A3BE8C',          // Nord aurora green
      warning: '#EBCB8B',          // Nord aurora yellow
      error: '#BF616A',            // Nord aurora red
      info: '#88C0D0',             // Nord frost cyan
    },
    statusBg: {
      success: 'rgba(163,190,140,0.12)',
      warning: 'rgba(235,203,139,0.12)',
      error: 'rgba(191,97,106,0.12)',
      info: 'rgba(136,192,208,0.12)',
    },
    elevation: {
      none: 'none',
      soft: 'none',
      medium: 'none',
      high: 'none',
    },
    brand: {
      primary: '#88C0D0',          // Nord frost cyan
      primaryDark: '#6FA8B8',      // Darker
      primaryLight: '#A5D4E0',     // Lighter
    },
  },

  /**
   * Monokai Theme (Dark)
   * Strategy: Classic code editor theme
   * Warm colors on dark background
   */
  monokai: {
    bg: {
      canvas: '#1E1E1E',           // Darker background
      surface: '#1F1F1F',          // Slightly lighter
      paper: '#272822',            // Monokai background
      section: '#232318',          // Between surface and paper
      elevated: '#2F2F2A',         // Elevated
      overlayScrim: 'rgba(0,0,0,0.60)',
    },
    border: {
      subtle: 'rgba(166,226,46,0.12)',   // Green tint
      strong: 'rgba(166,226,46,0.20)',
    },
    text: {
      primary: '#F8F8F2',          // Monokai foreground
      secondary: '#CFCFC2',        // Lighter gray
      tertiary: '#75715E',         // Comment gray
      disabled: 'rgba(248,248,242,0.38)',
    },
    divider: 'rgba(166,226,46,0.10)',
    status: {
      success: '#A6E22E',          // Monokai green
      warning: '#E6DB74',          // Monokai yellow
      error: '#F92672',            // Monokai pink/red
      info: '#66D9EF',             // Monokai cyan
    },
    statusBg: {
      success: 'rgba(166,226,46,0.12)',
      warning: 'rgba(230,219,116,0.12)',
      error: 'rgba(249,38,114,0.12)',
      info: 'rgba(102,217,239,0.12)',
    },
    elevation: {
      none: 'none',
      soft: 'none',
      medium: 'none',
      high: 'none',
    },
    brand: {
      primary: '#A6E22E',          // Monokai green
      primaryDark: '#87BA24',      // Darker
      primaryLight: '#C1F05C',     // Lighter
    },
  },

  /**
   * AgentOS Brand Colors
   */
  brand: {
    primary: '#8B5CF6',           // Purple (unchanged across modes)
    primaryDark: '#7C3AED',       // Darker purple for hover
    primaryLight: '#A78BFA',      // Lighter purple for active
  },

  /**
   * Shape Tokens (AgentOS "device feel")
   */
  shape: {
    radius: {
      sm: 8,   // Small cards, buttons (unified to 8px)
      md: 8,   // Default cards (unified to 8px)
      lg: 8,   // Large cards, modals (unified to 8px)
    },
  },

  /**
   * Spacing Tokens (AgentOS density)
   */
  spacing: {
    cardPadding: 18,      // Card internal padding
    sectionGap: 14,       // Gap between sections inside card
    moduleGap: 16,        // Gap between major modules
  },
} as const

/**
 * Helper: Get tokens for current theme mode
 */
export const getAgentOSTokens = (mode: 'light' | 'dark' | 'github' | 'google' | 'macos' | 'dracula' | 'nord' | 'monokai') => {
  // 自定义主题使用独立的配置
  if (mode === 'github' || mode === 'google' || mode === 'macos' || mode === 'dracula' || mode === 'nord' || mode === 'monokai') {
    const themeConfig = agentosTokens[mode]
    return {
      bg: themeConfig.bg,
      border: themeConfig.border,
      text: themeConfig.text,
      divider: themeConfig.divider,
      status: themeConfig.status,
      statusBg: themeConfig.statusBg,
      elevation: themeConfig.elevation,
      brand: themeConfig.brand,
      shape: agentosTokens.shape,
      spacing: agentosTokens.spacing,
    }
  }

  // Light/Dark 主题使用原有逻辑
  return {
    bg: agentosTokens[mode].bg,
    border: agentosTokens[mode].border,
    text: agentosTokens[mode].text,
    divider: agentosTokens[mode].divider,
    status: agentosTokens.status[mode],
    statusBg: agentosTokens.statusBg[mode],
    elevation: agentosTokens.elevation[mode],
    ...(mode === 'dark' && { surfaceHighlight: agentosTokens.surfaceHighlight.dark }),
    brand: agentosTokens.brand,
    shape: agentosTokens.shape,
    spacing: agentosTokens.spacing,
  }
}

// Type exports
export type AgentOSTokens = ReturnType<typeof getAgentOSTokens>
