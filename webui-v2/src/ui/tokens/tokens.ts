/**
 * Design Tokens - Single Source of Truth for UI Values
 * Based on Material Design 3 specifications
 *
 * DO NOT use magic numbers in components - reference these tokens instead
 */

export const tokens = {
  /**
   * Border Radius Scale
   * MD3 uses 4dp increments for shape
   */
  radius: {
    none: 0,
    xs: 8,    // Extra small - chips, small buttons (unified to 8px)
    sm: 8,    // Small - cards, inputs
    md: 8,    // Medium - dialogs, elevated cards (unified to 8px)
    lg: 8,    // Large - modal corners (unified to 8px)
    xl: 8,    // Extra large - hero cards (unified to 8px)
    xxl: 28,  // 2XL - special prominence
    full: 9999, // Fully rounded - pills, avatars
  },

  /**
   * Spacing Scale (8px base unit)
   * MD3 uses 8dp grid system
   */
  spacing: {
    xs: 4,    // 0.5x - tight spacing
    sm: 8,    // 1x - compact spacing
    md: 16,   // 2x - default spacing
    lg: 24,   // 3x - comfortable spacing
    xl: 32,   // 4x - spacious layout
    xxl: 48,  // 6x - section separation
    xxxl: 64, // 8x - major sections
  },

  /**
   * Elevation (shadow depth)
   * MD3 elevation levels
   */
  elevation: {
    none: 0,  // Flat surface
    xs: 1,    // Slightly raised (cards at rest)
    sm: 2,    // Raised (buttons, input fields)
    md: 3,    // Floating (FABs)
    lg: 4,    // Dialog overlay
    xl: 8,    // Modal overlay
    xxl: 12,  // Maximum elevation (snackbars)
  },

  /**
   * Typography Scale
   * MD3 type scale with pixel sizes
   */
  typography: {
    // Display - largest text for hero sections
    display: {
      large: { size: 57, lineHeight: 64, weight: 400, letterSpacing: -0.25 },
      medium: { size: 45, lineHeight: 52, weight: 400, letterSpacing: 0 },
      small: { size: 36, lineHeight: 44, weight: 400, letterSpacing: 0 },
    },
    // Headline - high-emphasis titles
    headline: {
      large: { size: 32, lineHeight: 40, weight: 400, letterSpacing: 0 },
      medium: { size: 28, lineHeight: 36, weight: 400, letterSpacing: 0 },
      small: { size: 24, lineHeight: 32, weight: 400, letterSpacing: 0 },
    },
    // Title - medium-emphasis titles
    title: {
      large: { size: 22, lineHeight: 28, weight: 400, letterSpacing: 0 },
      medium: { size: 16, lineHeight: 24, weight: 500, letterSpacing: 0.15 },
      small: { size: 14, lineHeight: 20, weight: 500, letterSpacing: 0.1 },
    },
    // Body - main content text
    body: {
      large: { size: 16, lineHeight: 24, weight: 400, letterSpacing: 0.5 },
      medium: { size: 14, lineHeight: 20, weight: 400, letterSpacing: 0.25 },
      small: { size: 12, lineHeight: 16, weight: 400, letterSpacing: 0.4 },
    },
    // Label - button and tag text
    label: {
      large: { size: 14, lineHeight: 20, weight: 500, letterSpacing: 0.1 },
      medium: { size: 12, lineHeight: 16, weight: 500, letterSpacing: 0.5 },
      small: { size: 11, lineHeight: 16, weight: 500, letterSpacing: 0.5 },
    },
  },

  /**
   * Animation Duration
   * MD3 motion durations
   */
  duration: {
    instant: 0,
    fast: 100,      // Micro-interactions
    normal: 200,    // Standard transitions
    slow: 300,      // Emphasis transitions
    slower: 400,    // Complex animations
  },

  /**
   * Animation Easing
   * MD3 easing curves
   */
  easing: {
    standard: 'cubic-bezier(0.4, 0.0, 0.2, 1)',     // Standard curve
    decelerate: 'cubic-bezier(0.0, 0.0, 0.2, 1)',   // Elements entering
    accelerate: 'cubic-bezier(0.4, 0.0, 1, 1)',     // Elements exiting
    emphasized: 'cubic-bezier(0.2, 0.0, 0, 1)',     // Emphasized entrance
  },

  /**
   * Z-Index Scale
   * Stacking order for layered UI
   */
  zIndex: {
    base: 0,
    dropdown: 1000,
    sticky: 1020,
    overlay: 1030,
    modal: 1040,
    popover: 1050,
    tooltip: 1060,
    notification: 1070,
  },

  /**
   * Container Max Widths
   * Standard content container sizes
   */
  container: {
    xs: 444,   // Mobile
    sm: 600,   // Small tablet
    md: 960,   // Tablet
    lg: 1280,  // Desktop
    xl: 1920,  // Large desktop
  },
} as const

// Type exports for TypeScript autocomplete
export type Radius = keyof typeof tokens.radius
export type Spacing = keyof typeof tokens.spacing
export type Elevation = keyof typeof tokens.elevation
export type Duration = keyof typeof tokens.duration
export type Easing = keyof typeof tokens.easing
export type ZIndex = keyof typeof tokens.zIndex
export type Container = keyof typeof tokens.container
