/**
 * CapabilityDashboardView - AgentOS v3 Capability Governance Dashboard
 *
 * Task #29: Display Capability governance real-time status
 *
 * Features:
 * - 5 Domain capability counts (State, Decision, Action, Governance, Evidence)
 * - Agent → Capability authorization relationship graph
 * - Real-time invocation statistics (today/week/month)
 * - Risk distribution (LOW/MEDIUM/HIGH/CRITICAL)
 * - 4 key indicator cards
 */

class CapabilityDashboardView {
    constructor(container) {
        this.container = container;
        this.stats = null;
        this.refreshInterval = null;
        this.charts = {};

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="capability-dashboard">
                <div class="view-header">
                    <div>
                        <h1>Capability Governance</h1>
                        <p class="text-sm text-gray-600 mt-1">AgentOS v3 - Real-time Governance Status</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="cap-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                        <button class="btn-secondary" id="cap-audit">
                            <span class="icon"><span class="material-icons md-18">security</span></span> Audit Log
                        </button>
                    </div>
                </div>

                <!-- Key Metrics Cards -->
                <div class="metrics-grid" id="cap-metrics-grid">
                    <!-- Cards will be rendered here -->
                </div>

                <!-- Domain Overview -->
                <div class="dashboard-section">
                    <h2 class="section-title">Domain Overview</h2>
                    <div class="domain-grid" id="cap-domain-grid">
                        <!-- Domain cards will be rendered here -->
                    </div>
                </div>

                <!-- Charts Row -->
                <div class="charts-row">
                    <div class="chart-card">
                        <h3 class="chart-title">Invocation Statistics (Today)</h3>
                        <canvas id="cap-invocation-chart"></canvas>
                    </div>
                    <div class="chart-card">
                        <h3 class="chart-title">Risk Distribution</h3>
                        <canvas id="cap-risk-chart"></canvas>
                    </div>
                </div>

                <!-- Quick Actions -->
                <div class="dashboard-section">
                    <h2 class="section-title">Quick Access</h2>
                    <div class="quick-actions-grid">
                        <button class="action-card" data-action="decisions">
                            <span class="material-icons md-36">timeline</span>
                            <span class="action-label">Decision Timeline</span>
                        </button>
                        <button class="action-card" data-action="actions">
                            <span class="material-icons md-36">play_circle_outline</span>
                            <span class="action-label">Action Log</span>
                        </button>
                        <button class="action-card" data-action="evidence">
                            <span class="material-icons md-36">account_tree</span>
                            <span class="action-label">Evidence Chains</span>
                        </button>
                        <button class="action-card" data-action="matrix">
                            <span class="material-icons md-36">grid_on</span>
                            <span class="action-label">Agent Matrix</span>
                        </button>
                    </div>
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
        const refreshBtn = this.container.querySelector('#cap-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadStats());
        }

        // Audit button
        const auditBtn = this.container.querySelector('#cap-audit');
        if (auditBtn) {
            auditBtn.addEventListener('click', () => {
                if (window.loadView) {
                    window.loadView('governance-audit');
                }
            });
        }

        // Quick action buttons
        const actionCards = this.container.querySelectorAll('.action-card');
        actionCards.forEach(card => {
            card.addEventListener('click', () => {
                const action = card.dataset.action;
                this.handleQuickAction(action);
            });
        });
    }

    handleQuickAction(action) {
        const viewMap = {
            'decisions': 'decision-timeline',
            'actions': 'action-log',
            'evidence': 'evidence-chain',
            'matrix': 'agent-matrix'
        };

        const viewName = viewMap[action];
        if (viewName && window.loadView) {
            window.loadView(viewName);
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/capability/dashboard/stats');
            const result = await response.json();

            if (result.ok && result.data) {
                this.stats = result.data;
                this.renderDashboard();
            } else {
                this.renderError(result.error || 'Failed to load dashboard stats');
            }
        } catch (error) {
            console.error('Failed to load dashboard stats:', error);
            this.renderError('Failed to connect to API');
        }
    }

    renderDashboard() {
        this.renderMetrics();
        this.renderDomains();
        this.renderCharts();
    }

    renderMetrics() {
        const metricsGrid = this.container.querySelector('#cap-metrics-grid');
        if (!metricsGrid) return;

        const { today_stats, domains, risk_distribution } = this.stats;

        // Calculate total capabilities
        const totalCapabilities = Object.values(domains).reduce((sum, d) => sum + d.count, 0);

        // Calculate total active agents
        const totalAgents = Object.values(domains).reduce((sum, d) => sum + d.active_agents, 0);

        // Calculate success rate
        const successRate = today_stats.total_invocations > 0
            ? Math.round(100 * today_stats.allowed / today_stats.total_invocations)
            : 0;

        // Critical capabilities count
        const criticalCount = risk_distribution.CRITICAL || 0;

        const metrics = [
            {
                label: 'Total Capabilities',
                value: totalCapabilities,
                icon: 'extension',
                color: 'blue',
                subtitle: '5 Domains'
            },
            {
                label: 'Active Agents',
                value: totalAgents,
                icon: 'people',
                color: 'green',
                subtitle: 'With Grants'
            },
            {
                label: 'Today Invocations',
                value: this.formatNumber(today_stats.total_invocations),
                icon: 'show_chart',
                color: 'purple',
                subtitle: `${successRate}% Success`
            },
            {
                label: 'Critical Capabilities',
                value: criticalCount,
                icon: 'warning',
                color: 'red',
                subtitle: 'Admin Level'
            }
        ];

        metricsGrid.innerHTML = metrics.map(metric => `
            <div class="metric-card metric-${metric.color}">
                <div class="metric-icon">
                    <span class="material-icons md-36">${metric.icon}</span>
                </div>
                <div class="metric-content">
                    <div class="metric-value">${metric.value}</div>
                    <div class="metric-label">${metric.label}</div>
                    <div class="metric-subtitle">${metric.subtitle}</div>
                </div>
            </div>
        `).join('');
    }

    renderDomains() {
        const domainGrid = this.container.querySelector('#cap-domain-grid');
        if (!domainGrid) return;

        const { domains } = this.stats;

        const domainInfo = {
            state: { label: 'State', icon: 'memory', color: 'blue' },
            decision: { label: 'Decision', icon: 'account_tree', color: 'purple' },
            action: { label: 'Action', icon: 'play_arrow', color: 'orange' },
            governance: { label: 'Governance', icon: 'security', color: 'green' },
            evidence: { label: 'Evidence', icon: 'description', color: 'teal' }
        };

        domainGrid.innerHTML = Object.entries(domains).map(([domain, stats]) => {
            const info = domainInfo[domain] || { label: domain, icon: 'extension', color: 'gray' };

            return `
                <div class="domain-card domain-${info.color}">
                    <div class="domain-header">
                        <span class="material-icons md-24">${info.icon}</span>
                        <span class="domain-name">${info.label}</span>
                    </div>
                    <div class="domain-stats">
                        <div class="stat-item">
                            <div class="stat-value">${stats.count}</div>
                            <div class="stat-label">Capabilities</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${stats.active_agents}</div>
                            <div class="stat-label">Active Agents</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderCharts() {
        this.renderInvocationChart();
        this.renderRiskChart();
    }

    renderInvocationChart() {
        const canvas = this.container.querySelector('#cap-invocation-chart');
        if (!canvas) return;

        const { today_stats } = this.stats;

        // Destroy existing chart
        if (this.charts.invocation) {
            this.charts.invocation.destroy();
        }

        const ctx = canvas.getContext('2d');
        this.charts.invocation = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Allowed', 'Denied'],
                datasets: [{
                    data: [today_stats.allowed, today_stats.denied],
                    backgroundColor: ['#10b981', '#ef4444'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = today_stats.total_invocations;
                                const percent = total > 0 ? Math.round(100 * value / total) : 0;
                                return `${label}: ${value} (${percent}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    renderRiskChart() {
        const canvas = this.container.querySelector('#cap-risk-chart');
        if (!canvas) return;

        const { risk_distribution } = this.stats;

        // Destroy existing chart
        if (this.charts.risk) {
            this.charts.risk.destroy();
        }

        const ctx = canvas.getContext('2d');
        this.charts.risk = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
                datasets: [{
                    data: [
                        risk_distribution.LOW || 0,
                        risk_distribution.MEDIUM || 0,
                        risk_distribution.HIGH || 0,
                        risk_distribution.CRITICAL || 0
                    ],
                    backgroundColor: [
                        '#10b981',  // green
                        '#f59e0b',  // orange
                        '#ef4444',  // red
                        '#b91c1c'   // dark red
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                return `${label}: ${value} capabilities`;
                            }
                        }
                    }
                }
            }
        });
    }

    renderError(message) {
        const metricsGrid = this.container.querySelector('#cap-metrics-grid');
        if (metricsGrid) {
            metricsGrid.innerHTML = `
                <div class="error-message" style="grid-column: 1 / -1;">
                    <span class="material-icons md-24">error_outline</span>
                    <p>${message}</p>
                </div>
            `;
        }
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    destroy() {
        // Clear auto-refresh
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CapabilityDashboardView;
}
