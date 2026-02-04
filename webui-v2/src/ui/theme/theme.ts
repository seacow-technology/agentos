import { createTheme, ThemeOptions, alpha } from '@mui/material/styles'
import { tokens } from '../tokens/tokens'
import { agentosTokens, getAgentOSTokens } from '../tokens/agentosTokens'

/**
 * AgentOS Theme Configuration
 *
 * 🎯 Modern Control Surface Theme
 *
 * Key Principles:
 * - Light Mode: White cards on light gray, depth through shadows (browser default friendly)
 * - Dark Mode: Surface brightness gradients, borders instead of shadows (structural integrity)
 *
 * ⚠️ DO NOT override these values in components
 * If you need customization, modify agentosTokens.ts
 */

// ===================================
// Typography Configuration
// ===================================
const typography = {
  fontFamily: [
    'ui-sans-serif',
    'system-ui',
    '-apple-system',
    'BlinkMacSystemFont',
    '"Segoe UI"',
    'Roboto',
    '"Helvetica Neue"',
    'Arial',
    'sans-serif',
    '"Apple Color Emoji"',
    '"Segoe UI Emoji"',
    '"Segoe UI Symbol"',
  ].join(','),
  // Map MD3 type scale to MUI variants
  h1: {
    fontSize: tokens.typography.display.large.size,
    lineHeight: `${tokens.typography.display.large.lineHeight}px`,
    fontWeight: tokens.typography.display.large.weight,
    letterSpacing: tokens.typography.display.large.letterSpacing,
  },
  h2: {
    fontSize: tokens.typography.display.medium.size,
    lineHeight: `${tokens.typography.display.medium.lineHeight}px`,
    fontWeight: tokens.typography.display.medium.weight,
    letterSpacing: tokens.typography.display.medium.letterSpacing,
  },
  h3: {
    fontSize: tokens.typography.headline.large.size,
    lineHeight: `${tokens.typography.headline.large.lineHeight}px`,
    fontWeight: tokens.typography.headline.large.weight,
    letterSpacing: tokens.typography.headline.large.letterSpacing,
  },
  h4: {
    fontSize: tokens.typography.headline.medium.size,
    lineHeight: `${tokens.typography.headline.medium.lineHeight}px`,
    fontWeight: tokens.typography.headline.medium.weight,
    letterSpacing: tokens.typography.headline.medium.letterSpacing,
  },
  h5: {
    fontSize: tokens.typography.headline.small.size,
    lineHeight: `${tokens.typography.headline.small.lineHeight}px`,
    fontWeight: tokens.typography.headline.small.weight,
    letterSpacing: tokens.typography.headline.small.letterSpacing,
  },
  h6: {
    fontSize: tokens.typography.title.large.size,
    lineHeight: `${tokens.typography.title.large.lineHeight}px`,
    fontWeight: tokens.typography.title.large.weight,
    letterSpacing: tokens.typography.title.large.letterSpacing,
  },
  subtitle1: {
    fontSize: tokens.typography.title.medium.size,
    lineHeight: `${tokens.typography.title.medium.lineHeight}px`,
    fontWeight: tokens.typography.title.medium.weight,
    letterSpacing: tokens.typography.title.medium.letterSpacing,
  },
  subtitle2: {
    fontSize: tokens.typography.title.small.size,
    lineHeight: `${tokens.typography.title.small.lineHeight}px`,
    fontWeight: tokens.typography.title.small.weight,
    letterSpacing: tokens.typography.title.small.letterSpacing,
  },
  body1: {
    fontSize: tokens.typography.body.large.size,
    lineHeight: `${tokens.typography.body.large.lineHeight}px`,
    fontWeight: tokens.typography.body.large.weight,
    letterSpacing: tokens.typography.body.large.letterSpacing,
  },
  body2: {
    fontSize: tokens.typography.body.medium.size,
    lineHeight: `${tokens.typography.body.medium.lineHeight}px`,
    fontWeight: tokens.typography.body.medium.weight,
    letterSpacing: tokens.typography.body.medium.letterSpacing,
  },
  button: {
    fontSize: tokens.typography.label.large.size,
    lineHeight: `${tokens.typography.label.large.lineHeight}px`,
    fontWeight: tokens.typography.label.large.weight,
    letterSpacing: tokens.typography.label.large.letterSpacing,
    textTransform: 'none' as const,
  },
  caption: {
    fontSize: tokens.typography.body.small.size,
    lineHeight: `${tokens.typography.body.small.lineHeight}px`,
    fontWeight: tokens.typography.body.small.weight,
    letterSpacing: tokens.typography.body.small.letterSpacing,
  },
  overline: {
    fontSize: tokens.typography.label.small.size,
    lineHeight: `${tokens.typography.label.small.lineHeight}px`,
    fontWeight: tokens.typography.label.small.weight,
    letterSpacing: tokens.typography.label.small.letterSpacing,
    textTransform: 'uppercase' as const,
  },
}

// ===================================
// Light Mode Palette
// ===================================
const lightTokens = getAgentOSTokens('light')

const lightPalette = {
  mode: 'light' as const,
  primary: {
    main: agentosTokens.brand.primary,
    dark: agentosTokens.brand.primaryDark,
    light: agentosTokens.brand.primaryLight,
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#625B71',
    light: '#7D7589',
    dark: '#49454F',
    contrastText: '#FFFFFF',
  },
  error: {
    main: lightTokens.status.error,
    light: '#DC362E',
    dark: '#8C1D18',
    contrastText: '#FFFFFF',
  },
  warning: {
    main: lightTokens.status.warning,
    light: '#FB8C00',
    dark: '#D84315',
    contrastText: '#FFFFFF',
  },
  info: {
    main: lightTokens.status.info,
    light: '#64B5F6',
    dark: '#1976D2',
    contrastText: '#FFFFFF',
  },
  success: {
    main: lightTokens.status.success,
    light: '#4CAF50',
    dark: '#1B5E20',
    contrastText: '#FFFFFF',
  },
  background: {
    default: lightTokens.bg.canvas,
    paper: lightTokens.bg.paper,
  },
  text: {
    primary: lightTokens.text.primary,
    secondary: lightTokens.text.secondary,
    disabled: lightTokens.text.disabled,
  },
  divider: lightTokens.divider,
  // ===================================
  // ✅ AgentOS Tokens (MUI 推荐扩展点)
  // ===================================
  agentos: lightTokens as any,
}

// ===================================
// Dark Mode Palette
// ===================================
const darkTokens = getAgentOSTokens('dark')

const darkPalette = {
  mode: 'dark' as const,
  primary: {
    main: agentosTokens.brand.primary,
    dark: agentosTokens.brand.primaryDark,
    light: agentosTokens.brand.primaryLight,
    contrastText: '#FFFFFF',
  },
  secondary: {
    main: '#CCC2DC',
    light: '#E8DEF8',
    dark: '#625B71',
    contrastText: '#332D41',
  },
  error: {
    main: darkTokens.status.error,
    light: '#FCA5A5',
    dark: '#DC2626',
    contrastText: '#FFFFFF',
  },
  warning: {
    main: darkTokens.status.warning,
    light: '#FDE68A',
    dark: '#F59E0B',
    contrastText: '#000000',
  },
  info: {
    main: darkTokens.status.info,
    light: '#BFDBFE',
    dark: '#3B82F6',
    contrastText: '#000000',
  },
  success: {
    main: darkTokens.status.success,
    light: '#6EE7B7',
    dark: '#10B981',
    contrastText: '#000000',
  },
  background: {
    default: darkTokens.bg.canvas,
    paper: darkTokens.bg.paper,
  },
  text: {
    primary: darkTokens.text.primary,
    secondary: darkTokens.text.secondary,
    disabled: darkTokens.text.disabled,
  },
  divider: darkTokens.divider,
  // ===================================
  // ✅ AgentOS Tokens (MUI 推荐扩展点)
  // ===================================
  agentos: darkTokens as any,
}

// ===================================
// Shape Configuration
// ===================================
const shape = {
  borderRadius: agentosTokens.shape.radius.md, // 8px default (unified)
}

// ===================================
// Spacing Configuration
// ===================================
const spacing = 8

// ===================================
// Custom Theme Palettes
// ===================================

// Helper to create custom theme palette
const createCustomPalette = (themeName: 'github' | 'google' | 'macos' | 'dracula' | 'nord' | 'monokai') => {
  const tokens = getAgentOSTokens(themeName)
  const isDark = themeName === 'dracula' || themeName === 'nord' || themeName === 'monokai'
  const mode = isDark ? 'dark' : 'light'

  return {
    mode: mode as 'light' | 'dark',
    primary: {
      main: tokens.brand.primary,
      dark: tokens.brand.primaryDark,
      light: tokens.brand.primaryLight,
      contrastText: '#FFFFFF',
    },
    secondary: {
      main: tokens.text.secondary,
      light: tokens.text.primary,
      dark: tokens.text.tertiary,
      contrastText: isDark ? '#000000' : '#FFFFFF',
    },
    error: {
      main: tokens.status.error,
      contrastText: '#FFFFFF',
    },
    warning: {
      main: tokens.status.warning,
      contrastText: isDark ? '#000000' : '#FFFFFF',
    },
    info: {
      main: tokens.status.info,
      contrastText: isDark ? '#000000' : '#FFFFFF',
    },
    success: {
      main: tokens.status.success,
      contrastText: isDark ? '#000000' : '#FFFFFF',
    },
    background: {
      default: tokens.bg.canvas,
      paper: tokens.bg.paper,
    },
    text: {
      primary: tokens.text.primary,
      secondary: tokens.text.secondary,
      disabled: tokens.text.disabled,
    },
    divider: tokens.divider,
    agentos: tokens as any,
  }
}

const githubPalette = createCustomPalette('github')
const googlePalette = createCustomPalette('google')
const macosPalette = createCustomPalette('macos')
const draculaPalette = createCustomPalette('dracula')
const nordPalette = createCustomPalette('nord')
const monokaiPalette = createCustomPalette('monokai')

// ===================================
// Create Base Theme Options
// ===================================
type ThemeMode = 'light' | 'dark' | 'github' | 'google' | 'macos' | 'dracula' | 'nord' | 'monokai'

const createThemeOptions = (mode: ThemeMode): ThemeOptions => {
  const modeTokens = getAgentOSTokens(mode)

  // Determine if theme is light or dark
  const darkThemes: ThemeMode[] = ['dark', 'dracula', 'nord', 'monokai']
  const isLight = !darkThemes.includes(mode)

  // Select palette based on mode
  const paletteMap: Record<ThemeMode, any> = {
    light: lightPalette,
    dark: darkPalette,
    github: githubPalette,
    google: googlePalette,
    macos: macosPalette,
    dracula: draculaPalette,
    nord: nordPalette,
    monokai: monokaiPalette,
  }
  const palette = paletteMap[mode]

  return {
    palette,
    typography,
    shape,
    spacing,

    // Transitions
    transitions: {
      duration: {
        shortest: tokens.duration.fast,
        shorter: tokens.duration.normal,
        short: tokens.duration.slow,
        standard: tokens.duration.slow,
        complex: tokens.duration.slower,
        enteringScreen: tokens.duration.slow,
        leavingScreen: tokens.duration.normal,
      },
      easing: {
        easeInOut: tokens.easing.standard,
        easeOut: tokens.easing.decelerate,
        easeIn: tokens.easing.accelerate,
        sharp: tokens.easing.emphasized,
      },
    },

    // Z-index
    zIndex: {
      mobileStepper: tokens.zIndex.base,
      fab: tokens.zIndex.dropdown,
      speedDial: tokens.zIndex.dropdown,
      appBar: tokens.zIndex.sticky,
      drawer: tokens.zIndex.modal,
      modal: tokens.zIndex.modal,
      snackbar: tokens.zIndex.notification,
      tooltip: tokens.zIndex.tooltip,
    },

    // ===================================
    // Component Style Overrides
    // ===================================
    components: {
      // Global baseline
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: modeTokens.bg.canvas,
          },
        },
      },

      // Paper (base surface)
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none', // Disable MUI gradient
            ...(isLight
              ? {
                  // Light: subtle border
                  border: `1px solid ${modeTokens.border.subtle}`,
                }
              : {
                  // Dark: border + subtle highlight
                  border: `1px solid ${modeTokens.border.subtle}`,
                  boxShadow: mode === 'dark' ? agentosTokens.surfaceHighlight.dark : 'none',
                }),
          },
        },
      },

      // Card (main structural element)
      MuiCard: {
        styleOverrides: {
          root: {
            backgroundColor: modeTokens.bg.paper,
            border: `1px solid ${modeTokens.border.subtle}`,
            borderRadius: agentosTokens.shape.radius.md,
            // Light: soft shadow, Dark: no shadow
            boxShadow: isLight ? modeTokens.elevation.soft : 'none',
            ...(isLight
              ? {}
              : {
                  // Dark: add subtle top highlight
                  position: 'relative' as const,
                  '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 1,
                    background: 'rgba(255,255,255,0.04)',
                    borderRadius: `${agentosTokens.shape.radius.md}px ${agentosTokens.shape.radius.md}px 0 0`,
                  },
                }),
          },
        },
      },

      // CardContent
      MuiCardContent: {
        styleOverrides: {
          root: {
            padding: agentosTokens.spacing.cardPadding,
            '&:last-child': {
              paddingBottom: agentosTokens.spacing.cardPadding,
            },
          },
        },
      },

      // Divider
      MuiDivider: {
        styleOverrides: {
          root: {
            borderColor: modeTokens.divider,
          },
        },
      },

      // AppBar
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: isLight
              ? modeTokens.bg.paper  // Light mode: pure white for better contrast
              : modeTokens.bg.surface,
            borderBottom: `1px solid ${modeTokens.border.subtle}`,
            boxShadow: isLight ? modeTokens.elevation.soft : 'none',
            color: modeTokens.text.primary,  // Ensure text color is set
          },
        },
      },

      // Drawer
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: modeTokens.bg.surface,
            borderRight: `1px solid ${modeTokens.border.subtle}`,
            backgroundImage: 'none',
          },
        },
      },

      // Button
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: agentosTokens.shape.radius.sm,
          },
          // Outlined buttons - ensure visibility in light mode
          outlined: isLight
            ? {
                borderWidth: '1.5px',
                borderColor: modeTokens.border.strong,
                '&:hover': {
                  borderWidth: '1.5px',
                  borderColor: agentosTokens.brand.primary,
                  backgroundColor: alpha(agentosTokens.brand.primary, 0.04),
                },
              }
            : {},
          // Text buttons - ensure visibility in light mode
          text: isLight
            ? {
                '&:hover': {
                  backgroundColor: alpha(agentosTokens.brand.primary, 0.08),
                },
              }
            : {},
        },
      },

      // Chip (status indicators)
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: agentosTokens.shape.radius.sm,
            border: `1px solid ${modeTokens.border.subtle}`,
            backgroundColor: isLight
              ? 'rgba(0,0,0,0.03)'
              : 'rgba(255,255,255,0.03)',
          },
          colorSuccess: {
            backgroundColor: modeTokens.statusBg.success,
            borderColor: alpha(modeTokens.status.success, 0.28),
            color: modeTokens.status.success,
          },
          colorWarning: {
            backgroundColor: modeTokens.statusBg.warning,
            borderColor: alpha(modeTokens.status.warning, 0.30),
            color: modeTokens.status.warning,
          },
          colorError: {
            backgroundColor: modeTokens.statusBg.error,
            borderColor: alpha(modeTokens.status.error, 0.30),
            color: modeTokens.status.error,
          },
          colorInfo: {
            backgroundColor: modeTokens.statusBg.info,
            borderColor: alpha(modeTokens.status.info, 0.28),
            color: modeTokens.status.info,
          },
        },
      },

      // Tooltip
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: modeTokens.bg.elevated,
            border: `1px solid ${modeTokens.border.subtle}`,
            color: modeTokens.text.primary,
            boxShadow: isLight ? modeTokens.elevation.medium : 'none',
          },
        },
      },

      // Dialog (elevated surface)
      MuiDialog: {
        styleOverrides: {
          paper: {
            backgroundColor: modeTokens.bg.elevated,
            border: `1px solid ${modeTokens.border.subtle}`,
            borderRadius: agentosTokens.shape.radius.lg,
            boxShadow: isLight ? modeTokens.elevation.high : 'none',
            backgroundImage: 'none',
          },
        },
      },

      // Outlined Input
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: isLight
              ? 'rgba(0,0,0,0.04)'  // Increased from 0.02 for better visibility
              : 'rgba(255,255,255,0.02)',
            '& .MuiOutlinedInput-notchedOutline': {
              borderColor: modeTokens.border.subtle,
              borderWidth: isLight ? '1.5px' : '1px',  // Thicker border in light mode
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: modeTokens.border.strong,
              borderWidth: isLight ? '1.5px' : '1px',
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: alpha(agentosTokens.brand.primary, 0.65),
              borderWidth: 2,
            },
          },
        },
      },

      // List Item Button
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: agentosTokens.shape.radius.sm,
            '&.Mui-selected': {
              backgroundColor: isLight
                ? alpha(agentosTokens.brand.primary, 0.08)
                : alpha(agentosTokens.brand.primary, 0.16),
              '&:hover': {
                backgroundColor: isLight
                  ? alpha(agentosTokens.brand.primary, 0.12)
                  : alpha(agentosTokens.brand.primary, 0.20),
              },
            },
          },
        },
      },

      // Table
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderColor: modeTokens.divider,
          },
        },
      },
    },
  }
}

// ===================================
// Create Themes
// ===================================

// Augment MUI Palette with AgentOS tokens
declare module '@mui/material/styles' {
  interface Palette {
    agentos: ReturnType<typeof getAgentOSTokens>
  }
  interface PaletteOptions {
    agentos?: ReturnType<typeof getAgentOSTokens>
  }
}

// Create light theme
export const lightTheme = createTheme(createThemeOptions('light'))
// ⚠️ MUI's createPalette() filters out unknown properties
// Must manually add agentos tokens after createTheme()
lightTheme.palette.agentos = getAgentOSTokens('light')

// Create dark theme
export const darkTheme = createTheme(createThemeOptions('dark'))
// ⚠️ MUI's createPalette() filters out unknown properties
// Must manually add agentos tokens after createTheme()
darkTheme.palette.agentos = getAgentOSTokens('dark')

// Create GitHub theme
export const githubTheme = createTheme(createThemeOptions('github'))
githubTheme.palette.agentos = getAgentOSTokens('github')

// Create Google theme
export const googleTheme = createTheme(createThemeOptions('google'))
googleTheme.palette.agentos = getAgentOSTokens('google')

// Create macOS theme
export const macosTheme = createTheme(createThemeOptions('macos'))
macosTheme.palette.agentos = getAgentOSTokens('macos')

// Create Dracula theme
export const draculaTheme = createTheme(createThemeOptions('dracula'))
draculaTheme.palette.agentos = getAgentOSTokens('dracula')

// Create Nord theme
export const nordTheme = createTheme(createThemeOptions('nord'))
nordTheme.palette.agentos = getAgentOSTokens('nord')

// Create Monokai theme
export const monokaiTheme = createTheme(createThemeOptions('monokai'))
monokaiTheme.palette.agentos = getAgentOSTokens('monokai')

// Export default theme (light mode)
export default lightTheme
