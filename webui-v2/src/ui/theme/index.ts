/**
 * Theme Module Entry Point
 *
 * ⚠️ 重要：此文件只负责重新导出，不定义任何 theme
 * 所有 theme 定义在 ./theme.ts 中，避免多个注入点混淆
 *
 * Re-exports theme from ./theme.ts to maintain backward compatibility
 * with imports like `from '@/ui/theme'`
 */

// Re-export themes from theme.ts (single source of truth)
export { lightTheme, darkTheme } from './theme'
export { default } from './theme'

// Re-export tokens for convenience
export { tokens } from '../tokens/tokens'

// Re-export DataGrid styles
export { dataGridStyles } from './dataGridStyles'
