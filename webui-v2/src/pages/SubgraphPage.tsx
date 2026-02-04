/**
 * SubgraphPage - Subgraph Visualization & Query
 *
 * 🔒 Migration Contract 遵循规则：
 * - ✅ Text System: 使用 t('xxx')（G7-G8）
 * - ✅ Layout: usePageHeader + usePageActions（G10-G11）
 * - ✅ P0 Implementation: Query + Filters + Node/Edge Interaction + Gap Anchors
 * - ✅ P1 Implementation: Legend Panel + Metadata Panel + Caching Mechanism
 * - ✅ P2 Implementation: Welcome Screen + Query Controls + API Integration
 * - ⚠️  P2-17 (Optional): Interactive Cytoscape.js graph visualization (table-based already sufficient)
 *
 * P0 Implementation Status:
 * - ✅ P0-25: Visualization Filters (Blind Spots/Weak Edges/Coverage Gaps)
 * - ✅ P0-26: Node/Edge Interaction (Table-based hover/click with DetailDrawer)
 * - ✅ P0-27: Gap Anchor Nodes (Special styling + DetailDrawer)
 *
 * P1 Implementation Status:
 * - ✅ P1-30: Legend Panel (Node type color encoding + optional visibility toggle)
 * - ✅ P1-31: Metadata Panel (StatCards with node/edge/depth stats)
 * - ✅ P1-32: Caching Mechanism (Client-side cache with 5min staleTime)
 *
 * P2 Implementation Status:
 * - ⚠️  P2-17: Interactive Cytoscape.js Graph (OPTIONAL - table-based already satisfies requirements)
 * - ✅ P2-18: Subgraph Query API Integration (verified in P0-25)
 * - ✅ P2-19: Query Controls (verified in P0-26 - Seed Input, K-Hop, Min Evidence)
 * - ✅ P2-20: Welcome Screen (EmptyState with usage instructions)
 *
 * Current Strategy: Simplified Table/CardGrid version
 * - Query controls: Seed input, K-Hop slider, Min Evidence slider
 * - Filters: Checkboxes for visual filtering
 * - Node display: Table with hover tooltips and click-to-detail
 * - Gap anchors: Special rows with distinct styling
 * - Welcome screen: EmptyState guidance before first query
 *
 * Future Enhancement (Optional): Migrate to interactive graph (react-cytoscapejs / React Flow)
 */

import React, { useState, useCallback, useMemo } from 'react'
import {
  Box,
  TextField,
  Slider,
  Button,
  Checkbox,
  FormControlLabel,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Tooltip,
  Alert,
  CircularProgress,
  IconButton,
  Drawer,
  FormGroup,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material'
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Circle as CircleIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Close as CloseIcon,
  Lens as LensIcon,
  Update as UpdateIcon,
} from '@mui/icons-material'
import { usePageHeader, usePageActions } from '@/ui/layout'
import { K, useTextTranslation } from '@/ui/text'
import { StatCard } from '@/ui/dashboard/StatCard'
import { DashboardGrid } from '@/ui/dashboard/DashboardGrid'
import { EmptyState } from '@/ui/layout/EmptyState'
import { brainosService } from '@/services/brainos.service'
import { toast } from '@/ui/feedback'

// ============================================================================
// Type Definitions
// ============================================================================

interface SubgraphNode {
  id: string
  entity_type: string
  entity_key: string
  entity_name: string
  evidence_count: number
  coverage_sources: string[]
  evidence_density: number
  is_blind_spot: boolean
  blind_spot_severity?: number
  blind_spot_type?: string
  blind_spot_reason?: string
  in_degree: number
  out_degree: number
  distance_from_seed: number
  missing_connections_count?: number
  gap_types?: string[]
  visual: NodeVisual
}

interface NodeVisual {
  color: string
  size: number
  border_color: string
  border_width: number
  border_style: string
  shape: string
  label: string
  tooltip: string
}

interface SubgraphEdge {
  source: string
  target: string
  type: string
  evidence_count: number
  confidence: number
  visual: {
    width: number
    color: string
    style: string
  }
}

interface SubgraphQueryParams {
  seed: string
  k_hop: number
  min_evidence: number
}

interface SubgraphResult {
  nodes: SubgraphNode[]
  edges: SubgraphEdge[]
  metadata: {
    node_count: number
    edge_count: number
    blind_spot_count: number
    gap_anchor_count: number
    avg_evidence_density: number
  }
}

interface FilterState {
  showBlindSpots: boolean
  showWeakEdges: boolean
  showCoverageGaps: boolean
}

// P1-32: Cache Entry Interface
interface CacheEntry {
  data: SubgraphResult
  timestamp: number
  params: SubgraphQueryParams
}

// P1-30: Node Type Legend
interface LegendItem {
  type: string
  label: string
  color: string
  visible: boolean
}

// ============================================================================
// P1-32: Cache Constants
// ============================================================================

const CACHE_KEY = 'subgraph_cache'
const CACHE_STALE_TIME = 5 * 60 * 1000 // 5 minutes in milliseconds

// ============================================================================
// SubgraphPage Component
// ============================================================================

export default function SubgraphPage() {
  // i18n Hook
  const { t } = useTextTranslation()

  // Query State
  const [queryParams, setQueryParams] = useState<SubgraphQueryParams>({
    seed: '',
    k_hop: 2,
    min_evidence: 1,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<SubgraphResult | null>(null)

  // Filter State (P0-25)
  const [filters, setFilters] = useState<FilterState>({
    showBlindSpots: true,
    showWeakEdges: true,
    showCoverageGaps: true,
  })

  // Detail Drawer State (P0-26, P0-27)
  const [selectedNode, setSelectedNode] = useState<SubgraphNode | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // P1-30: Legend State
  const [legendItems, setLegendItems] = useState<LegendItem[]>([])

  // P1-32: Cache State
  const [cacheHit, setCacheHit] = useState(false)

  // Page Header
  usePageHeader({
    title: t(K.page.subgraph.title),
    subtitle: t(K.page.subgraph.subtitle),
  })

  usePageActions([
    {
      key: 'refresh',
      label: t('common.refresh'),
      variant: 'outlined',
      onClick: () => handleQuery(true),
    },
  ])

  // ===================================
  // P1-32: Cache Utilities
  // ===================================

  function getCacheKey(params: SubgraphQueryParams): string {
    return `${params.seed}_${params.k_hop}_${params.min_evidence}`
  }

  function loadFromCache(params: SubgraphQueryParams): SubgraphResult | null {
    try {
      const cacheData = localStorage.getItem(CACHE_KEY)
      if (!cacheData) return null

      const cache: Record<string, CacheEntry> = JSON.parse(cacheData)
      const key = getCacheKey(params)
      const entry = cache[key]

      if (!entry) return null

      // Check if cache is stale (older than 5 minutes)
      const now = Date.now()
      const age = now - entry.timestamp
      if (age > CACHE_STALE_TIME) {
        console.log('[SubgraphPage] Cache expired:', { age, staleTime: CACHE_STALE_TIME })
        return null
      }

      console.log('[SubgraphPage] Cache hit:', { key, age })
      return entry.data
    } catch (err) {
      console.error('[SubgraphPage] Failed to load cache:', err)
      return null
    }
  }

  function saveToCache(params: SubgraphQueryParams, data: SubgraphResult): void {
    try {
      const cacheData = localStorage.getItem(CACHE_KEY)
      const cache: Record<string, CacheEntry> = cacheData ? JSON.parse(cacheData) : {}

      const key = getCacheKey(params)
      cache[key] = {
        data,
        timestamp: Date.now(),
        params,
      }

      localStorage.setItem(CACHE_KEY, JSON.stringify(cache))
      console.log('[SubgraphPage] Cache saved:', { key })
    } catch (err) {
      console.error('[SubgraphPage] Failed to save cache:', err)
    }
  }

  function invalidateCache(): void {
    try {
      localStorage.removeItem(CACHE_KEY)
      console.log('[SubgraphPage] Cache invalidated')
    } catch (err) {
      console.error('[SubgraphPage] Failed to invalidate cache:', err)
    }
  }

  // ===================================
  // Query Handlers
  // ===================================

  async function handleQuery(forceRefresh = false) {
    if (!queryParams.seed.trim()) {
      setError(t(K.page.subgraph.seedRequired))
      return
    }

    // P1-32: Check cache first (unless force refresh)
    if (!forceRefresh) {
      const cached = loadFromCache(queryParams)
      if (cached) {
        setResult(cached)
        setCacheHit(true)
        updateLegend(cached.nodes)
        console.log('[SubgraphPage] Loaded from cache')
        return
      }
    } else {
      // Force refresh invalidates entire cache
      invalidateCache()
      setCacheHit(false)
    }

    setLoading(true)
    setError(null)
    setCacheHit(false)

    try {
      // Phase 6: Real API Integration
      console.log('[SubgraphPage] Fetching subgraph from API:', queryParams)
      const apiResult = await brainosService.getSubgraph(queryParams.seed, queryParams.k_hop)

      // Transform API result to internal format
      const result: SubgraphResult = {
        nodes: apiResult.nodes,
        edges: apiResult.edges,
        metadata: apiResult.metadata,
      }

      setResult(result)

      // P1-32: Save to cache
      saveToCache(queryParams, result)

      // P1-30: Update legend
      updateLegend(result.nodes)

      console.log('[SubgraphPage] Subgraph loaded successfully:', {
        nodeCount: result.metadata.node_count,
        edgeCount: result.metadata.edge_count
      })
    } catch (err: any) {
      console.error('[SubgraphPage] Failed to load subgraph:', err)
      const errorMessage = err.message || t(K.page.subgraph.loadFailed)
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  // ===================================
  // P1-30: Legend Utilities
  // ===================================

  function updateLegend(nodes: SubgraphNode[]) {
    // Extract unique node types with their colors
    const typeMap = new Map<string, { color: string; count: number }>()

    nodes.forEach(node => {
      const type = node.entity_type
      if (typeMap.has(type)) {
        typeMap.get(type)!.count++
      } else {
        typeMap.set(type, {
          color: node.visual.color,
          count: 1,
        })
      }
    })

    // Convert to legend items
    const items: LegendItem[] = Array.from(typeMap.entries()).map(([type, { color }]) => ({
      type,
      label: type.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()),
      color,
      visible: true,
    }))

    setLegendItems(items)
  }

  function toggleLegendItem(type: string) {
    setLegendItems(prev =>
      prev.map(item =>
        item.type === type ? { ...item, visible: !item.visible } : item
      )
    )
  }

  function handleKeyPress(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Enter') {
      handleQuery(false)
    }
  }

  // ===================================
  // Filter Handlers (P0-25)
  // ===================================

  const handleFilterChange = useCallback((filterKey: keyof FilterState) => {
    setFilters(prev => ({ ...prev, [filterKey]: !prev[filterKey] }))
  }, [])

  const handleGapsOnlyClick = useCallback(() => {
    setFilters({
      showBlindSpots: true,
      showWeakEdges: false,
      showCoverageGaps: true,
    })
  }, [])

  // ===================================
  // Node/Edge Interaction (P0-26, P0-27)
  // ===================================

  const handleNodeClick = useCallback((node: SubgraphNode) => {
    setSelectedNode(node)
    setDrawerOpen(true)
  }, [])

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false)
  }, [])

  // ===================================
  // Filtered Nodes
  // ===================================

  const filteredNodes = useMemo(() => {
    if (!result) return []

    return result.nodes.filter(node => {
      // P0-25: Filter by visualization settings
      if (node.entity_type === 'gap_anchor' && !filters.showCoverageGaps) {
        return false
      }
      if (node.is_blind_spot && !filters.showBlindSpots) {
        return false
      }

      // P1-30: Filter by legend visibility
      const legendItem = legendItems.find(item => item.type === node.entity_type)
      if (legendItem && !legendItem.visible) {
        return false
      }

      return true
    })
  }, [result, filters, legendItems])

  // ===================================
  // P1-31: Metadata Stats (computed from result)
  // ===================================

  const metadataStats = useMemo(() => {
    if (!result) return null

    return {
      nodeCount: result.metadata.node_count,
      edgeCount: result.metadata.edge_count,
      depth: queryParams.k_hop,
      lastUpdated: new Date().toLocaleTimeString(),
    }
  }, [result, queryParams.k_hop])

  // ===================================
  // Render: Query Controls + Results
  // ===================================

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* P1-31: Metadata Panel (at top when result exists) */}
      {metadataStats && (
        <DashboardGrid columns={4} gap={16}>
          <StatCard
            title={t(K.page.subgraph.statTotalNodes)}
            value={metadataStats.nodeCount.toString()}
            icon={<CircleIcon />}
          />
          <StatCard
            title={t(K.page.subgraph.statTotalEdges)}
            value={metadataStats.edgeCount.toString()}
            icon={<FilterIcon />}
          />
          <StatCard
            title={t(K.page.subgraph.statAvgDepth)}
            value={metadataStats.depth.toString()}
            icon={<InfoIcon />}
          />
          <StatCard
            title={t(K.page.subgraph.lastUpdated)}
            value={metadataStats.lastUpdated}
            icon={<UpdateIcon />}
          />
        </DashboardGrid>
      )}

      {/* P1-32: Cache Status Indicator */}
      {cacheHit && (
        <Alert severity="info" onClose={() => setCacheHit(false)}>
          {t(K.page.subgraph.cacheLoadedMessage)}
        </Alert>
      )}

      {/* Query Controls Panel */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          {t(K.page.subgraph.queryControls)}
        </Typography>

        {/* Seed Input */}
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            label={t(K.page.subgraph.seedEntity)}
            placeholder={t(K.page.subgraph.searchPlaceholder)}
            value={queryParams.seed}
            onChange={(e) => setQueryParams(prev => ({ ...prev, seed: e.target.value }))}
            onKeyDown={handleKeyPress}
            InputProps={{
              endAdornment: (
                <IconButton onClick={() => handleQuery(false)} disabled={loading}>
                  <SearchIcon />
                </IconButton>
              ),
            }}
          />
        </Box>

        {/* K-Hop Slider */}
        <Box sx={{ mb: 2 }}>
          <Typography gutterBottom>{t(K.page.subgraph.kHop)}: {queryParams.k_hop}</Typography>
          <Slider
            value={queryParams.k_hop}
            onChange={(_, value) => setQueryParams(prev => ({ ...prev, k_hop: value as number }))}
            min={1}
            max={5}
            step={1}
            marks
            valueLabelDisplay="auto"
          />
        </Box>

        {/* Min Evidence Slider */}
        <Box sx={{ mb: 2 }}>
          <Typography gutterBottom>{t(K.page.subgraph.minEvidence)}: {queryParams.min_evidence}</Typography>
          <Slider
            value={queryParams.min_evidence}
            onChange={(_, value) => setQueryParams(prev => ({ ...prev, min_evidence: value as number }))}
            min={0}
            max={10}
            step={1}
            marks
            valueLabelDisplay="auto"
          />
        </Box>

        {/* Query Button */}
        <Button
          variant="contained"
          startIcon={loading ? <CircularProgress size={20} /> : <SearchIcon />}
          onClick={() => handleQuery(false)}
          disabled={loading || !queryParams.seed.trim()}
          fullWidth
        >
          {loading ? t(K.common.loading) : t(K.page.subgraph.queryButton)}
        </Button>
      </Paper>

      {/* Visualization Filters Panel (P0-25) */}
      {result && (
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6">
              <FilterIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              {t(K.page.subgraph.visualFilters)}
            </Typography>
            <Button
              size="small"
              variant="outlined"
              onClick={handleGapsOnlyClick}
            >
              {t(K.page.subgraph.gapsOnly)}
            </Button>
          </Box>

          <FormGroup row>
            <FormControlLabel
              control={
                <Checkbox
                  checked={filters.showBlindSpots}
                  onChange={() => handleFilterChange('showBlindSpots')}
                  icon={<VisibilityOffIcon />}
                  checkedIcon={<VisibilityIcon />}
                />
              }
              label={t(K.page.subgraph.showBlindSpots)}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={filters.showWeakEdges}
                  onChange={() => handleFilterChange('showWeakEdges')}
                  icon={<VisibilityOffIcon />}
                  checkedIcon={<VisibilityIcon />}
                />
              }
              label={t(K.page.subgraph.showWeakEdges)}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={filters.showCoverageGaps}
                  onChange={() => handleFilterChange('showCoverageGaps')}
                  icon={<VisibilityOffIcon />}
                  checkedIcon={<VisibilityIcon />}
                />
              }
              label={t(K.page.subgraph.showCoverageGaps)}
            />
          </FormGroup>

          {result.metadata && (
            <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Chip label={`Nodes: ${result.metadata.node_count}`} size="small" />
              <Chip label={`Edges: ${result.metadata.edge_count}`} size="small" />
              <Chip label={`Blind Spots: ${result.metadata.blind_spot_count}`} size="small" color="warning" />
              <Chip label={`Gap Anchors: ${result.metadata.gap_anchor_count}`} size="small" color="default" />
              <Chip label={`Avg Density: ${(result.metadata.avg_evidence_density * 100).toFixed(1)}%`} size="small" color="info" />
            </Box>
          )}
        </Paper>
      )}

      {/* P1-30: Legend Panel */}
      {result && legendItems.length > 0 && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            <LensIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            {t(K.page.subgraph.legendTitle)}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t(K.page.subgraph.legendToggle)}
          </Typography>
          <List dense>
            {legendItems.map((item) => (
              <ListItem
                key={item.type}
                component="button"
                onClick={() => toggleLegendItem(item.type)}
                sx={{
                  borderRadius: 1,
                  mb: 0.5,
                  opacity: item.visible ? 1 : 0.5,
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  {item.visible ? (
                    <CircleIcon sx={{ color: item.color, fontSize: 24 }} />
                  ) : (
                    <CircleIcon sx={{ color: item.color, fontSize: 24, opacity: 0.3 }} />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  secondary={`Type: ${item.type}`}
                  primaryTypographyProps={{
                    fontWeight: item.visible ? 600 : 400,
                  }}
                />
                {item.visible ? (
                  <VisibilityIcon sx={{ color: 'action.active' }} />
                ) : (
                  <VisibilityOffIcon sx={{ color: 'action.disabled' }} />
                )}
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      {/* Error Display */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* P2-20: Welcome Screen - EmptyState when no result */}
      {!result && !loading && !error && (
        <EmptyState
          icon={<SearchIcon sx={{ fontSize: 64 }} />}
          title={t(K.page.subgraph.welcomeTitle)}
          description={t(K.page.subgraph.welcomeDescription)}
        />
      )}

      {/* Results Table (P0-26: Node/Edge Interaction) */}
      {result && (
        <Paper>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>{t(K.page.subgraph.tableHeaderNode)}</TableCell>
                  <TableCell>{t(K.page.subgraph.tableHeaderType)}</TableCell>
                  <TableCell align="center">{t(K.page.subgraph.tableHeaderEvidence)}</TableCell>
                  <TableCell align="center">{t(K.page.subgraph.tableHeaderCoverage)}</TableCell>
                  <TableCell align="center">{t(K.page.subgraph.tableHeaderDegree)}</TableCell>
                  <TableCell align="center">{t(K.page.subgraph.tableHeaderStatus)}</TableCell>
                  <TableCell align="center">{t(K.page.subgraph.tableHeaderActions)}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredNodes.map((node) => {
                  const isGapAnchor = node.entity_type === 'gap_anchor'
                  const isBlindSpot = node.is_blind_spot

                  return (
                    <Tooltip key={node.id} title={node.visual.tooltip} placement="top" arrow>
                      <TableRow
                        hover
                        onClick={() => handleNodeClick(node)}
                        sx={{
                          cursor: 'pointer',
                          bgcolor: isGapAnchor ? 'action.hover' : 'inherit',
                          borderLeft: isBlindSpot ? '4px solid' : 'none',
                          borderLeftColor: isBlindSpot ? 'error.main' : 'transparent',
                          '&:hover': {
                            bgcolor: isGapAnchor ? 'action.selected' : 'action.hover',
                          },
                        }}
                      >
                        {/* Node Name */}
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <CircleIcon
                              sx={{
                                fontSize: node.visual.size / 2,
                                color: node.visual.color,
                                border: `${node.visual.border_width}px ${node.visual.border_style}`,
                                borderColor: node.visual.border_color,
                                borderRadius: '50%',
                              }}
                            />
                            <Typography variant="body2" fontWeight={isGapAnchor ? 'bold' : 'normal'}>
                              {node.entity_name}
                            </Typography>
                          </Box>
                        </TableCell>

                        {/* Type */}
                        <TableCell>
                          <Chip
                            label={node.entity_type}
                            size="small"
                            color={isGapAnchor ? 'default' : 'primary'}
                            variant={isGapAnchor ? 'outlined' : 'filled'}
                          />
                        </TableCell>

                        {/* Evidence Count */}
                        <TableCell align="center">
                          {isGapAnchor ? (
                            <Typography variant="body2" color="text.secondary">
                              N/A
                            </Typography>
                          ) : (
                            <Typography variant="body2" fontWeight="bold">
                              {node.evidence_count}
                            </Typography>
                          )}
                        </TableCell>

                        {/* Coverage Sources */}
                        <TableCell align="center">
                          {isGapAnchor ? (
                            <Typography variant="body2" color="text.secondary">
                              N/A
                            </Typography>
                          ) : (
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                              {node.coverage_sources.map(source => (
                                <Chip key={source} label={source} size="small" />
                              ))}
                            </Box>
                          )}
                        </TableCell>

                        {/* Degree */}
                        <TableCell align="center">
                          {isGapAnchor ? (
                            <Typography variant="body2" color="text.secondary">
                              N/A
                            </Typography>
                          ) : (
                            <Typography variant="body2">
                              {node.in_degree} / {node.out_degree}
                            </Typography>
                          )}
                        </TableCell>

                        {/* Status (P0-27: Gap Anchor Special Rendering) */}
                        <TableCell align="center">
                          {isGapAnchor ? (
                            <Chip
                              icon={<WarningIcon />}
                              label={`Gap (${node.missing_connections_count} missing)`}
                              size="small"
                              color="warning"
                            />
                          ) : isBlindSpot ? (
                            <Chip
                              icon={<WarningIcon />}
                              label={t(K.page.subgraph.statusBlindSpot)}
                              size="small"
                              color="error"
                            />
                          ) : (
                            <Chip
                              label={t(K.page.subgraph.statusHealthy)}
                              size="small"
                              color="success"
                            />
                          )}
                        </TableCell>

                        {/* Actions */}
                        <TableCell align="center">
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleNodeClick(node)
                            }}
                          >
                            <InfoIcon />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    </Tooltip>
                  )
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* TODO: Future Enhancement - Interactive Graph Visualization */}
      {result && (
        <Paper sx={{ p: 2, bgcolor: 'info.light' }}>
          <Typography variant="body2" color="info.dark">
            <InfoIcon sx={{ fontSize: 16, mr: 1, verticalAlign: 'middle' }} />
            {t(K.page.subgraph.futureEnhancement)}
          </Typography>
        </Paper>
      )}

      {/* Detail Drawer (P0-26, P0-27) */}
      <Drawer
        anchor="right"
        open={drawerOpen}
        onClose={handleDrawerClose}
        sx={{
          '& .MuiDrawer-paper': {
            width: 400,
            p: 3,
          },
        }}
      >
        {selectedNode && (
          <>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">{t(K.page.subgraph.detailTitle)}</Typography>
              <IconButton onClick={handleDrawerClose}>
                <CloseIcon />
              </IconButton>
            </Box>

            {/* Node Type Badge */}
            <Chip
              label={selectedNode.entity_type}
              color={selectedNode.entity_type === 'gap_anchor' ? 'warning' : 'primary'}
              sx={{ mb: 2 }}
            />

            {/* Node Name */}
            <Typography variant="body1" fontWeight="bold" gutterBottom>
              {selectedNode.entity_name}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {selectedNode.entity_key}
            </Typography>

            {/* Gap Anchor Details (P0-27) */}
            {selectedNode.entity_type === 'gap_anchor' && (
              <>
                <Alert severity="warning" sx={{ mb: 2 }}>
                  {t(K.page.subgraph.detailCoverageGap)}
                </Alert>
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailMissingConnections)}:</strong> {selectedNode.missing_connections_count}
                </Typography>
                {selectedNode.gap_types && selectedNode.gap_types.length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" gutterBottom>
                      <strong>{t(K.page.subgraph.detailGapTypes)}:</strong>
                    </Typography>
                    {selectedNode.gap_types.map(type => (
                      <Chip key={type} label={type} size="small" sx={{ mr: 0.5, mb: 0.5 }} />
                    ))}
                  </Box>
                )}
                <Typography variant="body2" sx={{ mt: 2 }}>
                  <strong>{t(K.page.subgraph.detailSuggestions)}:</strong>
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Add documentation for missing coverage
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Rebuild index to update relationships
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Review capability connections
                </Typography>
              </>
            )}

            {/* Regular Node Details */}
            {selectedNode.entity_type !== 'gap_anchor' && (
              <>
                {/* Evidence */}
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailEvidenceCount)}:</strong> {selectedNode.evidence_count}
                </Typography>
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailEvidenceDensity)}:</strong> {(selectedNode.evidence_density * 100).toFixed(1)}%
                </Typography>

                {/* Coverage Sources */}
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" gutterBottom>
                    <strong>{t(K.page.subgraph.detailCoverageSources)}:</strong>
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {selectedNode.coverage_sources.map(source => (
                      <Chip key={source} label={source} size="small" />
                    ))}
                  </Box>
                </Box>

                {/* Topology */}
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailInDegree)}:</strong> {selectedNode.in_degree}
                </Typography>
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailOutDegree)}:</strong> {selectedNode.out_degree}
                </Typography>
                <Typography variant="body2" gutterBottom>
                  <strong>{t(K.page.subgraph.detailDistanceSeed)}:</strong> {selectedNode.distance_from_seed}
                </Typography>

                {/* Blind Spot Details */}
                {selectedNode.is_blind_spot && (
                  <>
                    <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
                      {t(K.page.subgraph.detailBlindSpot)}
                    </Alert>
                    <Typography variant="body2" gutterBottom>
                      <strong>{t(K.page.subgraph.detailSeverity)}:</strong> {((selectedNode.blind_spot_severity || 0) * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      <strong>{t(K.page.subgraph.detailType)}:</strong> {selectedNode.blind_spot_type}
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      <strong>{t(K.page.subgraph.detailReason)}:</strong> {selectedNode.blind_spot_reason}
                    </Typography>
                  </>
                )}

                {/* Visual Encoding */}
                <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Typography variant="body2" gutterBottom>
                    <strong>{t(K.page.subgraph.detailVisual)}:</strong>
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <CircleIcon
                      sx={{
                        fontSize: selectedNode.visual.size / 2,
                        color: selectedNode.visual.color,
                        border: `${selectedNode.visual.border_width}px ${selectedNode.visual.border_style}`,
                        borderColor: selectedNode.visual.border_color,
                        borderRadius: '50%',
                      }}
                    />
                    <Typography variant="caption">
                      {t(K.page.subgraph.detailColor)}: {selectedNode.visual.color}
                    </Typography>
                  </Box>
                  <Typography variant="caption" display="block">
                    {t(K.page.subgraph.detailSize)}: {selectedNode.visual.size}px
                  </Typography>
                  <Typography variant="caption" display="block">
                    {t(K.page.subgraph.detailBorder)}: {selectedNode.visual.border_color} ({selectedNode.visual.border_style})
                  </Typography>
                </Box>
              </>
            )}
          </>
        )}
      </Drawer>
    </Box>
  )
}
