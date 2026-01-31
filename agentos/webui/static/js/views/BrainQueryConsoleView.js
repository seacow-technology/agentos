/**
 * BrainQueryConsoleView - BrainOS Query Console
 *
 * Unified query interface for BrainOS:
 * - Why Query: Trace entity origins
 * - Impact Query: Analyze downstream dependencies
 * - Trace Query: Track evolution timeline
 * - Map Query: Extract subgraph
 */

class BrainQueryConsoleView {
    constructor(container) {
        this.container = container;
        this.currentTab = 'why';
        this.currentResult = null;
        this.debounceTimer = null;
        this.selectedIndex = -1;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="brain-query-console">
                <div class="view-header">
                    <h1>Brain Query Console</h1>
                    <p class="text-sm text-gray-600 mt-1">Explore the knowledge graph with powerful queries</p>
                    <div class="header-actions">
                        <button class="btn-secondary" id="brain-back-to-dashboard">
                            <span class="icon"><span class="material-icons md-18">arrow_back</span></span> Dashboard
                        </button>
                    </div>
                </div>

                <div class="query-tabs">
                    <button class="tab active" data-tab="why">
                        <span class="material-icons md-18">help_outline</span> Why
                    </button>
                    <button class="tab" data-tab="impact">
                        <span class="material-icons md-18">account_tree</span> Impact
                    </button>
                    <button class="tab" data-tab="trace">
                        <span class="material-icons md-18">analytics</span> Trace
                    </button>
                    <button class="tab" data-tab="map">
                        <span class="material-icons md-18">map</span> Map
                    </button>
                </div>

                <div class="query-input-section">
                    <div class="input-group">
                        <div class="seed-input-container">
                            <input
                                type="text"
                                id="query-seed"
                                class="query-input"
                                placeholder="Enter file:path, doc:name, term:keyword, or capability:name"
                                autocomplete="off"
                            />
                            <div id="autocomplete-dropdown" class="autocomplete-dropdown" style="display: none;"></div>
                        </div>
                        <button class="btn-primary" id="query-btn">
                            <span class="material-icons md-18">search</span> Query
                        </button>
                    </div>
                    <div class="query-hints" id="query-hints">
                        ${this.renderHints('why')}
                    </div>
                </div>

                <div class="query-results" id="query-results">
                    <div class="empty-state">
                        <span class="material-icons md-48">search</span>
                        <p>Enter a query to explore the knowledge graph</p>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Tab switching
        const tabs = this.container.querySelectorAll('.tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                this.switchTab(tabName);
            });
        });

        // Query button
        const queryBtn = this.container.querySelector('#query-btn');
        if (queryBtn) {
            queryBtn.addEventListener('click', () => this.executeQuery());
        }

        // Enter key in input
        const queryInput = this.container.querySelector('#query-seed');
        if (queryInput) {
            queryInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const dropdown = this.container.querySelector('#autocomplete-dropdown');
                    if (dropdown && dropdown.style.display === 'block' && this.selectedIndex >= 0) {
                        e.preventDefault();
                        this.selectAutocompleteItem(this.selectedIndex);
                    } else {
                        this.executeQuery();
                    }
                }
            });

            // Autocomplete input handling
            queryInput.addEventListener('input', (e) => {
                this.handleAutocompleteInput(e.target.value);
            });

            // Keyboard navigation
            queryInput.addEventListener('keydown', (e) => {
                this.handleAutocompleteKeydown(e);
            });

            // Hide autocomplete on blur
            queryInput.addEventListener('blur', () => {
                setTimeout(() => this.hideAutocomplete(), 200);
            });
        }

        // Back to dashboard
        const backBtn = this.container.querySelector('#brain-back-to-dashboard');
        if (backBtn) {
            backBtn.addEventListener('click', () => loadView('brain-dashboard'));
        }
    }

    switchTab(tabName) {
        this.currentTab = tabName;

        // Update tab active state
        const tabs = this.container.querySelectorAll('.tab');
        tabs.forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Update hints
        const hintsEl = this.container.querySelector('#query-hints');
        if (hintsEl) {
            hintsEl.innerHTML = this.renderHints(tabName);
        }

        // Clear previous results
        this.currentResult = null;
        const resultsEl = this.container.querySelector('#query-results');
        if (resultsEl) {
            resultsEl.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">search</span>
                    <p>Enter a query to explore the knowledge graph</p>
                </div>
            `;
        }
    }

    renderHints(tabName) {
        const hints = {
            why: `
                <p><strong>Why Query</strong> traces entity origins:</p>
                <ul>
                    <li><code>file:agentos/core/task/manager.py</code> - Why this file exists</li>
                    <li><code>capability:retry_with_backoff</code> - Why this capability exists</li>
                    <li><code>term:ExecutionBoundary</code> - Why this term is important</li>
                </ul>
            `,
            impact: `
                <p><strong>Impact Query</strong> analyzes downstream dependencies:</p>
                <ul>
                    <li><code>file:agentos/core/task/models.py</code> - What depends on this file</li>
                    <li><code>doc:ADR_TASK_STATE_MACHINE.md</code> - What implements this design</li>
                </ul>
            `,
            trace: `
                <p><strong>Trace Query</strong> tracks evolution over time:</p>
                <ul>
                    <li><code>file:agentos/core/executor/executor_engine.py</code> - How this file evolved</li>
                    <li><code>capability:pipeline_runner</code> - How this capability was built</li>
                </ul>
            `,
            map: `
                <p><strong>Map Query</strong> extracts subgraph neighborhood:</p>
                <ul>
                    <li><code>file:agentos/core/brain/service/query_why.py</code> - Show related entities</li>
                    <li><code>term:BrainOS</code> - Show all connected nodes</li>
                </ul>
            `
        };

        return hints[tabName] || '';
    }

    async executeQuery() {
        const input = this.container.querySelector('#query-seed');
        if (!input) return;

        const seed = input.value.trim();
        if (!seed) {
            Dialog.alert('Please enter a query seed', { title: 'Validation Error' });
            return;
        }

        // Show loading state
        const resultsEl = this.container.querySelector('#query-results');
        if (resultsEl) {
            resultsEl.innerHTML = `
                <div class="loading-state">
                    <span class="material-icons md-48">refresh</span>
                    <p>Querying knowledge graph...</p>
                </div>
            `;
        }

        try {
            const endpoint = `/api/brain/query/${this.currentTab}`;
            // CSRF Fix: Use fetchWithCSRF for protected endpoint
            const response = await window.fetchWithCSRF(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed })
            });

            const result = await response.json();

            if (result.ok && result.data) {
                this.currentResult = result.data;
                this.renderResults();
            } else {
                this.renderError(result.error || 'Query failed');
            }
        } catch (error) {
            console.error('Query failed:', error);
            this.renderError('Failed to execute query: ' + error.message);
        }
    }

    renderResults() {
        const resultsEl = this.container.querySelector('#query-results');
        if (!resultsEl || !this.currentResult) return;

        const queryType = this.currentResult.query_type;

        let html = `
            <div class="query-result-header">
                <h3>Query Results</h3>
                <div class="result-meta">
                    <span class="meta-item">
                        <span class="material-icons md-18">account_tree</span>
                        ${this.currentResult.graph_version || 'unknown'}
                    </span>
                    <span class="meta-item">
                        <span class="material-icons md-18">analytics</span>
                        ${this.currentResult.summary || 'No summary'}
                    </span>
                </div>
            </div>
        `;

        if (queryType === 'why') {
            html += this.renderWhyResults();
        } else if (queryType === 'impact') {
            html += this.renderImpactResults();
        } else if (queryType === 'trace') {
            html += this.renderTraceResults();
        } else if (queryType === 'map') {
            html += this.renderMapResults();
        }

        resultsEl.innerHTML = html;
    }

    renderWhyResults() {
        const paths = this.currentResult.paths || [];

        if (paths.length === 0) {
            return `
                <div class="empty-state">
                    <span class="material-icons md-48">help_outline</span>
                    <p>No origin paths found for this entity</p>
                </div>
            `;
        }

        const pathsHtml = paths.slice(0, 10).map((path, index) => {
            const nodes = path.nodes || [];
            const edges = path.edges || [];

            const nodesHtml = nodes.map((node, i) => {
                const url = node.url;
                const iconHtml = `<span class="material-icons md-18">${node.icon || 'help_outline'}</span>`;

                let nodeHtml = `
                    <div class="path-node">
                        ${iconHtml}
                        <span class="node-name">${node.name}</span>
                        <span class="node-type">${node.type}</span>
                    </div>
                `;

                if (url) {
                    nodeHtml = `<a href="${url}" class="path-node-link">${nodeHtml}</a>`;
                }

                if (i < edges.length) {
                    const edgeLabel = edges[i].label || edges[i].type;
                    nodeHtml += `
                        <div class="path-arrow">
                            <span class="material-icons md-18">arrow_forward</span>
                            <span class="edge-label">${edgeLabel}</span>
                        </div>
                    `;
                }

                return nodeHtml;
            }).join('');

            return `
                <div class="path-card">
                    <div class="path-header">
                        <strong>Path #${index + 1}</strong>
                    </div>
                    <div class="path-content">
                        ${nodesHtml}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="paths-container">
                ${pathsHtml}
                ${paths.length > 10 ? `<p class="text-muted text-center">Showing 10 of ${paths.length} paths</p>` : ''}
            </div>
        `;
    }

    renderImpactResults() {
        const affectedNodes = this.currentResult.affected_nodes || [];
        const riskHints = this.currentResult.risk_hints || [];

        if (affectedNodes.length === 0) {
            return `
                <div class="empty-state">
                    <span class="material-icons md-48">check_circle</span>
                    <p>No downstream dependencies found</p>
                </div>
            `;
        }

        const nodesHtml = affectedNodes.map(node => `
            <div class="affected-node-card">
                <span class="material-icons md-18">${node.icon || 'description'}</span>
                <div class="node-info">
                    <strong>${node.name}</strong>
                    <span class="node-type">${node.type}</span>
                </div>
            </div>
        `).join('');

        const risksHtml = riskHints.length > 0 ? `
            <div class="risk-hints">
                <h4><span class="material-icons md-18">warning</span> Risk Hints</h4>
                <ul>
                    ${riskHints.map(hint => `<li>${hint}</li>`).join('')}
                </ul>
            </div>
        ` : '';

        return `
            <div class="impact-results">
                <h4>Affected Nodes (${affectedNodes.length})</h4>
                <div class="affected-nodes-grid">
                    ${nodesHtml}
                </div>
                ${risksHtml}
            </div>
        `;
    }

    renderTraceResults() {
        const timeline = this.currentResult.timeline || [];

        if (timeline.length === 0) {
            return `
                <div class="empty-state">
                    <span class="material-icons md-48">analytics</span>
                    <p>No evolution history found</p>
                </div>
            `;
        }

        const timelineHtml = timeline.map(event => `
            <div class="timeline-event">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <strong>${event.title || event.type}</strong>
                        <span class="timeline-date">${this.formatDate(event.timestamp)}</span>
                    </div>
                    <p>${event.description || ''}</p>
                </div>
            </div>
        `).join('');

        return `
            <div class="trace-results">
                <div class="timeline-container">
                    ${timelineHtml}
                </div>
            </div>
        `;
    }

    renderMapResults() {
        const nodes = this.currentResult.nodes || [];
        const edges = this.currentResult.edges || [];

        if (nodes.length === 0) {
            return `
                <div class="empty-state">
                    <span class="material-icons md-48">map</span>
                    <p>No subgraph found</p>
                </div>
            `;
        }

        // Group nodes by type
        const nodesByType = {};
        nodes.forEach(node => {
            const type = node.type || 'unknown';
            if (!nodesByType[type]) {
                nodesByType[type] = [];
            }
            nodesByType[type].push(node);
        });

        const typesHtml = Object.entries(nodesByType).map(([type, typeNodes]) => `
            <div class="node-type-group">
                <h4>${type} (${typeNodes.length})</h4>
                <div class="nodes-list">
                    ${typeNodes.map(node => `
                        <div class="node-chip">
                            <span class="material-icons md-18">${node.icon || 'help_outline'}</span>
                            <span>${node.name}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');

        return `
            <div class="map-results">
                <div class="subgraph-summary">
                    <span>${nodes.length} nodes, ${edges.length} edges</span>
                </div>
                ${typesHtml}
            </div>
        `;
    }

    renderError(message) {
        const resultsEl = this.container.querySelector('#query-results');
        if (!resultsEl) return;

        resultsEl.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48">error</span>
                <h3>Query Failed</h3>
                <p>${message}</p>
            </div>
        `;
    }

    formatDate(timestamp) {
        if (!timestamp) return 'Unknown';
        const date = new Date(timestamp * 1000);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    /**
     * Handle autocomplete input with debouncing
     */
    handleAutocompleteInput(value) {
        // Clear previous timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Debounce: wait 300ms before making API call
        this.debounceTimer = setTimeout(() => {
            this.triggerAutocomplete(value);
        }, 300);
    }

    /**
     * Trigger autocomplete API call
     */
    async triggerAutocomplete(value) {
        // Reset selection
        this.selectedIndex = -1;

        // Minimum 2 characters to trigger
        if (value.length < 2) {
            this.hideAutocomplete();
            return;
        }

        try {
            const response = await fetch(`/api/brain/autocomplete?prefix=${encodeURIComponent(value)}&limit=10`);
            const result = await response.json();

            if (result.ok && result.data && result.data.suggestions && result.data.suggestions.length > 0) {
                this.showAutocomplete(result.data.suggestions);
            } else {
                this.hideAutocomplete();
            }
        } catch (error) {
            console.error('Autocomplete failed:', error);
            this.hideAutocomplete();
        }
    }

    /**
     * Show autocomplete dropdown with suggestions
     */
    showAutocomplete(suggestions) {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (!dropdown) return;

        // Render suggestions
        dropdown.innerHTML = suggestions.map((s, index) => {
            const safetyIcons = {
                safe: '✅',
                warning: '⚠️',
                dangerous: '🚨'
            };

            const icon = safetyIcons[s.safety_level] || '❓';

            return `
                <div class="autocomplete-item ${this.escapeHtml(s.safety_level)}" data-index="${index}" data-key="${this.escapeHtml(s.display_text)}">
                    <div class="item-header">
                        <span class="item-icon">${icon}</span>
                        <span class="item-type">${this.escapeHtml(s.entity_type)}</span>
                        <span class="item-name">${this.escapeHtml(s.entity_name)}</span>
                    </div>
                    <div class="item-hint ${this.escapeHtml(s.safety_level)}">
                        ${this.escapeHtml(s.hint_text)}
                    </div>
                </div>
            `;
        }).join('');

        dropdown.style.display = 'block';

        // Attach click handlers
        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, index) => {
            item.addEventListener('mousedown', (e) => {
                e.preventDefault(); // Prevent input blur
                this.selectAutocompleteItem(index);
            });

            item.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                this.highlightSelected();
            });
        });
    }

    /**
     * Hide autocomplete dropdown
     */
    hideAutocomplete() {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
            this.selectedIndex = -1;
        }
    }

    /**
     * Handle keyboard navigation in autocomplete
     */
    handleAutocompleteKeydown(e) {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (!dropdown || dropdown.style.display === 'none') return;

        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (items.length === 0) return;

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                this.highlightSelected();
                this.scrollToSelected();
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.highlightSelected();
                this.scrollToSelected();
                break;

            case 'Escape':
                e.preventDefault();
                this.hideAutocomplete();
                break;

            // Enter is handled in keypress event
        }
    }

    /**
     * Highlight selected autocomplete item
     */
    highlightSelected() {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (!dropdown) return;

        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    /**
     * Scroll to selected item
     */
    scrollToSelected() {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (!dropdown) return;

        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (this.selectedIndex >= 0 && this.selectedIndex < items.length) {
            items[this.selectedIndex].scrollIntoView({
                block: 'nearest',
                behavior: 'smooth'
            });
        }
    }

    /**
     * Select an autocomplete item
     */
    selectAutocompleteItem(index) {
        const dropdown = this.container.querySelector('#autocomplete-dropdown');
        if (!dropdown) return;

        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (index >= 0 && index < items.length) {
            const selectedItem = items[index];
            const key = selectedItem.dataset.key;

            const input = this.container.querySelector('#query-seed');
            if (input) {
                input.value = key;
            }

            this.hideAutocomplete();
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (typeof text !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    destroy() {
        // Cleanup timers
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
    }
}
