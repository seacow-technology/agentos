/**
 * ExplainDrawer Component
 *
 * A right-side drawer that displays BrainOS query results for any entity.
 * Supports 4 query types: Why, Impact, Trace, Map
 *
 * Usage:
 *   ExplainDrawer.show('task', task.id, task.name);
 *
 * Part of: PR-WebUI-BrainOS-1B (Explain Button Embedding)
 */

class ExplainDrawer {
    constructor() {
        this.currentEntityType = null;
        this.currentEntityKey = null;
        this.currentEntityName = null;
        this.currentTab = 'why';
        this.searchDebounceTimer = null;
        this.selectedSearchItemIndex = -1;

        this.createDrawer();
    }

    /**
     * Create the drawer DOM structure
     */
    createDrawer() {
        // Remove existing drawer if present
        const existing = document.getElementById('explain-drawer');
        if (existing) {
            existing.remove();
        }

        const drawer = document.createElement('div');
        drawer.id = 'explain-drawer';
        drawer.className = 'explain-drawer';
        drawer.innerHTML = `
            <div class="explain-drawer-overlay"></div>
            <div class="explain-drawer-content">
                <div class="explain-drawer-header">
                    <h3>psychology Explain: <span id="explain-entity-name"></span></h3>
                    <button class="explain-drawer-close" aria-label="Close drawer">&times;</button>
                </div>

                <div class="entity-search-container">
                    <input
                        type="text"
                        id="entity-search-input"
                        placeholder="Search other entities..."
                        autocomplete="off"
                    />
                    <div id="entity-search-dropdown" class="entity-search-dropdown" style="display: none;"></div>
                </div>

                <div class="explain-tabs">
                    <button class="explain-tab active" data-tab="why">Why</button>
                    <button class="explain-tab" data-tab="impact">Impact</button>
                    <button class="explain-tab" data-tab="trace">Trace</button>
                    <button class="explain-tab" data-tab="map">Map</button>
                </div>

                <div class="explain-content">
                    <div id="explain-loading" style="display: none;">
                        <div class="loading-spinner"></div>
                        <p>Loading...</p>
                    </div>
                    <div id="explain-result"></div>
                </div>
            </div>
        `;
        document.body.appendChild(drawer);

        this.attachDrawerHandlers();
    }

    /**
     * Attach event handlers to drawer elements
     */
    attachDrawerHandlers() {
        // Close button
        const closeBtn = document.querySelector('.explain-drawer-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }

        // Overlay click
        const overlay = document.querySelector('.explain-drawer-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.hide());
        }

        // Tab switching
        document.querySelectorAll('.explain-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });

        // Entity search autocomplete
        const searchInput = document.getElementById('entity-search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleEntitySearch(e.target.value);
            });

            searchInput.addEventListener('keydown', (e) => {
                this.handleSearchKeydown(e);
            });

            searchInput.addEventListener('blur', () => {
                // Delay hiding to allow click events on dropdown items
                setTimeout(() => this.hideEntitySearchDropdown(), 200);
            });
        }

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const drawer = document.getElementById('explain-drawer');
                if (drawer && drawer.classList.contains('active')) {
                    this.hide();
                }
            }
        });
    }

    /**
     * Show the drawer with entity context
     *
     * @param {string} entityType - Type of entity ('task', 'extension', 'file')
     * @param {string} entityKey - Entity key/ID
     * @param {string} entityName - Display name
     */
    static show(entityType, entityKey, entityName) {
        // Create singleton instance if needed
        if (!window.explainDrawer) {
            window.explainDrawer = new ExplainDrawer();
        }

        const drawer = window.explainDrawer;
        drawer.currentEntityType = entityType;
        drawer.currentEntityKey = entityKey;
        drawer.currentEntityName = entityName;

        const nameEl = document.getElementById('explain-entity-name');
        if (nameEl) {
            nameEl.textContent = entityName;
        }

        const drawerEl = document.getElementById('explain-drawer');
        if (drawerEl) {
            drawerEl.classList.add('active');
        }

        // Auto query first tab
        drawer.query(drawer.currentTab);
    }

    /**
     * Hide the drawer
     */
    hide() {
        const drawerEl = document.getElementById('explain-drawer');
        if (drawerEl) {
            drawerEl.classList.remove('active');
        }
    }

    /**
     * Switch to a different tab
     *
     * @param {string} tabName - Tab name ('why', 'impact', 'trace', 'map')
     */
    switchTab(tabName) {
        this.currentTab = tabName;

        // Update active tab
        document.querySelectorAll('.explain-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Query new tab
        this.query(tabName);
    }

    /**
     * Execute a BrainOS query
     *
     * @param {string} queryType - Query type ('why', 'impact', 'trace', 'map')
     */
    async query(queryType) {
        const seed = this.getSeedForEntity();

        const loadingEl = document.getElementById('explain-loading');
        const resultEl = document.getElementById('explain-result');

        if (loadingEl) loadingEl.style.display = 'block';
        if (resultEl) resultEl.innerHTML = '';

        try {
            // Map 'map' to 'subgraph' for API
            const apiQueryType = queryType === 'map' ? 'subgraph' : queryType;

            const response = await fetch(`/api/brain/query/${apiQueryType}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seed })
            });

            // Check HTTP status first
            if (!response.ok) {
                try {
                    const errorBody = await response.json();
                    // FastAPI HTTPException returns {detail: "..."}
                    const errorMsg = errorBody.detail || errorBody.error || `Query failed (HTTP ${response.status})`;
                    this.renderError(errorMsg);
                } catch (e) {
                    this.renderError(`Query failed (HTTP ${response.status})`);
                }
                return;
            }

            const result = await response.json();

            if (result.ok && result.data) {
                // Check for blind spots asynchronously
                const blindSpot = await this.checkBlindSpot(
                    this.currentEntityType,
                    this.currentEntityKey
                );

                // Merge top-level reason into data for render methods
                const dataWithReason = {
                    ...result.data,
                    reason: result.reason
                };
                this.renderResult(queryType, dataWithReason, blindSpot);
            } else {
                this.renderError(result.error || 'Query failed');
            }
        } catch (error) {
            console.error('BrainOS query failed:', error);
            this.renderError(error.message || 'Failed to query BrainOS');
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }

    /**
     * Derive seed from current entity
     *
     * @returns {string} Seed string for BrainOS query
     */
    getSeedForEntity() {
        switch (this.currentEntityType) {
            case 'task':
                // Try to derive from task name - fallback to term
                return `term:${this.currentEntityName}`;

            case 'extension':
                // Use capability key
                return `capability:${this.currentEntityKey}`;

            case 'file':
                // Direct file key
                return `file:${this.currentEntityKey}`;

            default:
                return this.currentEntityKey;
        }
    }

    /**
     * Render query result based on type
     *
     * @param {string} queryType - Query type
     * @param {object} result - Query result from API
     * @param {object} blindSpot - Blind spot data (if any)
     */
    renderResult(queryType, result, blindSpot = null) {
        const resultDiv = document.getElementById('explain-result');
        if (!resultDiv) return;

        switch (queryType) {
            case 'why':
                this.renderWhyResult(result, resultDiv, blindSpot);
                break;
            case 'impact':
                this.renderImpactResult(result, resultDiv, blindSpot);
                break;
            case 'trace':
                this.renderTraceResult(result, resultDiv, blindSpot);
                break;
            case 'map':
                this.renderMapResult(result, resultDiv, blindSpot);
                break;
            default:
                resultDiv.innerHTML = '<p class="no-result">Unknown query type</p>';
        }
    }

    /**
     * Render "Why" query results
     */
    renderWhyResult(result, container, blindSpot = null) {
        if (!result.paths || result.paths.length === 0) {
            let message = 'No explanation found.';
            let hint = '';

            if (result.reason === 'entity_not_indexed') {
                message = 'This entity is not in the knowledge graph yet.';
                hint = 'Build the BrainOS index to include this entity.';
            } else if (result.reason === 'no_coverage') {
                message = 'This entity exists but has no documentation references.';
                hint = 'Consider adding ADR or design docs that reference this entity.';
            } else {
                message = 'No explanation found.';
                hint = 'This may indicate missing documentation or references.';
            }

            container.innerHTML = `
                <p class="no-result">${message}</p>
                ${hint ? `<p class="no-result-hint">${hint}</p>` : ''}
            `;
            return;
        }

        let html = '';

        // Blind spot warning (if present)
        if (blindSpot) {
            html += this.renderBlindSpotWarning(blindSpot);
        }

        // Coverage badge
        html += this.renderCoverageBadge(result);

        // Summary and paths
        html += `<div class="explain-summary">${result.summary || 'Found ' + result.paths.length + ' explanation paths'}</div>`;
        html += '<div class="explain-paths">';

        result.paths.slice(0, 5).forEach((path, idx) => {
            html += `<div class="explain-path">`;
            html += `<div class="path-header">Path #${idx + 1}</div>`;

            path.nodes.forEach((node, nodeIdx) => {
                html += `<div class="path-node">`;
                html += `<span class="node-type">${this.escapeHtml(node.type)}</span>: `;
                html += `<span class="node-name">${this.escapeHtml(node.name)}</span>`;
                if (node.url) {
                    html += ` <a href="${this.escapeHtml(node.url)}" class="node-link">→</a>`;
                }
                html += `</div>`;

                if (nodeIdx < path.nodes.length - 1 && path.edges[nodeIdx]) {
                    html += `<div class="path-edge">${this.escapeHtml(path.edges[nodeIdx].label || path.edges[nodeIdx].type)}</div>`;
                }
            });

            html += `</div>`;
        });

        html += '</div>';

        if (result.evidence && result.evidence.length > 0) {
            html += '<div class="explain-evidence">';
            html += '<h4>Evidence</h4>';
            result.evidence.slice(0, 3).forEach(ev => {
                html += `<div class="evidence-item">`;
                html += `<span class="evidence-type">${this.escapeHtml(ev.source_type)}</span>: `;
                html += `<span class="evidence-ref">${this.escapeHtml(ev.label || ev.source_ref)}</span>`;
                if (ev.url) {
                    html += ` <a href="${this.escapeHtml(ev.url)}" class="evidence-link">View</a>`;
                }
                html += `</div>`;
            });
            html += '</div>';
        }

        container.innerHTML = html;
    }

    /**
     * Render "Impact" query results
     */
    renderImpactResult(result, container, blindSpot = null) {
        if (!result.affected_nodes || result.affected_nodes.length === 0) {
            let message = 'No downstream dependencies found.';
            let hint = '';

            if (result.reason === 'entity_not_indexed') {
                message = 'This entity is not in the knowledge graph yet.';
                hint = 'Build the BrainOS index to analyze its impact.';
            } else if (result.reason === 'no_coverage') {
                message = 'This entity exists but is not referenced by other files or modules.';
                hint = 'This is common for leaf nodes (no downstream dependencies).';
            } else {
                message = 'No downstream dependencies found.';
                hint = 'This entity may not be referenced by others.';
            }

            container.innerHTML = `
                <p class="no-result">${message}</p>
                ${hint ? `<p class="no-result-hint">${hint}</p>` : ''}
            `;
            return;
        }

        let html = '';

        // Blind spot warning (if present)
        if (blindSpot) {
            html += this.renderBlindSpotWarning(blindSpot);
        }

        // Coverage badge
        html += this.renderCoverageBadge(result);

        // Summary
        html += `<div class="explain-summary">${result.summary || 'Found ' + result.affected_nodes.length + ' affected entities'}</div>`;

        if (result.risk_hints && result.risk_hints.length > 0) {
            html += '<div class="explain-risks">';
            html += '<h4>warning Risk Hints</h4>';
            result.risk_hints.forEach(hint => {
                html += `<div class="risk-hint">${this.escapeHtml(hint)}</div>`;
            });
            html += '</div>';
        }

        html += '<div class="explain-affected">';
        html += '<h4>Affected Entities</h4>';
        result.affected_nodes.slice(0, 10).forEach(node => {
            html += `<div class="affected-node">`;
            html += `<span class="node-type">${this.escapeHtml(node.type)}</span>: `;
            html += `<span class="node-name">${this.escapeHtml(node.name)}</span>`;
            html += ` <span class="node-distance">(distance: ${node.distance})</span>`;
            html += `</div>`;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    /**
     * Render "Trace" query results
     */
    renderTraceResult(result, container, blindSpot = null) {
        if (!result.timeline || result.timeline.length === 0) {
            let message = 'No evolution history found.';
            let hint = '';

            if (result.reason === 'entity_not_indexed') {
                message = 'This entity is not in the knowledge graph yet.';
                hint = 'Build the BrainOS index to track its history.';
            } else if (result.reason === 'no_coverage') {
                message = 'This entity exists but has no historical mentions in tracked sources.';
                hint = 'Only commits, docs, and code references are tracked.';
            } else {
                message = 'No evolution history found.';
                hint = 'This entity may not have been mentioned in tracked sources.';
            }

            container.innerHTML = `
                <p class="no-result">${message}</p>
                ${hint ? `<p class="no-result-hint">${hint}</p>` : ''}
            `;
            return;
        }

        let html = '';

        // Blind spot warning (if present)
        if (blindSpot) {
            html += this.renderBlindSpotWarning(blindSpot);
        }

        // Coverage badge
        html += this.renderCoverageBadge(result);

        // Summary and timeline
        html += `<div class="explain-summary">${result.summary || 'Found ' + result.timeline.length + ' timeline events'}</div>`;
        html += '<div class="explain-timeline">';

        result.timeline.slice(0, 10).forEach(event => {
            html += `<div class="timeline-event">`;
            html += `<div class="event-time">${new Date(event.timestamp * 1000).toLocaleDateString()}</div>`;
            html += `<div class="event-node">`;
            html += `<span class="node-type">${this.escapeHtml(event.node.type)}</span>: `;
            html += `<span class="node-name">${this.escapeHtml(event.node.name)}</span>`;
            html += `</div>`;
            html += `<div class="event-relation">${this.escapeHtml(event.relation)}</div>`;
            html += `</div>`;
        });

        html += '</div>';
        container.innerHTML = html;
    }

    /**
     * Render "Map" query results
     */
    renderMapResult(result, container, blindSpot = null) {
        if (!result.nodes || result.nodes.length === 0) {
            let message = 'No related entities found.';
            let hint = '';

            if (result.reason === 'entity_not_indexed') {
                message = 'This entity is not in the knowledge graph yet.';
                hint = 'Build the BrainOS index to see related entities.';
            } else if (result.reason === 'no_coverage') {
                message = 'This entity exists but has no connected nodes in the graph.';
                hint = 'This may indicate an isolated entity with no relationships.';
            } else {
                message = 'No related entities found.';
                hint = 'Try increasing the k-hop parameter or check the seed format.';
            }

            container.innerHTML = `
                <p class="no-result">${message}</p>
                ${hint ? `<p class="no-result-hint">${hint}</p>` : ''}
            `;
            return;
        }

        let html = '';

        // Blind spot warning (if present)
        if (blindSpot) {
            html += this.renderBlindSpotWarning(blindSpot);
        }

        // Coverage badge
        html += this.renderCoverageBadge(result);

        // Summary and nodes
        html += `<div class="explain-summary">Subgraph with ${result.nodes.length} nodes and ${result.edges ? result.edges.length : 0} edges</div>`;
        html += '<div class="explain-nodes">';
        html += '<h4>Nodes</h4>';

        result.nodes.slice(0, 15).forEach(node => {
            html += `<div class="subgraph-node">`;
            html += `<span class="node-type">${this.escapeHtml(node.type)}</span>: `;
            html += `<span class="node-name">${this.escapeHtml(node.name)}</span>`;
            if (node.distance !== undefined) {
                html += ` <span class="node-distance">(distance: ${node.distance})</span>`;
            }
            html += `</div>`;
        });

        html += '</div>';

        if (result.edges && result.edges.length > 0) {
            html += '<div class="explain-edges">';
            html += '<h4>Relationships</h4>';
            result.edges.slice(0, 10).forEach(edge => {
                html += `<div class="subgraph-edge">${this.escapeHtml(edge.label || edge.type)}</div>`;
            });
            html += '</div>';
        }

        container.innerHTML = html;
    }

    /**
     * Check if entity is a blind spot
     *
     * @param {string} entityType - Entity type
     * @param {string} entityKey - Entity key
     * @returns {Promise<object|null>} Blind spot data or null
     */
    async checkBlindSpot(entityType, entityKey) {
        try {
            // Fetch blind spots from API
            const response = await fetch('/api/brain/blind-spots?max_results=100');
            const result = await response.json();

            if (!result.ok || !result.data) {
                return null;
            }

            // Check if current entity is in blind spots list
            const blindSpots = result.data.blind_spots || [];
            const matchingBlindSpot = blindSpots.find(bs =>
                bs.entity_type === entityType && bs.entity_key === entityKey
            );

            return matchingBlindSpot || null;
        } catch (error) {
            console.error('Failed to check blind spot:', error);
            return null;
        }
    }

    /**
     * Render coverage badge
     *
     * @param {object} result - Query result with coverage_info
     * @returns {string} HTML for coverage badge
     */
    renderCoverageBadge(result) {
        if (!result.coverage_info) {
            return ''; // No coverage info available
        }

        const coverage = result.coverage_info;
        const sources = coverage.evidence_sources || [];
        const sourceCount = coverage.source_count || 0;
        const explanation = coverage.explanation || '';

        // Determine badge class
        let badgeClass = 'coverage-badge-low';
        let icon = 'cancel';
        if (sourceCount === 3) {
            badgeClass = 'coverage-badge-high';
            icon = 'check_circle';
        } else if (sourceCount === 2) {
            badgeClass = 'coverage-badge-medium';
            icon = 'warning';
        }

        // Render source tags
        const allSources = ['git', 'doc', 'code'];
        const sourceTags = allSources.map(src => {
            const hasSource = sources.includes(src);
            return `<span class="source-tag ${hasSource ? 'active' : 'inactive'}">${src.toUpperCase()}</span>`;
        }).join(' ');

        return `
            <div class="coverage-badge ${badgeClass}">
                <div class="coverage-header">
                    <span class="coverage-icon">bar_chart</span>
                    <span class="coverage-label">Evidence Sources:</span>
                    ${sourceTags}
                    <span class="coverage-count">(${sourceCount}/3 sources)</span>
                </div>
                <div class="coverage-explanation">
                    <span class="explanation-icon">${icon}</span>
                    <span class="explanation-text">${this.escapeHtml(explanation)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Render blind spot warning
     *
     * @param {object} blindSpot - Blind spot data
     * @returns {string} HTML for blind spot warning
     */
    renderBlindSpotWarning(blindSpot) {
        if (!blindSpot) {
            return '';
        }

        const severityClass = this.getSeverityClass(blindSpot.severity);
        const severityIcon = this.getSeverityIcon(blindSpot.severity);

        return `
            <div class="blind-spot-warning ${severityClass}">
                <div class="warning-header">
                    <span class="warning-icon">${severityIcon}</span>
                    <span class="warning-title">Blind Spot Detected</span>
                    <span class="severity-badge">${blindSpot.severity.toFixed(2)}</span>
                </div>
                <div class="warning-body">
                    <p class="warning-reason">${this.escapeHtml(blindSpot.reason)}</p>
                    <p class="warning-action">
                        <strong>→ Suggested:</strong> ${this.escapeHtml(blindSpot.suggested_action)}
                    </p>
                </div>
            </div>
        `;
    }

    /**
     * Get severity class based on severity value
     *
     * @param {number} severity - Severity value (0.0-1.0)
     * @returns {string} CSS class name
     */
    getSeverityClass(severity) {
        if (severity >= 0.7) {
            return 'high';
        } else if (severity >= 0.4) {
            return 'medium';
        } else {
            return 'low';
        }
    }

    /**
     * Get severity icon based on severity value
     *
     * @param {number} severity - Severity value (0.0-1.0)
     * @returns {string} Icon emoji
     */
    getSeverityIcon(severity) {
        if (severity >= 0.7) {
            return 'emergency';
        } else if (severity >= 0.4) {
            return 'warning';
        } else {
            return 'lightbulb';
        }
    }

    /**
     * Render error message
     */
    renderError(error) {
        const resultEl = document.getElementById('explain-result');
        if (resultEl) {
            resultEl.innerHTML = `<p class="error">Error: ${this.escapeHtml(error)}</p>`;
        }
    }

    /**
     * Handle entity search input with debounce
     *
     * @param {string} value - Search input value
     */
    handleEntitySearch(value) {
        // Clear previous debounce timer
        if (this.searchDebounceTimer) {
            clearTimeout(this.searchDebounceTimer);
        }

        // Require at least 2 characters
        if (value.length < 2) {
            this.hideEntitySearchDropdown();
            return;
        }

        // Debounce by 300ms
        this.searchDebounceTimer = setTimeout(async () => {
            await this.fetchEntitySuggestions(value);
        }, 300);
    }

    /**
     * Fetch entity suggestions from API
     *
     * @param {string} prefix - Search prefix
     */
    async fetchEntitySuggestions(prefix) {
        try {
            const response = await fetch(
                `/api/brain/autocomplete?prefix=${encodeURIComponent(prefix)}&limit=10&include_warnings=true`
            );
            const result = await response.json();

            if (result.ok && result.data && result.data.suggestions.length > 0) {
                this.showEntitySearchDropdown(result.data.suggestions);
            } else {
                this.hideEntitySearchDropdown();
            }
        } catch (error) {
            console.error('Entity search failed:', error);
            this.hideEntitySearchDropdown();
        }
    }

    /**
     * Show entity search dropdown with suggestions
     *
     * @param {Array} suggestions - List of suggestion objects
     */
    showEntitySearchDropdown(suggestions) {
        const dropdown = document.getElementById('entity-search-dropdown');
        if (!dropdown) return;

        this.selectedSearchItemIndex = -1;

        dropdown.innerHTML = suggestions.map((s, idx) => {
            // Determine safety icon and level
            let safetyIcon = '';
            let safetyClass = '';

            if (s.safety_level === 'dangerous') {
                safetyIcon = 'emergency';
                safetyClass = 'dangerous';
            } else if (s.safety_level === 'warning') {
                safetyIcon = 'warning';
                safetyClass = 'warning';
            } else {
                safetyIcon = 'check_circle';
                safetyClass = 'safe';
            }

            return `
                <div class="entity-search-item ${safetyClass}"
                     data-index="${idx}"
                     data-type="${this.escapeHtml(s.entity_type)}"
                     data-key="${this.escapeHtml(s.entity_key)}"
                     data-name="${this.escapeHtml(s.entity_name)}">
                    <div class="item-header">
                        <span class="safety-icon material-icons">${safetyIcon}</span>
                        <span class="item-type-badge">${this.escapeHtml(s.entity_type)}</span>
                        <span class="item-name">${this.escapeHtml(s.entity_name)}</span>
                    </div>
                    <div class="item-hint ${safetyClass}">
                        ${this.escapeHtml(s.hint_text)}
                    </div>
                    ${s.is_blind_spot && s.blind_spot_severity >= 0.7 ? `
                        <div class="item-warning">
                            <strong>High-risk blind spot:</strong> ${this.escapeHtml(s.blind_spot_reason)}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        dropdown.style.display = 'block';

        // Attach click handlers
        dropdown.querySelectorAll('.entity-search-item').forEach(item => {
            item.addEventListener('click', () => {
                this.switchToEntity(
                    item.dataset.type,
                    item.dataset.key,
                    item.dataset.name
                );
                this.hideEntitySearchDropdown();
            });
        });
    }

    /**
     * Hide entity search dropdown
     */
    hideEntitySearchDropdown() {
        const dropdown = document.getElementById('entity-search-dropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
        this.selectedSearchItemIndex = -1;
    }

    /**
     * Handle keyboard navigation in search dropdown
     *
     * @param {KeyboardEvent} e - Keyboard event
     */
    handleSearchKeydown(e) {
        const dropdown = document.getElementById('entity-search-dropdown');
        if (!dropdown || dropdown.style.display === 'none') {
            return;
        }

        const items = dropdown.querySelectorAll('.entity-search-item');
        if (items.length === 0) {
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedSearchItemIndex = Math.min(
                    this.selectedSearchItemIndex + 1,
                    items.length - 1
                );
                this.highlightSearchItem(items);
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.selectedSearchItemIndex = Math.max(
                    this.selectedSearchItemIndex - 1,
                    0
                );
                this.highlightSearchItem(items);
                break;

            case 'Enter':
                e.preventDefault();
                if (this.selectedSearchItemIndex >= 0) {
                    const selectedItem = items[this.selectedSearchItemIndex];
                    this.switchToEntity(
                        selectedItem.dataset.type,
                        selectedItem.dataset.key,
                        selectedItem.dataset.name
                    );
                    this.hideEntitySearchDropdown();
                }
                break;

            case 'Escape':
                e.preventDefault();
                this.hideEntitySearchDropdown();
                break;
        }
    }

    /**
     * Highlight selected search item
     *
     * @param {NodeList} items - List of item elements
     */
    highlightSearchItem(items) {
        items.forEach((item, idx) => {
            if (idx === this.selectedSearchItemIndex) {
                item.classList.add('selected');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('selected');
            }
        });
    }

    /**
     * Switch to a different entity
     *
     * @param {string} entityType - Entity type
     * @param {string} entityKey - Entity key
     * @param {string} entityName - Display name
     */
    switchToEntity(entityType, entityKey, entityName) {
        // Update current entity context
        this.currentEntityType = entityType;
        this.currentEntityKey = entityKey;
        this.currentEntityName = entityName;

        // Update header display
        const nameEl = document.getElementById('explain-entity-name');
        if (nameEl) {
            nameEl.textContent = entityName;
        }

        // Clear search box
        const searchInput = document.getElementById('entity-search-input');
        if (searchInput) {
            searchInput.value = '';
        }

        // Re-query current tab
        this.query(this.currentTab);
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ExplainDrawer = ExplainDrawer;
}
