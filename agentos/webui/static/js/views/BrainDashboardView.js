/**
 * BrainDashboardView - BrainOS Cognitive Dashboard
 *
 * Displays BrainOS knowledge graph statistics and health metrics:
 * - Graph status (version, commit, build time)
 * - Data scale (entities, edges, evidence)
 * - Input coverage (Git, Doc, Code)
 * - Cognitive coverage (doc refs, dependency graph)
 * - Blind spots (files with no references)
 * - Quick actions (rebuild, query console)
 */

class BrainDashboardView {
    constructor(container) {
        this.container = container;
        this.stats = null;
        this.refreshInterval = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="brain-dashboard">
                <div class="view-header">
                    <div>
                        <h1>BrainOS Dashboard</h1>
                        <p class="text-sm text-gray-600 mt-1">Local Knowledge Graph - Cognitive Status</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="brain-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-primary" id="brain-query-console">
                            <span class="icon"><span class="material-icons md-18">search</span></span> Query Console
                        </button>
                    </div>
                </div>

                <div class="dashboard-grid" id="brain-dashboard-grid">
                    <!-- Cards will be rendered here -->
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadStats();

        // Auto-refresh every 30 seconds
        this.refreshInterval = setInterval(() => this.loadStats(), 30000);
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#brain-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadStats());
        }

        // Query console button
        const queryBtn = this.container.querySelector('#brain-query-console');
        if (queryBtn) {
            queryBtn.addEventListener('click', () => {
                loadView('brain-query');
            });
        }
    }

    async loadStats() {
        try {
            // Fetch all data in parallel
            const [statsResponse, coverageResponse, blindSpotsResponse] = await Promise.all([
                fetch('/api/brain/stats'),
                fetch('/api/brain/coverage'),
                fetch('/api/brain/blind-spots?max_results=10')
            ]);

            const statsResult = await statsResponse.json();
            const coverageResult = await coverageResponse.json();
            const blindSpotsResult = await blindSpotsResponse.json();

            if (statsResult.ok && statsResult.data) {
                this.stats = statsResult.data;
                this.coverage = coverageResult.ok ? coverageResult.data : null;
                this.blindSpots = blindSpotsResult.ok ? blindSpotsResult.data : null;
                this.renderDashboard();
            } else {
                this.renderError(statsResult.error || 'Failed to load BrainOS stats');
            }
        } catch (error) {
            console.error('Failed to load BrainOS stats:', error);
            this.renderError('Failed to connect to BrainOS API');
        }
    }

    renderDashboard() {
        const grid = this.container.querySelector('#brain-dashboard-grid');
        if (!grid) return;

        grid.innerHTML = `
            ${this.renderGraphStatusCard()}
            ${this.renderDataScaleCard()}
            ${this.renderInputCoverageCard()}
            ${this.renderCognitiveCoverageCard()}
            ${this.renderBlindSpotsCard()}
            ${this.renderActionsCard()}
            ${this.renderCoverageSummaryCard()}
            ${this.renderTopBlindSpotsCard()}
        `;
    }

    renderGraphStatusCard() {
        const lastBuild = this.stats?.last_build;

        if (!lastBuild) {
            return `
                <div class="card graph-status">
                    <h3><span class="material-icons md-18">account_tree</span> Graph Status</h3>
                    <div class="card-content">
                        <p class="text-muted">No index built yet</p>
                        <button class="btn-primary mt-3" onclick="window.buildBrainIndex()">
                            Build Index Now
                        </button>
                    </div>
                </div>
            `;
        }

        const graphVersion = lastBuild.graph_version || 'unknown';
        const sourceCommit = lastBuild.source_commit || 'unknown';
        const builtAt = lastBuild.built_at || 0;
        const durationMs = lastBuild.duration_ms || 0;

        const timeAgo = this.formatTimeAgo(builtAt * 1000);
        const duration = this.formatDuration(durationMs);

        return `
            <div class="card graph-status">
                <h3><span class="material-icons md-18">account_tree</span> Graph Status</h3>
                <div class="card-content">
                    <div class="metric-row">
                        <span class="metric-label">Version:</span>
                        <span class="metric-value">${this.truncate(graphVersion, 20)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Commit:</span>
                        <span class="metric-value code">${sourceCommit.substring(0, 8)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Built:</span>
                        <span class="metric-value">${timeAgo}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Duration:</span>
                        <span class="metric-value">${duration}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderDataScaleCard() {
        const entities = this.stats?.entities || 0;
        const edges = this.stats?.edges || 0;
        const evidence = this.stats?.evidence || 0;
        const density = edges > 0 ? (evidence / edges).toFixed(2) : '0.00';

        return `
            <div class="card data-scale">
                <h3><span class="material-icons md-18">save</span> Data Scale</h3>
                <div class="card-content">
                    <div class="metric-row">
                        <span class="metric-label">Entities:</span>
                        <span class="metric-value">${this.formatNumber(entities)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Edges:</span>
                        <span class="metric-value">${this.formatNumber(edges)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Evidence:</span>
                        <span class="metric-value">${this.formatNumber(evidence)}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Density:</span>
                        <span class="metric-value">${density}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderInputCoverageCard() {
        const coverage = this.stats?.coverage || {};
        const gitCoverage = coverage.git_coverage ? 'check_circle' : 'cancel';
        const docCoverage = coverage.doc_coverage ? 'check_circle' : 'cancel';
        const codeCoverage = coverage.code_coverage ? 'check_circle' : 'cancel';

        // TODO: Get actual counts from stats
        const commitCount = this.stats?.commit_count || 0;
        const docCount = this.stats?.doc_count || 0;
        const depCount = this.stats?.dependency_count || 0;

        return `
            <div class="card input-coverage">
                <h3><span class="material-icons md-18">inbox</span> Input Coverage</h3>
                <div class="card-content">
                    <div class="metric-row">
                        <span class="metric-label">Git:</span>
                        <span class="metric-value">${gitCoverage} (${commitCount} commits)</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Doc:</span>
                        <span class="metric-value">${docCoverage} (${docCount} docs)</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Code:</span>
                        <span class="metric-value">${codeCoverage} (${depCount} deps)</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderCognitiveCoverageCard() {
        const coverage = this.stats?.coverage || {};
        const docRefsPct = coverage.doc_refs_pct || 0;
        const depGraphPct = coverage.dep_graph_pct || 0;

        return `
            <div class="card cognitive-coverage">
                <h3><span class="material-icons md-18">psychology</span> Cognitive Coverage</h3>
                <div class="card-content">
                    <div class="metric-row">
                        <span class="metric-label">Files with Doc Refs:</span>
                        <span class="metric-value">${docRefsPct}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Files in Dep Graph:</span>
                        <span class="metric-value">${depGraphPct}%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${docRefsPct}%"></div>
                    </div>
                </div>
            </div>
        `;
    }

    renderBlindSpotsCard() {
        const blindSpots = this.stats?.blind_spots || [];

        if (blindSpots.length === 0) {
            return `
                <div class="card blind-spots">
                    <h3><span class="material-icons md-18">block</span> Blind Spots</h3>
                    <div class="card-content">
                        <p class="text-muted">No significant blind spots detected</p>
                    </div>
                </div>
            `;
        }

        const spotsList = blindSpots.map(spot => `
            <li class="blind-spot-item">
                <span class="material-icons md-18">warning</span>
                <span>${spot.label || spot.name || 'Unknown'}</span>
            </li>
        `).join('');

        return `
            <div class="card blind-spots">
                <h3><span class="material-icons md-18">block</span> Blind Spots</h3>
                <div class="card-content">
                    <ul class="blind-spots-list">
                        ${spotsList}
                    </ul>
                </div>
            </div>
        `;
    }

    renderActionsCard() {
        return `
            <div class="card actions">
                <h3><span class="material-icons md-18">settings</span> Actions</h3>
                <div class="card-content actions-buttons">
                    <button class="btn-primary" onclick="window.buildBrainIndex()">
                        <span class="material-icons md-18">refresh</span>
                        Rebuild Index
                    </button>
                    <button class="btn-secondary" onclick="loadView('brain-query')">
                        <span class="material-icons md-18">search</span>
                        Query Console
                    </button>
                    <button class="btn-secondary" onclick="window.viewGoldenQueries()">
                        <span class="material-icons md-18">new_releases</span>
                        Golden Queries
                    </button>
                </div>
            </div>
        `;
    }

    renderError(message) {
        const grid = this.container.querySelector('#brain-dashboard-grid');
        if (!grid) return;

        grid.innerHTML = `
            <div class="card error-card full-width">
                <div class="card-content">
                    <span class="material-icons md-48">error</span>
                    <h3>Failed to Load Dashboard</h3>
                    <p class="text-muted">${message}</p>
                    <button class="btn-primary mt-3" onclick="window.buildBrainIndex()">
                        Build Index Now
                    </button>
                </div>
            </div>
        `;
    }

    // Utility methods
    formatNumber(num) {
        return num.toLocaleString();
    }

    formatTimeAgo(timestamp) {
        const now = Date.now();
        const diff = now - timestamp;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ago`;
        if (hours > 0) return `${hours}h ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'just now';
    }

    formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);

        if (minutes > 0) {
            const remainingSeconds = seconds % 60;
            return `${minutes}m ${remainingSeconds}s`;
        }
        return `${seconds}s`;
    }

    truncate(str, maxLen) {
        if (str.length <= maxLen) return str;
        return str.substring(0, maxLen - 3) + '...';
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    getCoverageClass(coverage) {
        if (coverage >= 0.7) return 'high';
        if (coverage >= 0.4) return 'medium';
        return 'low';
    }

    getSeverityClass(severity) {
        if (severity >= 0.7) return 'high';
        if (severity >= 0.4) return 'medium';
        return 'low';
    }

    getSeverityIcon(severity) {
        if (severity >= 0.7) return 'circle';
        if (severity >= 0.4) return 'circle';
        return 'circle';
    }

    renderCoverageSummaryCard() {
        if (!this.coverage) {
            return `
                <div class="card coverage-summary-card">
                    <h3><span class="material-icons md-18">assessment</span> Cognitive Coverage</h3>
                    <div class="card-content">
                        <p class="text-muted">No coverage data available</p>
                    </div>
                </div>
            `;
        }

        const codeCoveragePercent = (this.coverage.code_coverage * 100).toFixed(1);
        const docCoveragePercent = (this.coverage.doc_coverage * 100).toFixed(1);
        const depCoveragePercent = (this.coverage.dependency_coverage * 100).toFixed(1);

        const codeCoverageClass = this.getCoverageClass(this.coverage.code_coverage);
        const docCoverageClass = this.getCoverageClass(this.coverage.doc_coverage);
        const depCoverageClass = this.getCoverageClass(this.coverage.dependency_coverage);

        const uncoveredCount = this.coverage.uncovered_files ? this.coverage.uncovered_files.length : 0;

        return `
            <div class="card coverage-summary-card">
                <h3><span class="material-icons md-18">assessment</span> Cognitive Coverage</h3>
                <div class="card-subtitle">What BrainOS knows vs. what exists</div>
                <div class="card-content">
                    <div class="coverage-item">
                        <div class="coverage-label">
                            <span>Code Coverage</span>
                            <span class="coverage-value ${codeCoverageClass}">${codeCoveragePercent}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill ${codeCoverageClass}" style="width: ${codeCoveragePercent}%"></div>
                        </div>
                    </div>

                    <div class="coverage-item">
                        <div class="coverage-label">
                            <span>Doc Coverage</span>
                            <span class="coverage-value ${docCoverageClass}">${docCoveragePercent}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill ${docCoverageClass}" style="width: ${docCoveragePercent}%"></div>
                        </div>
                    </div>

                    <div class="coverage-item">
                        <div class="coverage-label">
                            <span>Dependency Coverage</span>
                            <span class="coverage-value ${depCoverageClass}">${depCoveragePercent}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill ${depCoverageClass}" style="width: ${depCoveragePercent}%"></div>
                        </div>
                    </div>

                    <div class="coverage-summary">
                        <div class="summary-row">
                            <span class="summary-label">Covered files</span>
                            <span class="summary-value">${this.coverage.covered_files}/${this.coverage.total_files}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">No evidence</span>
                            <span class="summary-value warn">${uncoveredCount}</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderTopBlindSpotsCard() {
        if (!this.blindSpots || this.blindSpots.total_blind_spots === 0) {
            return `
                <div class="card blind-spots-summary-card">
                    <h3><span class="material-icons md-18">block</span> Top Blind Spots</h3>
                    <div class="card-subtitle">Areas where BrainOS knows it doesn't know</div>
                    <div class="card-content">
                        <p class="no-data good">No blind spots detected! celebration</p>
                    </div>
                </div>
            `;
        }

        const topBlindSpots = this.blindSpots.blind_spots.slice(0, 5);

        const spotsList = topBlindSpots.map(bs => `
            <div class="blind-spot-item">
                <div class="blind-spot-header">
                    <span class="severity-icon ${this.getSeverityClass(bs.severity)}">${this.getSeverityIcon(bs.severity)}</span>
                    <span class="blind-spot-name">${this.escapeHtml(bs.entity_name || bs.entity_key)}</span>
                    <span class="severity-value">${bs.severity.toFixed(2)}</span>
                </div>
                <div class="blind-spot-reason">
                    ${this.escapeHtml(bs.reason)}
                </div>
            </div>
        `).join('');

        const highCount = this.blindSpots.by_severity?.high || 0;
        const mediumCount = this.blindSpots.by_severity?.medium || 0;
        const lowCount = this.blindSpots.by_severity?.low || 0;

        return `
            <div class="card blind-spots-summary-card">
                <h3><span class="material-icons md-18">block</span> Top Blind Spots</h3>
                <div class="card-subtitle">Areas where BrainOS knows it doesn't know</div>
                <div class="card-content">
                    <div class="blind-spots-list">
                        ${spotsList}
                    </div>

                    <div class="blind-spots-summary">
                        <span class="severity-badge high">${highCount} high</span>
                        <span class="severity-badge medium">${mediumCount} medium</span>
                        <span class="severity-badge low">${lowCount} low</span>
                    </div>
                </div>
            </div>
        `;
    }

    destroy() {
        // Clear refresh interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
}

// Global action handlers
window.buildBrainIndex = async function() {
    if (!confirm('Rebuild BrainOS index? This may take a few minutes.')) {
        return;
    }

    try {
        const response = await fetch('/api/brain/build', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: false })
        });

        const result = await response.json();

        if (result.ok) {
            alert('Index build started successfully!');
            // Reload dashboard after a few seconds
            setTimeout(() => loadView('brain-dashboard'), 3000);
        } else {
            alert(`Build failed: ${result.error}`);
        }
    } catch (error) {
        console.error('Build failed:', error);
        alert('Build failed: ' + error.message);
    }
};

window.viewGoldenQueries = function() {
    // TODO: Implement golden queries view
    alert('Golden Queries view coming soon!');
};
