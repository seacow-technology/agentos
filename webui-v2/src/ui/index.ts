/**
 * UI Design System Entry Point
 *
 * This is the single source of truth for all UI-related exports.
 * Pages MUST import all components, theme, and utilities from here.
 *
 * FORBIDDEN: Direct imports from @mui/material or @mui/x-data-grid
 *
 * Usage:
 *   import { PrimaryButton, AppCard, TextInput, theme, tokens } from '@/ui'
 *   import { AddIcon, EditIcon } from '@/ui/icons'
 */

// ============================================================
// Theme & Tokens
// ============================================================
export { default as theme, lightTheme, darkTheme, tokens, dataGridStyles } from './theme'

export type {
  Radius,
  Spacing,
  Elevation,
  Duration,
  Easing,
  ZIndex,
} from './tokens/tokens'

// ============================================================
// Icons
// ============================================================
export * from './icons'

// ============================================================
// Text (Unified Text Exit)
// ============================================================
export { T, txt, t, tr, tm, hasTranslation, getCurrentLanguage, changeLanguage, K } from './text'

export type {
  TranslateParams,
  TranslateOptions,
  Language,
  FallbackDict,
  TextKey,
  AllTextKeys,
} from './text'

// ============================================================
// Buttons
// ============================================================
export {
  PrimaryButton,
  SecondaryButton,
  DangerButton,
  IconOnlyButton,
  ButtonWithIcon,
} from './controls/buttons'

export type {
  PrimaryButtonProps,
  SecondaryButtonProps,
  DangerButtonProps,
  IconOnlyButtonProps,
  ButtonWithIconProps,
} from './controls/buttons'

// ============================================================
// Forms
// ============================================================
export {
  TextInput,
  SelectInput,
  FormField,
} from './controls/forms'

export type {
  TextInputProps,
  SelectInputProps,
  SelectOption,
  FormFieldProps,
} from './controls/forms'

// ============================================================
// MUI Layout & Typography Components (Native Re-exports)
// ============================================================
// G3 Exceptions: Box, Stack, Grid, Typography, Divider, Container are allowed
export {
  Box,
  Stack,
  Grid,
  Typography,
  Divider,
  Container,
} from '@mui/material'

// ============================================================
// MUI Form Components (Native Re-exports)
// ============================================================
// For pages that need native MUI form components (DialogForm, FilterBar)
// G3 Exception: These are re-exported to maintain centralized import path
export {
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  ToggleButtonGroup,
  ToggleButton,
} from '@mui/material'

// ============================================================
// MUI Dialog & Button Components (Native Re-exports)
// ============================================================
// For pages that need to create custom dialogs or use standard buttons
// G3 Exception: These are re-exported to maintain centralized import path
export {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Chip,
  CircularProgress,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  Alert,
  AlertTitle,
  Checkbox,
  FormControlLabel,
  Link,
} from '@mui/material'

// ============================================================
// Surfaces (Cards)
// ============================================================
export {
  AppCard,
  AppCardHeader,
  AppCardBody,
} from './surfaces/AppCard'

export type {
  AppCardProps,
  AppCardHeaderProps,
  AppCardBodyProps,
} from './surfaces/AppCard'

// ============================================================
// Data (Tables)
// ============================================================
export {
  AppTable,
  TableToolbar,
} from './data/AppTable'

export type {
  AppTableProps,
  TableToolbarProps,
  GridColDef,
  GridRowsProp,
  GridPaginationModel,
} from './data/AppTable'

// Table System (Pattern Components)
export {
  TableShell,
  FilterBar,
} from './table'

export type {
  TableShellProps,
  FilterBarProps,
  FilterItem,
  FilterAction,
} from './table'

// Card System (Pattern Components)
export {
  CardCollectionWrap,
  ItemCard,
  StatusCard,
} from './cards'

export type {
  CardCollectionWrapProps,
  ItemCardProps,
  ItemCardMeta,
  ItemCardAction,
  StatusCardProps,
  StatusCardMeta,
  StatusCardAction,
  StatusColor,
} from './cards'

// Dashboard System (Pattern Components)
export {
  DashboardGrid,
  StatCard,
  MetricCard,
} from './dashboard'

export type {
  DashboardGridProps,
  StatCardProps,
  MetricCardProps,
  MetricItem,
  MetricCardAction,
} from './dashboard'

// Chat System (Pattern Components)
export {
  AppChatShell,
  ChatShell,
  SessionList,
  SessionItem,
  ChatMessage,
  ChatInputBar,
  ChatSkeleton,
  ModelSelectionBar,
} from './chat'

export type {
  AppChatShellProps,
  ChatSession,
  ChatShellProps,
  ChatMessageType,
  SessionListProps,
  SessionItemProps,
  ModelSelectionBarProps,
} from './chat'

// ============================================================
// Components (AppBar & UI Utilities)
// ============================================================
export {
  ThemeToggle,
  LanguageSwitch,
  ApiStatus,
  ApiStatusDialog,
} from './components'

export type {
  ThemeToggleProps,
  LanguageSwitchProps,
  ApiStatusProps,
  ApiStatusType,
  ApiStatusDialogProps,
} from './components'

// ============================================================
// States (from components/)
// ============================================================
export { EmptyState } from '../components/EmptyState'
export { ErrorState } from '../components/ErrorState'
export { LoadingState } from '../components/LoadingState'

export type { EmptyStateProps } from '../components/EmptyState'
export type { ErrorStateProps } from '../components/ErrorState'
export type { LoadingStateProps } from '../components/LoadingState'
