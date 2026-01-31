/**
 * EvidenceChainView - AgentOS v3 Evidence Chain Visualization
 *
 * Task #29: Graph visualization of evidence chains
 *
 * Features:
 * - Graph display using Cytoscape.js
 * - Nodes: Decision, Action, Memory, StateChange
 * - Edges: caused_by, resulted_in, modified
 * - Click node to view details
 * - Replay button for evidence chain
 * - Search for chain by ID
 */

class EvidenceChainView {
    constructor(container) {
        this.container = container;
        this.cy = null;
        this.chainData = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="evidence-chain-view">
                <div class="view-header">
                    <div>
                        <h1>Evidence Chain Viewer</h1>
                        <p class="text-sm text-gray-600 mt-1">Visualize evidence chains and dependencies</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-secondary" id="ec-replay" disabled>
                            <span class="icon"><span class="material-icons md-18">replay</span></span> Replay Chain
                        </button>
                    </div>
                </div>

                <!-- Search Bar -->
                <div class="search-bar">
                    <div class="search-input-group">
                        <span class="material-icons md-18">search</span>
                        <input type="text" id="ec-search-input" class="search-input" placeholder="Enter Chain ID (e.g., chain-xxx)">
                        <button class="btn-primary" id="ec-search-btn">Load Chain</button>
                    </div>
                    <div class="search-help">
                        <span class="material-icons md-14">info</span>
                        <span>Enter a chain ID to visualize its evidence graph</span>
                    </div>
                </div>

                <!-- Graph Container -->
                <div class="graph-container">
                    <div id="ec-graph" class="evidence-graph">
                        <!-- Cytoscape graph will be rendered here -->
                    </div>
                    <div class="graph-controls">
                        <button class="control-btn" id="ec-fit" title="Fit to Screen">
                            <span class="material-icons md-24">fit_screen</span>
                        </button>
                        <button class="control-btn" id="ec-center" title="Center Graph">
                            <span class="material-icons md-24">center_focus_strong</span>
                        </button>
                        <button class="control-btn" id="ec-zoom-in" title="Zoom In">
                            <span class="material-icons md-24">add</span>
                        </button>
                        <button class="control-btn" id="ec-zoom-out" title="Zoom Out">
                            <span class="material-icons md-24">remove</span>
                        </button>
                    </div>
                </div>

                <!-- Info Panel -->
                <div class="info-panel" id="ec-info-panel">
                    <div class="info-placeholder">
                        <span class="material-icons md-48">account_tree</span>
                        <p>Load a chain or click on a node to view details</p>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.initCytoscape();
    }

    setupEventListeners() {
        // Search button
        const searchBtn = this.container.querySelector('#ec-search-btn');
        const searchInput = this.container.querySelector('#ec-search-input');

        if (searchBtn) {
            searchBtn.addEventListener('click', () => {
                const chainId = searchInput.value.trim();
                if (chainId) {
                    this.loadChain(chainId);
                }
            });
        }

        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const chainId = searchInput.value.trim();
                    if (chainId) {
                        this.loadChain(chainId);
                    }
                }
            });
        }

        // Replay button
        const replayBtn = this.container.querySelector('#ec-replay');
        if (replayBtn) {
            replayBtn.addEventListener('click', () => {
                if (this.chainData) {
                    this.replayChain(this.chainData.chain_id);
                }
            });
        }

        // Graph controls
        const fitBtn = this.container.querySelector('#ec-fit');
        const centerBtn = this.container.querySelector('#ec-center');
        const zoomInBtn = this.container.querySelector('#ec-zoom-in');
        const zoomOutBtn = this.container.querySelector('#ec-zoom-out');

        if (fitBtn) fitBtn.addEventListener('click', () => this.cy && this.cy.fit());
        if (centerBtn) centerBtn.addEventListener('click', () => this.cy && this.cy.center());
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => this.cy && this.cy.zoom(this.cy.zoom() * 1.2));
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => this.cy && this.cy.zoom(this.cy.zoom() * 0.8));
    }

    initCytoscape() {
        const container = this.container.querySelector('#ec-graph');
        if (!container) return;

        // Check if Cytoscape is available
        if (typeof cytoscape === 'undefined') {
            console.error('Cytoscape.js not loaded');
            container.innerHTML = `
                <div class="error-state">
                    <span class="material-icons md-48">error_outline</span>
                    <p>Cytoscape.js library not loaded</p>
                </div>
            `;
            return;
        }

        this.cy = cytoscape({
            container: container,
            elements: [],
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': '#3b82f6',
                        'label': 'data(label)',
                        'width': 60,
                        'height': 60,
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'color': '#1f2937',
                        'font-size': '12px',
                        'text-wrap': 'wrap',
                        'text-max-width': '80px',
                        'border-width': 2,
                        'border-color': '#1e40af'
                    }
                },
                {
                    selector: 'node[type="decision"]',
                    style: {
                        'background-color': '#8b5cf6',
                        'border-color': '#6d28d9'
                    }
                },
                {
                    selector: 'node[type="action"]',
                    style: {
                        'background-color': '#f59e0b',
                        'border-color': '#d97706'
                    }
                },
                {
                    selector: 'node[type="memory"]',
                    style: {
                        'background-color': '#10b981',
                        'border-color': '#059669'
                    }
                },
                {
                    selector: 'node[type="state_change"]',
                    style: {
                        'background-color': '#06b6d4',
                        'border-color': '#0891b2'
                    }
                },
                {
                    selector: 'node[root]',
                    style: {
                        'border-width': 4,
                        'border-color': '#ef4444'
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'width': 2,
                        'line-color': '#94a3b8',
                        'target-arrow-color': '#94a3b8',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'label': 'data(label)',
                        'font-size': '10px',
                        'color': '#64748b',
                        'text-rotation': 'autorotate',
                        'text-margin-y': -10
                    }
                },
                {
                    selector: ':selected',
                    style: {
                        'background-color': '#ef4444',
                        'line-color': '#ef4444',
                        'target-arrow-color': '#ef4444',
                        'border-color': '#b91c1c'
                    }
                }
            ],
            layout: {
                name: 'breadthfirst',
                directed: true,
                spacingFactor: 1.5
            }
        });

        // Node click event
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            this.showNodeDetails(node.data());
        });
    }

    async loadChain(chainId) {
        try {
            const response = await fetch(`/api/capability/evidence/chain/${chainId}`);
            const result = await response.json();

            if (result.ok && result.data) {
                this.chainData = result.data;
                this.renderGraph(result.data);

                // Enable replay button
                const replayBtn = this.container.querySelector('#ec-replay');
                if (replayBtn) {
                    replayBtn.disabled = false;
                }
            } else {
                this.renderError(result.error || 'Failed to load evidence chain');
            }
        } catch (error) {
            console.error('Failed to load evidence chain:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderGraph(data) {
        if (!this.cy) return;

        // Clear existing graph
        this.cy.elements().remove();

        // Add nodes and edges
        this.cy.add(data.nodes);
        this.cy.add(data.edges);

        // Layout the graph
        this.cy.layout({
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.5,
            avoidOverlap: true,
            nodeDimensionsIncludeLabels: true
        }).run();

        // Fit to screen
        this.cy.fit();

        // Update info panel
        this.showChainInfo(data);
    }

    showChainInfo(data) {
        const infoPanel = this.container.querySelector('#ec-info-panel');
        if (!infoPanel) return;

        infoPanel.innerHTML = `
            <div class="chain-info">
                <h3>Evidence Chain</h3>
                <div class="info-row">
                    <strong>Chain ID:</strong>
                    <code>${data.chain_id}</code>
                </div>
                <div class="info-row">
                    <strong>Chain Type:</strong>
                    <span class="chain-type">${data.chain_type}</span>
                </div>
                <div class="info-row">
                    <strong>Nodes:</strong>
                    <span>${data.nodes.length}</span>
                </div>
                <div class="info-row">
                    <strong>Edges:</strong>
                    <span>${data.edges.length}</span>
                </div>
                <div class="info-row">
                    <strong>Created At:</strong>
                    <span>${this.formatTimestamp(data.created_at)}</span>
                </div>
            </div>
            <div class="legend">
                <h4>Legend</h4>
                <div class="legend-item">
                    <span class="legend-color" style="background-color: #8b5cf6;"></span>
                    <span>Decision</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background-color: #f59e0b;"></span>
                    <span>Action</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background-color: #10b981;"></span>
                    <span>Memory</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background-color: #06b6d4;"></span>
                    <span>State Change</span>
                </div>
            </div>
        `;
    }

    showNodeDetails(nodeData) {
        const infoPanel = this.container.querySelector('#ec-info-panel');
        if (!infoPanel) return;

        infoPanel.innerHTML = `
            <div class="node-details">
                <h3>Node Details</h3>
                <div class="info-row">
                    <strong>ID:</strong>
                    <code>${nodeData.id}</code>
                </div>
                <div class="info-row">
                    <strong>Type:</strong>
                    <span class="node-type type-${nodeData.type}">${nodeData.type}</span>
                </div>
                <div class="info-row">
                    <strong>Label:</strong>
                    <span>${nodeData.label}</span>
                </div>
                ${nodeData.root ? `
                    <div class="info-row">
                        <strong>Root Node:</strong>
                        <span class="text-red-600">✓</span>
                    </div>
                ` : ''}
            </div>
            <div class="node-actions">
                <button class="btn-secondary btn-sm" onclick="window.viewNodeFullDetails('${nodeData.id}')">
                    View Full Details
                </button>
            </div>
        `;
    }

    renderError(message) {
        const graphContainer = this.container.querySelector('#ec-graph');
        if (graphContainer) {
            graphContainer.innerHTML = `
                <div class="error-state">
                    <span class="material-icons md-48">error_outline</span>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    replayChain(chainId) {
        alert(`Replay evidence chain: ${chainId}\n\n(Replay functionality to be implemented)`);
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    destroy() {
        if (this.cy) {
            this.cy.destroy();
        }
    }
}

// Global function for node details
window.viewNodeFullDetails = function(nodeId) {
    alert(`View full details for node: ${nodeId}\n\n(Details modal to be implemented)`);
};

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EvidenceChainView;
}
