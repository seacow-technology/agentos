import { Components, Theme } from '@mui/material/styles'
import { tokens } from '../tokens/tokens'

/**
 * Global Component Style Overrides
 *
 * This file defines default props and style overrides for all MUI components.
 * Goal: Achieve visual consistency without writing sx/style props in pages.
 */

export const components: Components<Theme> = {
  // Button component
  MuiButton: {
    defaultProps: {
      disableElevation: false, // Keep MD3 elevation
      size: 'medium',
    },
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.full, // MD3 uses fully rounded buttons
        textTransform: 'none', // MD3 uses sentence case
        fontWeight: 500,
        paddingLeft: 24,
        paddingRight: 24,
      },
      sizeLarge: {
        height: 48,
        fontSize: tokens.typography.label.large.size,
        paddingLeft: 32,
        paddingRight: 32,
      },
      sizeMedium: {
        height: 40,
        fontSize: tokens.typography.label.large.size,
        paddingLeft: 24,
        paddingRight: 24,
      },
      sizeSmall: {
        height: 32,
        fontSize: tokens.typography.label.medium.size,
        paddingLeft: 16,
        paddingRight: 16,
      },
      contained: {
        boxShadow: 'none', // MD3 filled buttons have no shadow at rest
        '&:hover': {
          boxShadow: 'none',
        },
      },
      outlined: {
        borderWidth: 1,
      },
    },
  },

  // Icon Button
  MuiIconButton: {
    defaultProps: {
      size: 'medium',
    },
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.full,
      },
      sizeLarge: {
        width: 48,
        height: 48,
      },
      sizeMedium: {
        width: 40,
        height: 40,
      },
      sizeSmall: {
        width: 32,
        height: 32,
      },
    },
  },

  // TextField component
  MuiTextField: {
    defaultProps: {
      variant: 'outlined',
      size: 'medium',
    },
    styleOverrides: {
      root: {
        // Consistent spacing
      },
    },
  },

  // OutlinedInput (used by TextField)
  MuiOutlinedInput: {
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.xs, // MD3 uses small radius for inputs
        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
          borderWidth: 2, // MD3 emphasizes focused state
        },
      },
      input: {
        height: 'auto',
        padding: '16px 16px', // MD3 standard padding
      },
      inputSizeSmall: {
        padding: '8px 12px',
      },
    },
  },

  // Card component
  MuiCard: {
    defaultProps: {
      elevation: tokens.elevation.xs, // Subtle elevation at rest
    },
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.md, // MD3 medium radius for cards
        backgroundImage: 'none', // Remove MUI gradient
      },
    },
  },

  // CardContent
  MuiCardContent: {
    styleOverrides: {
      root: {
        padding: tokens.spacing.lg, // 24px padding
        '&:last-child': {
          paddingBottom: tokens.spacing.lg,
        },
      },
    },
  },

  // CardActions
  MuiCardActions: {
    styleOverrides: {
      root: {
        padding: tokens.spacing.md, // 16px padding
        paddingTop: 0,
      },
    },
  },

  // Paper component
  MuiPaper: {
    defaultProps: {
      elevation: tokens.elevation.xs,
    },
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.sm,
        backgroundImage: 'none',
      },
      rounded: {
        borderRadius: tokens.radius.sm,
      },
    },
  },

  // Dialog component
  MuiDialog: {
    defaultProps: {
      maxWidth: 'sm',
    },
    styleOverrides: {
      paper: {
        borderRadius: tokens.radius.lg, // Large radius for dialogs
        backgroundImage: 'none',
      },
    },
  },

  // DialogTitle
  MuiDialogTitle: {
    styleOverrides: {
      root: {
        fontSize: tokens.typography.headline.small.size,
        fontWeight: tokens.typography.headline.small.weight,
        padding: `${tokens.spacing.lg}px ${tokens.spacing.lg}px ${tokens.spacing.md}px`,
      },
    },
  },

  // DialogContent
  MuiDialogContent: {
    styleOverrides: {
      root: {
        padding: `0 ${tokens.spacing.lg}px`,
      },
    },
  },

  // DialogActions
  MuiDialogActions: {
    styleOverrides: {
      root: {
        padding: tokens.spacing.lg,
        gap: tokens.spacing.sm,
      },
    },
  },

  // Chip component
  MuiChip: {
    defaultProps: {
      size: 'medium',
    },
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.sm, // MD3 uses small radius for chips
        height: 32,
        fontSize: tokens.typography.label.medium.size,
        fontWeight: tokens.typography.label.medium.weight,
      },
      sizeSmall: {
        height: 24,
        fontSize: tokens.typography.label.small.size,
      },
      sizeMedium: {
        height: 32,
      },
    },
  },


  // AppBar
  MuiAppBar: {
    defaultProps: {
      elevation: 0,
    },
    styleOverrides: {
      root: {
        borderBottom: '1px solid',
        borderColor: 'divider',
      },
    },
  },

  // Toolbar
  MuiToolbar: {
    styleOverrides: {
      root: {
        minHeight: 64,
        paddingLeft: tokens.spacing.lg,
        paddingRight: tokens.spacing.lg,
      },
    },
  },

  // Drawer
  MuiDrawer: {
    styleOverrides: {
      paper: {
        borderRadius: 0, // Drawers don't have rounded corners
        backgroundImage: 'none',
      },
    },
  },

  // Tab
  MuiTab: {
    styleOverrides: {
      root: {
        textTransform: 'none',
        minHeight: 48,
        fontSize: tokens.typography.title.small.size,
        fontWeight: tokens.typography.title.small.weight,
        letterSpacing: tokens.typography.title.small.letterSpacing,
      },
    },
  },

  // Tabs
  MuiTabs: {
    styleOverrides: {
      root: {
        minHeight: 48,
      },
      indicator: {
        height: 3,
        borderRadius: `${tokens.radius.xs}px ${tokens.radius.xs}px 0 0`,
      },
    },
  },

  // Alert
  MuiAlert: {
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.sm,
        fontSize: tokens.typography.body.medium.size,
      },
      standardSuccess: {
        backgroundColor: 'rgba(46, 125, 50, 0.1)',
      },
      standardInfo: {
        backgroundColor: 'rgba(33, 150, 243, 0.1)',
      },
      standardWarning: {
        backgroundColor: 'rgba(230, 81, 0, 0.1)',
      },
      standardError: {
        backgroundColor: 'rgba(179, 38, 30, 0.1)',
      },
    },
  },

  // Snackbar
  MuiSnackbar: {
    styleOverrides: {
      root: {
        '& .MuiPaper-root': {
          borderRadius: tokens.radius.sm,
        },
      },
    },
  },

  // Menu
  MuiMenu: {
    styleOverrides: {
      paper: {
        borderRadius: tokens.radius.sm,
        marginTop: tokens.spacing.xs,
      },
      list: {
        padding: `${tokens.spacing.xs}px 0`,
      },
    },
  },

  // MenuItem
  MuiMenuItem: {
    styleOverrides: {
      root: {
        fontSize: tokens.typography.body.medium.size,
        minHeight: 48,
        paddingLeft: tokens.spacing.md,
        paddingRight: tokens.spacing.md,
        borderRadius: 0,
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
        },
      },
    },
  },

  // Tooltip
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        backgroundColor: 'rgba(97, 97, 97, 0.92)', // MD3 tooltip color
        fontSize: tokens.typography.body.small.size,
        borderRadius: tokens.radius.xs,
        padding: `${tokens.spacing.xs}px ${tokens.spacing.sm}px`,
      },
      arrow: {
        color: 'rgba(97, 97, 97, 0.92)',
      },
    },
  },

  // Switch
  MuiSwitch: {
    styleOverrides: {
      root: {
        width: 52,
        height: 32,
        padding: 0,
      },
      switchBase: {
        padding: 4,
        '&.Mui-checked': {
          transform: 'translateX(20px)',
        },
      },
      thumb: {
        width: 24,
        height: 24,
      },
      track: {
        borderRadius: tokens.radius.full,
        opacity: 1,
      },
    },
  },

  // Checkbox
  MuiCheckbox: {
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.xs,
      },
    },
  },

  // Radio
  MuiRadio: {
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.full,
      },
    },
  },

  // List
  MuiList: {
    styleOverrides: {
      root: {
        padding: `${tokens.spacing.xs}px 0`,
      },
    },
  },

  // ListItem
  MuiListItem: {
    styleOverrides: {
      root: {
        paddingLeft: tokens.spacing.md,
        paddingRight: tokens.spacing.md,
      },
    },
  },

  // ListItemButton
  MuiListItemButton: {
    styleOverrides: {
      root: {
        borderRadius: tokens.radius.xs,
        marginLeft: tokens.spacing.xs,
        marginRight: tokens.spacing.xs,
        paddingLeft: tokens.spacing.md,
        paddingRight: tokens.spacing.md,
        '&:hover': {
          backgroundColor: 'rgba(0, 0, 0, 0.04)',
        },
        '&.Mui-selected': {
          backgroundColor: 'rgba(103, 80, 164, 0.08)',
          '&:hover': {
            backgroundColor: 'rgba(103, 80, 164, 0.12)',
          },
        },
      },
    },
  },

  // Divider
  MuiDivider: {
    styleOverrides: {
      root: {
        borderColor: 'divider',
      },
    },
  },

  // Select
  MuiSelect: {
    defaultProps: {
      variant: 'outlined',
    },
    styleOverrides: {
      outlined: {
        borderRadius: tokens.radius.xs,
      },
    },
  },
}
