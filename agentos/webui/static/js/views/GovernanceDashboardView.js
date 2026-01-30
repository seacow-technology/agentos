/**
 * GovernanceDashboardView - C-level Governance Dashboard
 *
 * Features:
 * - Real-time governance health metrics
 * - Trend analysis (7d/30d/90d)
 * - Top risks visualization
 * - Health indicators
 * - Auto-refresh capability
 * - Responsive design
 *
 * Task #6 - Governance Dashboard WebUI Main View
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class GovernanceDashboardView {
    constructor() {
        this.currentTimeframe = '7d';
        this.refreshInterval = null;
        this.autoRefresh = false;
        this.container = null;
    }

    /**
     * Render the dashboard view
     * @param {HTMLElement} container - Container element
     */
    async render(container) {
        this.container = container;

        container.innerHTML = `
            <div class="governance-dashboard">
                <div class="view-header">
                    <div>
                        <h1>Governance Dashboard</h1>
                        <p class="text-sm text-gray-600 mt-1">C-level governance health metrics and risks</p>
                    </div>
                    <div class="header-actions">
                        <label class="auto-refresh-toggle" style="display: flex; align-items: center; gap: 6px; margin-right: 12px; font-size: 13px;">
                            <input type="checkbox" id="auto-refresh-checkbox">
                            Auto Refresh (5min)
                        </label>
                        <button id="refresh-btn" class="btn-refresh" title="Refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="filter-section">
                    <div class="filter-bar">
                        <div class="filter-item">
                            <label class="filter-label">Timeframe</label>
                            <select id="timeframe-selector" class="filter-select">
                                <option value="7d" selected>Last 7 Days</option>
                                <option value="30d">Last 30 Days</option>
                                <option value="90d">Last 90 Days</option>
                            </select>
                        </div>
                    </div>
                </div>

                <div class="table-section">
                    <div id="dashboard-content">
                        <div class="loading">Loading governance data...</div>
                    </div>
                </div>
            </div>
        `;

        this.attachHeaderEventListeners();
        await this.loadDashboardData();
    }

    /**
     * Attach event listeners to header controls
     */
    attachHeaderEventListeners() {
        // Timeframe selector
        const timeframeSelector = document.getElementById('timeframe-selector');
        if (timeframeSelector) {
            timeframeSelector.addEventListener('change', (e) => {
                this.currentTimeframe = e.target.value;
                this.loadDashboardData();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData();
            });
        }

        // Auto refresh toggle
        const autoRefreshCheckbox = document.getElementById('auto-refresh-checkbox');
        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.addEventListener('change', (e) => {
                this.autoRefresh = e.target.checked;
                if (this.autoRefresh) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }
    }

    /**
     * Load dashboard data from API
     */
    async loadDashboardData() {
        const contentDiv = document.getElementById('dashboard-content');
        if (!contentDiv) return;

        try {
            contentDiv.innerHTML = '<div class="loading">Loading governance data...</div>';

            const response = await fetch(`/api/governance/dashboard?timeframe=${this.currentTimeframe}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.renderDashboardContent(contentDiv, data);
        } catch (error) {
            console.error('Failed to load dashboard:', error);
            this.renderError(contentDiv, error);
        }
    }

    /**
     * Render dashboard content
     * @param {HTMLElement} container - Content container
     * @param {Object} data - Dashboard data
     */
    renderDashboardContent(container, data) {
        container.innerHTML = `
            <div class="dashboard-grid">
                <!-- Metrics Section -->
                <div class="metrics-section">
                    <div id="metric-risk-level"></div>
                    <div id="metric-open-findings"></div>
                    <div id="metric-blocked-rate"></div>
                    <div id="metric-guarded-percentage"></div>
                </div>

                <!-- Trends Section -->
                <div class="trends-section">
                    <h2>Trends (${this.getTimeframeLabel()})</h2>
                    <div class="trend-cards">
                        <div id="trend-findings"></div>
                        <div id="trend-blocked"></div>
                        <div id="trend-coverage"></div>
                    </div>
                </div>

                <!-- Top Risks Section -->
                <div class="risks-section">
                    <h2>Top Risks</h2>
                    <div id="top-risks-list"></div>
                </div>

                <!-- Health Section -->
                <div class="health-section">
                    <h2>Governance Health</h2>
                    <div id="health-indicators"></div>
                </div>

                <!-- Metadata -->
                <div class="dashboard-footer">
                    <small>Last updated: ${new Date(data.generated_at).toLocaleString()}</small>
                </div>
            </div>
        `;

        // Render metrics using components from Task #7
        this.renderMetrics(data.metrics);
        this.renderTrends(data.trends);
        this.renderTopRisks(data.top_risks);
        this.renderHealth(data.health);
    }

    /**
     * Render metrics section
     * @param {Object} metrics - Metrics data
     */
    renderMetrics(metrics) {
        // Risk Level (wrap RiskBadge in card container)
        const riskContainer = document.querySelector('#metric-risk-level');
        if (riskContainer) {
            riskContainer.innerHTML = `
                <div class="metric-card metric-card-medium">
                    <div class="metric-card-header">
                        <div class="metric-card-title">Risk Level</div>
                    </div>
                    <div class="metric-card-body">
                        <div id="risk-badge-container"></div>
                    </div>
                </div>
            `;
            const riskBadge = new RiskBadge({
                container: '#risk-badge-container',
                level: metrics.risk_level,
                size: 'large',
                showIcon: true,
            });
        }

        // Open Findings (uses MetricCard component)
        const findingsCard = new MetricCard({
            container: '#metric-open-findings',
            title: 'Open Findings',
            value: metrics.open_findings,
            size: 'medium',
            icon: 'search',
            iconType: 'material',
        });

        // Blocked Rate (uses MetricCard component)
        const blockedCard = new MetricCard({
            container: '#metric-blocked-rate',
            title: 'Blocked Rate',
            value: `${(metrics.blocked_rate * 100).toFixed(1)}%`,
            size: 'medium',
            icon: 'block',
            iconType: 'material',
        });

        // Guardian Coverage (wrap HealthIndicator in card container)
        const coverageContainer = document.querySelector('#metric-guarded-percentage');
        if (coverageContainer) {
            coverageContainer.innerHTML = `
                <div class="metric-card metric-card-medium">
                    <div class="metric-card-header">
                        <div class="metric-card-title">Guardian Coverage</div>
                    </div>
                    <div class="metric-card-body">
                        <div id="health-indicator-container"></div>
                    </div>
                </div>
            `;
            const coverageIndicator = new HealthIndicator({
                container: '#health-indicator-container',
                mode: 'bar',
                percentage: metrics.guarded_percentage * 100,
                label: '',
                showLabel: false,
                thresholds: { critical: 50, warning: 70 },
            });
        }
    }

    /**
     * Render trends section
     * @param {Object} trends - Trends data
     */
    renderTrends(trends) {
        // Findings Trend
        const findingsTrend = new MetricCard({
            container: '#trend-findings',
            title: 'Findings',
            value: trends.findings.current,
            trend: trends.findings.direction,
            trendValue: Math.abs(trends.findings.change * 100),
            sparklineData: trends.findings.data_points,
            size: 'medium',
        });

        // Blocked Decisions Trend
        const blockedTrend = new MetricCard({
            container: '#trend-blocked',
            title: 'Blocked Decisions',
            value: `${trends.blocked_decisions.current.toFixed(1)}%`,
            trend: trends.blocked_decisions.direction,
            trendValue: Math.abs(trends.blocked_decisions.change * 100),
            sparklineData: trends.blocked_decisions.data_points,
            size: 'medium',
        });

        // Guardian Coverage Trend
        const coverageTrend = new MetricCard({
            container: '#trend-coverage',
            title: 'Guardian Coverage',
            value: `${trends.guardian_coverage.current.toFixed(0)}%`,
            trend: trends.guardian_coverage.direction,
            trendValue: Math.abs(trends.guardian_coverage.change * 100),
            sparklineData: trends.guardian_coverage.data_points,
            size: 'medium',
        });
    }

    /**
     * Render top risks section
     * @param {Array} topRisks - Top risks data
     */
    renderTopRisks(topRisks) {
        const container = document.getElementById('top-risks-list');
        if (!container) return;

        if (topRisks.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon"><span class="material-icons md-18">check_circle</span></div>
                    <p>No critical risks detected</p>
                </div>
            `;
            return;
        }

        const risksHtml = topRisks.map(risk => `
            <div class="risk-item risk-${risk.severity.toLowerCase()}">
                <div class="risk-header">
                    <span class="risk-badge badge-${risk.severity.toLowerCase()}">${risk.severity}</span>
                    <span class="risk-type">${risk.type}</span>
                    <span class="risk-time">${this.formatRelativeTime(risk.first_seen)}</span>
                </div>
                <div class="risk-title">${risk.title}</div>
                <div class="risk-meta">
                    <span class="affected-count">
                        <span class="material-icons md-18">warning</span> ${risk.affected_tasks} task${risk.affected_tasks > 1 ? 's' : ''} affected
                    </span>
                </div>
            </div>
        `).join('');

        container.innerHTML = risksHtml;
    }

    /**
     * Render health section
     * @param {Object} health - Health data
     */
    renderHealth(health) {
        const container = document.getElementById('health-indicators');
        if (!container) return;

        container.innerHTML = `
            <div class="health-grid">
                <div class="health-item">
                    <label>Guardian Coverage</label>
                    <div class="health-value">
                        <span class="value-large">${(health.guardian_coverage * 100).toFixed(0)}%</span>
                    </div>
                    <div class="health-bar">
                        <div class="bar-fill" style="width: ${health.guardian_coverage * 100}%; background: #28a745;"></div>
                    </div>
                </div>

                <div class="health-item">
                    <label>Avg Decision Latency</label>
                    <div class="health-value">
                        <span class="value-large">${health.avg_decision_latency_ms}ms</span>
                    </div>
                    <div class="health-indicator ${this.getLatencyColor(health.avg_decision_latency_ms)}"></div>
                </div>

                <div class="health-item">
                    <label>Tasks with Audits</label>
                    <div class="health-value">
                        <span class="value-large">${(health.tasks_with_audits * 100).toFixed(0)}%</span>
                    </div>
                    <div class="health-bar">
                        <div class="bar-fill" style="width: ${health.tasks_with_audits * 100}%; background: #17a2b8;"></div>
                    </div>
                </div>

                <div class="health-item">
                    <label>Active Guardians</label>
                    <div class="health-value">
                        <span class="value-large">${health.active_guardians}</span>
                    </div>
                </div>

                <div class="health-item health-item-wide">
                    <label>Last Scan</label>
                    <div class="health-value">
                        <span class="value-medium">${health.last_scan ? new Date(health.last_scan).toLocaleString() : 'N/A'}</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render error state
     * @param {HTMLElement} container - Content container
     * @param {Error} error - Error object
     */
    renderError(container, error) {
        container.innerHTML = `
            <div class="error-state">
                <div class="error-icon"><span class="material-icons md-18">warning</span></div>
                <h3>Failed to Load Dashboard</h3>
                <p>${error.message}</p>
                <button id="retry-btn" class="btn-primary">Retry</button>
            </div>
        `;

        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.loadDashboardData();
            });
        }
    }

    /**
     * Get timeframe label
     * @returns {string} Timeframe label
     */
    getTimeframeLabel() {
        const labels = {
            '7d': 'Last 7 Days',
            '30d': 'Last 30 Days',
            '90d': 'Last 90 Days'
        };
        return labels[this.currentTimeframe] || this.currentTimeframe;
    }

    /**
     * Format relative time
     * @param {string} isoString - ISO timestamp
     * @returns {string} Relative time string
     */
    formatRelativeTime(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        return `${diffDays}d ago`;
    }

    /**
     * Get latency color class
     * @param {number} latency - Latency in ms
     * @returns {string} CSS class name
     */
    getLatencyColor(latency) {
        if (latency < 500) return 'success';
        if (latency < 1500) return 'warning';
        return 'danger';
    }

    /**
     * Start auto-refresh
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.loadDashboardData();
        }, 5 * 60 * 1000);  // 5 minutes
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Destroy the view
     */
    destroy() {
        this.stopAutoRefresh();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export to window
window.GovernanceDashboardView = GovernanceDashboardView;
