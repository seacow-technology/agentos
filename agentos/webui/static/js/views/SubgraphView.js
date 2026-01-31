/**
 * SubgraphView - Subgraph Visualization View
 *
 * Core Responsibilities:
 * 1. Query subgraph data (call /api/brain/subgraph)
 * 2. Render visual graph (Cytoscape.js)
 * 3. Apply visual encoding (colors, sizes, borders = cognitive attributes)
 * 4. Implement interactions (hover, click, zoom, filter)
 * 5. Display blind spots and blank areas
 *
 * IMPORTANT: This is NOT "drawing a knowledge graph", but "visualizing cognitive boundaries"
 *
 * Based on:
 * - P2_COGNITIVE_MODEL_DEFINITION.md
 * - P2_VISUAL_SEMANTICS_QUICK_REFERENCE.md
 * - P2_TASK3_API_REFERENCE.md
 */

class SubgraphView {
    constructor() {
        this.cy = null;  // Cytoscape instance
        this.currentSeed = null;
        this.currentKHop = 2;
        this.currentMinEvidence = 1;
        this.currentData = null;
        this.showBlindSpots = true;
        this.showWeakEdges = true;
    }

    /**
     * Initialize view
     */
    init() {
        console.log('[SubgraphView] Initializing...');

        // 1. Create DOM container
        this.createContainer();

        // 2. Initialize Cytoscape
        this.initCytoscape();

        // 3. Bind events
        this.bindEvents();

        // 4. Load default subgraph if seed provided in URL
        const urlParams = new URLSearchParams(window.location.search);
        const seed = urlParams.get('seed');
        if (seed) {
            this.loadSubgraph(seed);
        } else {
            this.showWelcome();
        }
    }

    /**
     * Create DOM structure
     */
    createContainer() {
        const container = document.getElementById('main-content');
        container.innerHTML = `
            <div class="subgraph-view h-full flex flex-col">
                <!-- Controls Bar -->
                <div class="subgraph-controls bg-gray-50 border-b border-gray-200 p-4">
                    <div class="flex flex-wrap gap-4 items-center">
                        <!-- Seed Input -->
                        <div class="flex-1 min-w-64">
                            <label for="seed-input" class="block text-xs font-medium text-gray-700 mb-1">
                                Seed Entity
                            </label>
                            <div class="flex gap-2">
                                <input
                                    type="text"
                                    id="seed-input"
                                    class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    placeholder="e.g., file:manager.py, capability:api"
                                    value="${this.currentSeed || ''}"
                                />
                                <button
                                    id="query-btn"
                                    class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                    Query
                                </button>
                            </div>
                        </div>

                        <!-- K-Hop Control -->
                        <div>
                            <label for="k-hop-slider" class="block text-xs font-medium text-gray-700 mb-1">
                                K-Hop: <span id="k-hop-value" class="text-blue-600 font-semibold">2</span>
                            </label>
                            <input
                                type="range"
                                id="k-hop-slider"
                                class="w-24"
                                min="1"
                                max="3"
                                value="2"
                            />
                        </div>

                        <!-- Min Evidence Control -->
                        <div>
                            <label for="min-evidence-slider" class="block text-xs font-medium text-gray-700 mb-1">
                                Min Evidence: <span id="min-evidence-value" class="text-blue-600 font-semibold">1</span>
                            </label>
                            <input
                                type="range"
                                id="min-evidence-slider"
                                class="w-24"
                                min="1"
                                max="10"
                                value="1"
                            />
                        </div>

                        <!-- Filters -->
                        <div class="flex gap-3">
                            <label class="inline-flex items-center text-sm text-gray-700">
                                <input type="checkbox" id="show-blind-spots" class="mr-2" checked />
                                Show Blind Spots
                            </label>
                            <label class="inline-flex items-center text-sm text-gray-700">
                                <input type="checkbox" id="show-weak-edges" class="mr-2" checked />
                                Show Weak Edges
                            </label>
                            <label class="inline-flex items-center text-sm text-gray-700">
                                <input type="checkbox" id="show-gaps" class="mr-2" checked />
                                Show Coverage Gaps
                            </label>
                        </div>

                        <!-- Gap Filter Buttons -->
                        <div>
                            <button id="gaps-only-btn" class="px-3 py-1 bg-orange-500 text-white rounded-md text-xs font-medium hover:bg-orange-600">
                                Gaps Only
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Graph Container -->
                <div class="flex-1 relative">
                    <div id="cytoscape-container" class="w-full h-full bg-white"></div>

                    <!-- Welcome Screen -->
                    <div id="welcome-screen" class="absolute inset-0 flex items-center justify-center bg-gray-50">
                        <div class="text-center p-8">
                            <svg class="w-16 h-16 mx-auto text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                            </svg>
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">Cognitive Subgraph Visualization</h3>
                            <p class="text-sm text-gray-600 max-w-md">
                                Enter a seed entity to explore the cognitive structure. This is not just a knowledge graph -
                                it visualizes <strong>what is understood, what is weak, and what is missing</strong>.
                            </p>
                            <div class="mt-6 text-left max-w-md mx-auto">
                                <p class="text-xs font-medium text-gray-700 mb-2">Example seeds:</p>
                                <ul class="text-xs text-gray-600 space-y-1">
                                    <li><code class="bg-gray-100 px-2 py-1 rounded">file:manager.py</code></li>
                                    <li><code class="bg-gray-100 px-2 py-1 rounded">capability:api</code></li>
                                    <li><code class="bg-gray-100 px-2 py-1 rounded">term:authentication</code></li>
                                </ul>
                            </div>
                        </div>
                    </div>

                    <!-- Loading Overlay -->
                    <div id="loading-overlay" class="absolute inset-0 hidden items-center justify-center bg-white bg-opacity-90">
                        <div class="text-center">
                            <div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                            <p class="mt-4 text-sm text-gray-600">Loading subgraph...</p>
                        </div>
                    </div>

                    <!-- Legend -->
                    <div id="legend" class="absolute top-4 right-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs hidden">
                        <h4 class="text-sm font-semibold text-gray-800 mb-3">Legend</h4>

                        <div class="space-y-3 text-xs">
                            <div>
                                <p class="font-medium text-gray-700 mb-1">Node Colors (Coverage)</p>
                                <div class="space-y-1">
                                    <div class="flex items-center gap-2">
                                        <span class="w-4 h-4 rounded-full" style="background: #10b981;"></span>
                                        <span class="text-gray-600">3 sources (Git+Doc+Code)</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <span class="w-4 h-4 rounded-full" style="background: #3b82f6;"></span>
                                        <span class="text-gray-600">2 sources</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <span class="w-4 h-4 rounded-full" style="background: #f59e0b;"></span>
                                        <span class="text-gray-600">1 source</span>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <p class="font-medium text-gray-700 mb-1">Blind Spots</p>
                                <div class="flex items-center gap-2">
                                    <span class="w-4 h-4 rounded-full border-2 border-dashed" style="background: #ef4444; border-color: #dc2626;"></span>
                                    <span class="text-gray-600">Cognitive risk</span>
                                </div>
                            </div>

                            <div>
                                <p class="font-medium text-gray-700 mb-1">Edge Strength</p>
                                <div class="space-y-1">
                                    <div class="flex items-center gap-2">
                                        <div class="w-8 h-1" style="background: #10b981;"></div>
                                        <span class="text-gray-600">5+ evidence</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <div class="w-8 h-0.5" style="background: #9ca3af;"></div>
                                        <span class="text-gray-600">1-2 evidence</span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <div class="w-8 border-t border-dashed border-gray-400"></div>
                                        <span class="text-gray-600">Suspected edge</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Metadata Panel -->
                    <div id="metadata-panel" class="absolute bottom-4 left-4 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs hidden">
                        <h4 class="text-sm font-semibold text-gray-800 mb-3">Subgraph Metadata</h4>
                        <div id="metadata-content" class="text-xs space-y-1 text-gray-600"></div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Initialize Cytoscape instance
     */
    initCytoscape() {
        const container = document.getElementById('cytoscape-container');
        if (!container) {
            console.error('[SubgraphView] Cytoscape container not found');
            return;
        }

        this.cy = cytoscape({
            container: container,

            // Layout configuration (COSE - Compound Spring Embedder)
            layout: {
                name: 'cose',
                animate: true,
                animationDuration: 500,
                animationEasing: 'ease-out',

                // Evidence weight adjustment (CRITICAL!)
                // Edges with more evidence should be "stiffer" (shorter in the layout)
                edgeElasticity: (edge) => {
                    const evidenceCount = edge.data('evidence_count') || 1;
                    return 1 / Math.sqrt(evidenceCount);  // More evidence = stiffer spring
                },

                nodeRepulsion: 400000,
                idealEdgeLength: 100,
                gravity: 0.1,
                numIter: 1000,
                initialTemp: 200,
                coolingFactor: 0.95,
                minTemp: 1.0
            },

            // Style (following P2-1 visual semantics)
            style: [
                // Node styles
                {
                    selector: 'node',
                    style: {
                        'background-color': 'data(color)',
                        'width': 'data(size)',
                        'height': 'data(size)',
                        'label': 'data(label)',
                        'font-size': 12,
                        'font-family': 'sans-serif',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'text-wrap': 'wrap',
                        'text-max-width': 100,
                        'border-width': 'data(border_width)',
                        'border-color': 'data(border_color)',
                        'border-style': 'data(border_style)',
                        'color': '#374151',
                        'text-outline-color': '#ffffff',
                        'text-outline-width': 2
                    }
                },

                // Edge styles
                {
                    selector: 'edge',
                    style: {
                        'width': 'data(width)',
                        'line-color': 'data(color)',
                        'line-style': 'data(style)',
                        'opacity': 'data(opacity)',
                        'target-arrow-color': 'data(color)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': 9,
                        'text-rotation': 'autorotate',
                        'text-margin-y': -10,
                        'color': '#6b7280',
                        'text-background-color': '#ffffff',
                        'text-background-opacity': 0.8,
                        'text-background-padding': 2
                    }
                },

                // Blind spot node highlight (RED LINE 2)
                {
                    selector: 'node[is_blind_spot = "true"]',
                    style: {
                        'border-width': 3,
                        'border-color': '#dc2626',
                        'border-style': 'dashed'
                    }
                },

                // Gap Anchor Node styles (RED LINE 3)
                {
                    selector: 'node.gap-anchor',
                    style: {
                        'background-color': '#ffffff',  // White fill (empty)
                        'border-width': 2,
                        'border-color': '#9ca3af',  // Gray border
                        'border-style': 'dashed',  // Dashed border (clearly virtual)
                        'label': 'data(label)',
                        'font-size': 11,
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'shape': 'ellipse',  // Circle
                        'width': 'data(size)',
                        'height': 'data(size)',
                        'color': '#6b7280',  // Gray text
                        'text-outline-color': '#ffffff',
                        'text-outline-width': 2
                    }
                },

                // Gap Anchor selected/hover
                {
                    selector: 'node.gap-anchor:selected',
                    style: {
                        'overlay-color': '#f59e0b',  // Orange highlight
                        'overlay-opacity': 0.3,
                        'overlay-padding': 8
                    }
                },

                // Coverage Gap edge styles (RED LINE 3)
                {
                    selector: 'edge[edge_type = "coverage_gap"]',
                    style: {
                        'width': 1,
                        'line-color': '#9ca3af',  // Gray
                        'line-style': 'dashed',  // Dashed (clearly virtual)
                        'opacity': 0.6,
                        'target-arrow-shape': 'none',  // No arrow
                        'curve-style': 'bezier'
                    }
                },

                // Hover styles
                {
                    selector: 'node:selected',
                    style: {
                        'overlay-color': '#3b82f6',
                        'overlay-opacity': 0.3,
                        'overlay-padding': 10
                    }
                },
                {
                    selector: 'edge:selected',
                    style: {
                        'overlay-color': '#3b82f6',
                        'overlay-opacity': 0.3,
                        'overlay-padding': 5
                    }
                }
            ],

            // Interaction configuration
            minZoom: 0.3,
            maxZoom: 3.0,
            wheelSensitivity: 0.2,
            boxSelectionEnabled: false,
            autoungrabify: false,
            autounselectify: false
        });

        console.log('[SubgraphView] Cytoscape initialized');
    }

    /**
     * Load subgraph data
     */
    async loadSubgraph(seed, kHop = null, minEvidence = null) {
        try {
            // Use provided parameters or current values
            kHop = kHop !== null ? kHop : this.currentKHop;
            minEvidence = minEvidence !== null ? minEvidence : this.currentMinEvidence;

            console.log(`[SubgraphView] Loading subgraph: seed=${seed}, k_hop=${kHop}, min_evidence=${minEvidence}`);

            // 1. Show loading state
            this.showLoading();

            // 2. Call API
            const url = `/api/brain/subgraph?seed=${encodeURIComponent(seed)}&k_hop=${kHop}&min_evidence=${minEvidence}`;
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            // 3. Error handling
            if (!result.ok) {
                this.showError(result.error);
                return;
            }

            // 4. Save data
            this.currentData = result.data;
            this.currentSeed = seed;
            this.currentKHop = kHop;
            this.currentMinEvidence = minEvidence;

            // 5. Render graph
            this.renderSubgraph(result.data);

            // 6. Update metadata
            this.updateMetadata(result.data.metadata);

            // 7. Hide loading, show legend and metadata
            this.hideLoading();
            document.getElementById('legend').classList.remove('hidden');
            document.getElementById('metadata-panel').classList.remove('hidden');

            console.log(`[SubgraphView] Subgraph loaded: ${result.data.nodes.length} nodes, ${result.data.edges.length} edges`);
        } catch (error) {
            console.error('[SubgraphView] Failed to load subgraph:', error);
            this.showError(`Network error: ${error.message}`);
        }
    }

    /**
     * Render subgraph (CORE METHOD)
     */
    renderSubgraph(data) {
        console.log('[SubgraphView] Rendering subgraph...');

        // 1. Clear existing graph
        this.cy.elements().remove();

        // 2. Convert node data (following P2-1 visual encoding)
        const nodes = data.nodes.map(node => {
            // Check if this is a Gap Anchor Node
            const isGapAnchor = node.entity_type === 'gap_anchor';

            return {
                data: {
                    id: node.id,
                    label: node.visual.label.split('\n')[0],  // Use first line for label
                    color: node.visual.color,
                    size: node.visual.size,
                    border_width: node.visual.border_width,
                    border_color: node.visual.border_color,
                    border_style: node.visual.border_style,
                    is_blind_spot: node.is_blind_spot.toString(),
                    tooltip: node.visual.tooltip,

                    // Gap Anchor specific data
                    is_gap_anchor: isGapAnchor,
                    missing_count: node.missing_connections_count || 0,
                    gap_types: node.gap_types || [],
                    suggestions: node.suggestions || [],

                    // Raw data (for interactions)
                    entity_type: node.entity_type,
                    entity_key: node.entity_key,
                    entity_name: node.entity_name,
                    evidence_count: node.evidence_count,
                    coverage_sources: node.coverage_sources,
                    in_degree: node.in_degree,
                    out_degree: node.out_degree
                },

                // Add gap-anchor class for styling
                classes: isGapAnchor ? 'gap-anchor' : ''
            };
        });

        // 3. Convert edge data (following P2-1 visual encoding)
        const edges = data.edges
            .filter(edge => {
                // Apply filters
                if (!this.showWeakEdges && edge.is_weak) return false;
                return true;
            })
            .map(edge => ({
                data: {
                    id: edge.id,
                    source: edge.source_id,
                    target: edge.target_id,
                    label: '',  // Hide label by default (too cluttered)
                    width: edge.visual.width,
                    color: edge.visual.color,
                    style: edge.visual.style,
                    opacity: edge.visual.opacity,
                    tooltip: edge.visual.tooltip,

                    // Raw data
                    edge_type: edge.edge_type,
                    evidence_count: edge.evidence_count,
                    evidence_types: edge.evidence_types,
                    confidence: edge.confidence
                }
            }));

        // 4. Add to Cytoscape
        this.cy.add([...nodes, ...edges]);

        // 5. Apply layout (Gap Anchor Nodes use special positioning)
        const layout = this.cy.layout({
            name: 'cose',
            animate: true,
            animationDuration: 500,
            edgeElasticity: (edge) => {
                // Skip virtual edges (coverage_gap) in evidence weighting
                if (edge.data('edge_type') === 'coverage_gap') {
                    return 0.1;  // Very weak spring (gap anchors float near parent)
                }
                const evidenceCount = edge.data('evidence_count') || 1;
                return 1 / Math.sqrt(evidenceCount);
            },
            nodeRepulsion: (node) => {
                // Gap Anchor Nodes have low repulsion (don't push other nodes)
                if (node.hasClass('gap-anchor')) {
                    return 10000;
                }
                return 400000;
            },
            idealEdgeLength: 100,
            gravity: 0.1
        });

        layout.run();

        // 6. Show missing connections if any (RED LINE 3)
        if (data.metadata.missing_connections_count > 0 && data.metadata.coverage_gaps) {
            this.showMissingConnections(data.metadata.coverage_gaps);
        }

        console.log('[SubgraphView] Rendering complete');
    }

    /**
     * Show missing connections (RED LINE 3: Make blank areas visible)
     */
    showMissingConnections(coverageGaps) {
        console.log(`[SubgraphView] Showing ${coverageGaps.length} coverage gaps`);

        // For now, just log them (TODO: Add visual indicators)
        coverageGaps.forEach((gap, index) => {
            console.log(`  Gap ${index + 1}: ${gap.type} - ${gap.description}`);
        });
    }

    /**
     * Bind interaction events
     */
    bindEvents() {
        // Node hover
        this.cy.on('mouseover', 'node', (event) => {
            const node = event.target;
            this.showTooltip(node.data('tooltip'), event.renderedPosition);
        });

        this.cy.on('mouseout', 'node', () => {
            this.hideTooltip();
        });

        // Node click
        this.cy.on('tap', 'node', (event) => {
            const node = event.target;
            this.handleNodeClick(node);
        });

        // Edge hover
        this.cy.on('mouseover', 'edge', (event) => {
            const edge = event.target;
            this.showTooltip(edge.data('tooltip'), event.renderedPosition);
        });

        this.cy.on('mouseout', 'edge', () => {
            this.hideTooltip();
        });

        // Query button
        document.getElementById('query-btn').addEventListener('click', () => {
            const seed = document.getElementById('seed-input').value.trim();
            if (seed) {
                this.loadSubgraph(seed, this.currentKHop, this.currentMinEvidence);
            } else {
                Dialog.alert('Please enter a seed entity (e.g., file:manager.py)', { title: 'Validation Error' });
            }
        });

        // Enter key in seed input
        document.getElementById('seed-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('query-btn').click();
            }
        });

        // K-Hop slider
        document.getElementById('k-hop-slider').addEventListener('input', (e) => {
            const value = e.target.value;
            document.getElementById('k-hop-value').textContent = value;
            this.currentKHop = parseInt(value);
        });

        // Min evidence slider
        document.getElementById('min-evidence-slider').addEventListener('input', (e) => {
            const value = e.target.value;
            document.getElementById('min-evidence-value').textContent = value;
            this.currentMinEvidence = parseInt(value);
        });

        // Filter checkboxes
        document.getElementById('show-blind-spots').addEventListener('change', (e) => {
            this.showBlindSpots = e.target.checked;
            if (this.currentData) {
                this.renderSubgraph(this.currentData);
            }
        });

        document.getElementById('show-weak-edges').addEventListener('change', (e) => {
            this.showWeakEdges = e.target.checked;
            if (this.currentData) {
                this.renderSubgraph(this.currentData);
            }
        });

        // Show/hide coverage gaps
        document.getElementById('show-gaps').addEventListener('change', (e) => {
            const showGaps = e.target.checked;
            this.toggleGaps(showGaps);
        });

        // Gaps Only button
        document.getElementById('gaps-only-btn').addEventListener('click', () => {
            this.showGapsOnly();
        });

        // Gap Anchor Node click event
        this.cy.on('tap', 'node.gap-anchor', (event) => {
            const node = event.target;
            this.showGapDetails(node);
            event.stopPropagation();  // Don't trigger normal node click
        });

        // Gap Anchor Node hover event
        this.cy.on('mouseover', 'node.gap-anchor', (event) => {
            const node = event.target;
            const data = node.data();
            this.showTooltip(data.tooltip, event.renderedPosition);
        });
    }

    /**
     * Handle node click
     */
    handleNodeClick(node) {
        const data = node.data();
        console.log('[SubgraphView] Node clicked:', data.entity_type, data.entity_key);

        // Option 1: Re-query with this node as seed
        const newSeed = `${data.entity_type}:${data.entity_key}`;
        this.loadSubgraph(newSeed);

        // Update seed input
        document.getElementById('seed-input').value = newSeed;
    }

    /**
     * Update metadata panel
     */
    updateMetadata(metadata) {
        const container = document.getElementById('metadata-content');

        const coverageClass = metadata.coverage_percentage >= 0.8 ? 'text-green-600' :
                             metadata.coverage_percentage >= 0.5 ? 'text-yellow-600' : 'text-red-600';

        container.innerHTML = `
            <div><strong>Seed:</strong> ${metadata.seed_entity}</div>
            <div><strong>K-Hop:</strong> ${metadata.k_hop}</div>
            <div><strong>Nodes:</strong> ${metadata.total_nodes}</div>
            <div><strong>Edges:</strong> ${metadata.total_edges} (${metadata.confirmed_edges} confirmed, ${metadata.suspected_edges} suspected)</div>
            <div><strong>Coverage:</strong> <span class="${coverageClass} font-semibold">${(metadata.coverage_percentage * 100).toFixed(1)}%</span></div>
            <div><strong>Evidence Density:</strong> ${metadata.evidence_density.toFixed(1)} per edge</div>
            <div><strong>Blind Spots:</strong> ${metadata.blind_spot_count} (${metadata.high_risk_blind_spot_count} high risk)</div>
            <div><strong>Missing Connections:</strong> ${metadata.missing_connections_count}</div>
        `;
    }

    /**
     * Show tooltip
     */
    showTooltip(text, position) {
        let tooltip = document.getElementById('cy-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'cy-tooltip';
            tooltip.className = 'absolute bg-gray-900 text-white text-xs rounded px-3 py-2 pointer-events-none z-50';
            tooltip.style.maxWidth = '300px';
            document.body.appendChild(tooltip);
        }

        tooltip.innerHTML = text.replace(/\n/g, '<br>');
        tooltip.style.left = `${position.x + 10}px`;
        tooltip.style.top = `${position.y + 10}px`;
        tooltip.classList.remove('hidden');
    }

    /**
     * Hide tooltip
     */
    hideTooltip() {
        const tooltip = document.getElementById('cy-tooltip');
        if (tooltip) {
            tooltip.classList.add('hidden');
        }
    }

    /**
     * Show welcome screen
     */
    showWelcome() {
        document.getElementById('welcome-screen').classList.remove('hidden');
        document.getElementById('legend').classList.add('hidden');
        document.getElementById('metadata-panel').classList.add('hidden');
    }

    /**
     * Hide welcome screen
     */
    hideWelcome() {
        document.getElementById('welcome-screen').classList.add('hidden');
    }

    /**
     * Show loading overlay
     */
    showLoading() {
        this.hideWelcome();
        const overlay = document.getElementById('loading-overlay');
        overlay.classList.remove('hidden');
        overlay.classList.add('flex');
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        overlay.classList.add('hidden');
        overlay.classList.remove('flex');
    }

    /**
     * Show error message
     */
    showError(message) {
        this.hideLoading();

        const container = document.getElementById('cytoscape-container');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'absolute inset-0 flex items-center justify-center bg-red-50';
        errorDiv.innerHTML = `
            <div class="text-center p-8 max-w-md">
                <svg class="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 class="text-lg font-semibold text-gray-800 mb-2">Failed to Load Subgraph</h3>
                <p class="text-sm text-gray-600 mb-4">${message}</p>
                <button
                    onclick="document.getElementById('seed-input').focus()"
                    class="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700"
                >
                    Try Again
                </button>
            </div>
        `;
        container.appendChild(errorDiv);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
            this.showWelcome();
        }, 5000);
    }

    /**
     * Toggle Gap Anchor Nodes visibility
     */
    toggleGaps(show) {
        if (!this.cy) return;

        if (show) {
            this.cy.nodes('.gap-anchor').show();
            this.cy.edges('[edge_type = "coverage_gap"]').show();
        } else {
            this.cy.nodes('.gap-anchor').hide();
            this.cy.edges('[edge_type = "coverage_gap"]').hide();
        }
    }

    /**
     * Show only Gap Anchor Nodes (hide everything else)
     */
    showGapsOnly() {
        if (!this.cy) return;

        // Hide all normal nodes and edges
        this.cy.nodes(':not(.gap-anchor)').hide();
        this.cy.edges('[edge_type != "coverage_gap"]').hide();

        // Show all Gap Anchor Nodes and coverage_gap edges
        this.cy.nodes('.gap-anchor').show();
        this.cy.edges('[edge_type = "coverage_gap"]').show();

        // Re-run layout with only gap nodes
        const layout = this.cy.layout({
            name: 'cose',
            animate: true,
            animationDuration: 500
        });
        layout.run();
    }

    /**
     * Show Gap Anchor Node details in modal
     */
    showGapDetails(gapNode) {
        const data = gapNode.data();

        console.log('[SubgraphView] Showing gap details:', data);

        // Format gap types for display
        const formattedTypes = data.gap_types.map(type => this.formatGapType(type));

        // Create modal HTML
        const modalHtml = `
            <div class="gap-details-modal">
                <h3>Coverage Gap Details</h3>
                <p><strong>Missing Connections:</strong> ${data.missing_count}</p>

                <h4>Gap Types:</h4>
                <ul>
                    ${formattedTypes.map(type => `<li>${type}</li>`).join('')}
                </ul>

                <h4>Suggested Actions:</h4>
                <ul>
                    ${data.suggestions.map(s => `<li>${s}</li>`).join('')}
                </ul>

                <button onclick="window.subgraphView.closeGapDetails()">Close</button>
            </div>
        `;

        // Remove existing modal if any
        const existingModal = document.getElementById('gap-details-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Create and show modal
        const modal = document.createElement('div');
        modal.id = 'gap-details-modal';
        modal.className = 'modal';
        modal.innerHTML = modalHtml;
        document.body.appendChild(modal);

        // Store reference for global access
        window.subgraphView = this;
    }

    /**
     * Close Gap Details modal
     */
    closeGapDetails() {
        const modal = document.getElementById('gap-details-modal');
        if (modal) {
            modal.remove();
        }
    }

    /**
     * Format gap type to user-friendly string
     */
    formatGapType(type) {
        const typeMap = {
            'missing_doc_coverage': 'Missing Documentation',
            'missing_intra_capability': 'Missing Capability Connection',
            'missing_suspected_dependency': 'Missing Suspected Dependency',
            'missing_documentation_edge': 'Missing Documentation for High-Impact Component'
        };
        return typeMap[type] || type;
    }

    /**
     * Cleanup view
     */
    cleanup() {
        console.log('[SubgraphView] Cleaning up...');
        if (this.cy) {
            this.cy.destroy();
            this.cy = null;
        }

        const tooltip = document.getElementById('cy-tooltip');
        if (tooltip) {
            tooltip.remove();
        }

        const modal = document.getElementById('gap-details-modal');
        if (modal) {
            modal.remove();
        }
    }
}

// Register view globally
window.SubgraphView = SubgraphView;
