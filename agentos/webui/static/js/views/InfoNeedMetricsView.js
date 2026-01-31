/**
 * InfoNeedMetricsView - InfoNeed Classification Quality Metrics Dashboard
 *
 * Displays quality metrics for InfoNeed classification:
 * - Comm Trigger Rate (how often REQUIRE_COMM is triggered)
 * - False Positive Rate (unnecessary comm requests)
 * - False Negative Rate (missed comm opportunities)
 * - Ambient Hit Rate (AMBIENT_STATE accuracy)
 * - Decision Latency (p50, p95, p99, avg)
 * - Decision Stability (consistency for similar questions)
 *
 * Features:
 * - Time range selection (24h, 7d, 30d, custom)
 * - Manual refresh with last updated time
 * - Trend visualization with Chart.js
 * - Color-coded metric cards (green/yellow/red)
 * - Export functionality
 *
 * Constraints:
 * - Read-only dashboard, no semantic analysis
 * - Pure statistical data from audit logs
 * - No LLM calls, can run offline
 */

class InfoNeedMetricsView {
    constructor(container) {
        this.container = container;
        this.summary = null;
        this.history = null;
        this.currentTimeRange = '24h';
        this.chart = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="info-need-metrics-dashboard">
                <div class="view-header">
                    <div>
                        <h1>InfoNeed Quality Metrics</h1>
                        <p class="text-sm text-gray-600 mt-1">Classification Quality Monitoring</p>
                    </div>
                    <div class="header-actions">
                        <select class="time-range-selector" id="time-range-select">
                            <option value="24h" selected>Last 24 Hours</option>
                            <option value="7d">Last 7 Days</option>
                            <option value="30d">Last 30 Days</option>
                        </select>
                        <button class="btn-refresh" id="metrics-refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                        <button class="btn-secondary" id="metrics-export">
                            <span class="material-icons md-18">download</span> Export
                        </button>
                    </div>
                </div>

                <div class="last-updated" id="last-updated">
                    <!-- Last updated time will be shown here -->
                </div>

                <div class="metrics-grid" id="metrics-grid">
                    <!-- Metric cards will be rendered here -->
                </div>

                <div class="trends-section" id="trends-section">
                    <h2 class="section-title">Trends</h2>
                    <div class="chart-container">
                        <canvas id="metrics-chart"></canvas>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadMetrics();
    }

    setupEventListeners() {
        // Time range selector
        const selector = this.container.querySelector('#time-range-select');
        if (selector) {
            selector.addEventListener('change', (e) => {
                this.currentTimeRange = e.target.value;
                this.loadMetrics();
            });
        }

        // Refresh button
        const refreshBtn = this.container.querySelector('#metrics-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadMetrics());
        }

        // Export button
        const exportBtn = this.container.querySelector('#metrics-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportMetrics());
        }
    }

    async loadMetrics() {
        try {
            // Show loading state
            this.showLoading();

            // Fetch summary and history in parallel
            const [summaryResponse, historyResponse] = await Promise.all([
                fetch(`/api/info-need-metrics/summary?time_range=${this.currentTimeRange}`),
                fetch(`/api/info-need-metrics/history?time_range=${this.currentTimeRange}&granularity=hour`)
            ]);

            const summaryResult = await summaryResponse.json();
            const historyResult = await historyResponse.json();

            if (summaryResult.ok && summaryResult.data) {
                this.summary = summaryResult.data;
                this.history = historyResult.ok ? historyResult.data : null;
                this.renderDashboard();
            } else {
                this.renderError(summaryResult.error || 'Failed to load metrics');
            }
        } catch (error) {
            console.error('Failed to load metrics:', error);
            this.renderError('Failed to connect to metrics API');
        }
    }

    showLoading() {
        const grid = this.container.querySelector('#metrics-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="loading-state">
                    <span class="material-icons md-48 animate-spin">refresh</span>
                    <p>Loading metrics...</p>
                </div>
            `;
        }
    }

    renderDashboard() {
        // Update last updated time
        this.renderLastUpdated();

        // Render metric cards
        this.renderMetricCards();

        // Render trend chart
        this.renderTrendChart();
    }

    renderLastUpdated() {
        const lastUpdatedEl = this.container.querySelector('#last-updated');
        if (lastUpdatedEl && this.summary) {
            const time = new Date(this.summary.last_updated);
            lastUpdatedEl.textContent = `Last updated: ${this.formatTime(time)}`;
        }
    }

    renderMetricCards() {
        const grid = this.container.querySelector('#metrics-grid');
        if (!grid || !this.summary) return;

        const metrics = this.summary.metrics;
        const counts = this.summary.counts;

        grid.innerHTML = `
            ${this.renderMetricCard(
                'Comm Trigger Rate',
                metrics.comm_trigger_rate,
                'how_to_reg',
                'percentage',
                'How often REQUIRE_COMM is triggered',
                { low: 0.15, high: 0.35 }
            )}
            ${this.renderMetricCard(
                'False Positive Rate',
                metrics.false_positive_rate,
                'error_outline',
                'percentage',
                'Unnecessary comm requests',
                { low: 0.10, high: 0.20 },
                true  // lower is better
            )}
            ${this.renderMetricCard(
                'False Negative Rate',
                metrics.false_negative_rate,
                'warning',
                'percentage',
                'Missed comm opportunities',
                { low: 0.15, high: 0.25 },
                true  // lower is better
            )}
            ${this.renderMetricCard(
                'Ambient Hit Rate',
                metrics.ambient_hit_rate,
                'check_circle',
                'percentage',
                'AMBIENT_STATE classification accuracy',
                { low: 0.85, high: 0.95 }
            )}
            ${this.renderLatencyCard(metrics.decision_latency)}
            ${this.renderMetricCard(
                'Decision Stability',
                metrics.decision_stability,
                'trending_flat',
                'percentage',
                'Consistency for similar questions',
                { low: 0.75, high: 0.90 }
            )}
        `;
    }

    renderMetricCard(title, value, icon, format, description, thresholds, lowerIsBetter = false) {
        const formattedValue = this.formatMetricValue(value, format);
        const status = this.getMetricStatus(value, thresholds, lowerIsBetter);
        const statusClass = this.getStatusClass(status);
        const trendIcon = this.getTrendIcon(value, thresholds, lowerIsBetter);

        return `
            <div class="metric-card ${statusClass}">
                <div class="metric-header">
                    <span class="material-icons md-24">${icon}</span>
                    <span class="metric-title">${title}</span>
                </div>
                <div class="metric-value">${formattedValue}</div>
                <div class="metric-description">${description}</div>
                <div class="metric-trend">${trendIcon}</div>
            </div>
        `;
    }

    renderLatencyCard(latency) {
        const avgMs = latency.avg;
        const status = this.getLatencyStatus(avgMs);
        const statusClass = this.getStatusClass(status);

        return `
            <div class="metric-card ${statusClass}">
                <div class="metric-header">
                    <span class="material-icons md-24">speed</span>
                    <span class="metric-title">Decision Latency</span>
                </div>
                <div class="metric-value">${avgMs.toFixed(1)}ms</div>
                <div class="metric-description">Classification performance</div>
                <div class="latency-details">
                    <div class="latency-item">
                        <span class="label">P50:</span>
                        <span class="value">${latency.p50.toFixed(1)}ms</span>
                    </div>
                    <div class="latency-item">
                        <span class="label">P95:</span>
                        <span class="value">${latency.p95.toFixed(1)}ms</span>
                    </div>
                    <div class="latency-item">
                        <span class="label">P99:</span>
                        <span class="value">${latency.p99.toFixed(1)}ms</span>
                    </div>
                    <div class="latency-item">
                        <span class="label">Count:</span>
                        <span class="value">${latency.count}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderTrendChart() {
        if (!this.history || !this.history.data_points || this.history.data_points.length === 0) {
            const trendsSection = this.container.querySelector('#trends-section');
            if (trendsSection) {
                trendsSection.innerHTML = `
                    <h2 class="section-title">Trends</h2>
                    <div class="no-data">No historical data available</div>
                `;
            }
            return;
        }

        const canvas = this.container.querySelector('#metrics-chart');
        if (!canvas) return;

        // Destroy existing chart if any
        if (this.chart) {
            this.chart.destroy();
        }

        const dataPoints = this.history.data_points;
        const labels = dataPoints.map(dp => this.formatChartLabel(dp.timestamp));

        const datasets = [
            {
                label: 'Comm Trigger Rate',
                data: dataPoints.map(dp => dp.comm_trigger_rate * 100),
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4
            },
            {
                label: 'False Positive Rate',
                data: dataPoints.map(dp => dp.false_positive_rate * 100),
                borderColor: '#EF4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                tension: 0.4
            },
            {
                label: 'False Negative Rate',
                data: dataPoints.map(dp => dp.false_negative_rate * 100),
                borderColor: '#F59E0B',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                tension: 0.4
            },
            {
                label: 'Ambient Hit Rate',
                data: dataPoints.map(dp => dp.ambient_hit_rate * 100),
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                tension: 0.4
            },
            {
                label: 'Decision Stability',
                data: dataPoints.map(dp => dp.decision_stability * 100),
                borderColor: '#8B5CF6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                tension: 0.4
            }
        ];

        // Load Chart.js dynamically if not already loaded
        if (typeof Chart === 'undefined') {
            this.loadChartJs().then(() => {
                this.createChart(canvas, labels, datasets);
            });
        } else {
            this.createChart(canvas, labels, datasets);
        }
    }

    createChart(canvas, labels, datasets) {
        this.chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += context.parsed.y.toFixed(2) + '%';
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Percentage (%)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }

    async loadChartJs() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async exportMetrics() {
        try {
            const response = await fetch(`/api/info-need-metrics/export?time_range=${this.currentTimeRange}&format=json`);
            const result = await response.json();

            if (result.ok && result.data) {
                const blob = new Blob([JSON.stringify(result.data.full_metrics, null, 2)], {
                    type: 'application/json'
                });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `info_need_metrics_${this.currentTimeRange}_${Date.now()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                Dialog.alert('Metrics exported successfully!', { title: 'Export Complete' });
            } else {
                Dialog.alert('Export failed: ' + result.error, { title: 'Export Error' });
            }
        } catch (error) {
            console.error('Failed to export metrics:', error);
            Dialog.alert('Export failed: ' + error.message, { title: 'Export Error' });
        }
    }

    // Utility methods

    formatMetricValue(value, format) {
        if (value === null || value === undefined) return 'N/A';

        if (format === 'percentage') {
            return (value * 100).toFixed(1) + '%';
        } else if (format === 'number') {
            return value.toFixed(2);
        } else if (format === 'ms') {
            return value.toFixed(1) + 'ms';
        }

        return value.toString();
    }

    getMetricStatus(value, thresholds, lowerIsBetter = false) {
        if (!thresholds) return 'neutral';

        if (lowerIsBetter) {
            if (value <= thresholds.low) return 'good';
            if (value <= thresholds.high) return 'warning';
            return 'danger';
        } else {
            if (value >= thresholds.high) return 'good';
            if (value >= thresholds.low) return 'warning';
            return 'danger';
        }
    }

    getLatencyStatus(avgMs) {
        if (avgMs <= 150) return 'good';
        if (avgMs <= 300) return 'warning';
        return 'danger';
    }

    getStatusClass(status) {
        return `status-${status}`;
    }

    getTrendIcon(value, thresholds, lowerIsBetter) {
        // For now, just show the current status
        // In the future, we could compare with previous periods
        const status = this.getMetricStatus(value, thresholds, lowerIsBetter);

        if (status === 'good') {
            return '<span class="material-icons md-18 text-green-600">check_circle</span>';
        } else if (status === 'warning') {
            return '<span class="material-icons md-18 text-yellow-600">warning</span>';
        } else if (status === 'danger') {
            return '<span class="material-icons md-18 text-red-600">error</span>';
        }

        return '';
    }

    formatTime(date) {
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;

        return date.toLocaleString();
    }

    formatChartLabel(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        const hours = Math.floor(diff / (1000 * 60 * 60));

        if (hours < 24) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        }
    }

    renderError(message) {
        const grid = this.container.querySelector('#metrics-grid');
        if (!grid) return;

        grid.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48 text-red-600">error</span>
                <h3>Failed to Load Metrics</h3>
                <p class="text-muted">${this.escapeHtml(message)}</p>
                <button class="btn-primary mt-3" onclick="location.reload()">
                    Retry
                </button>
            </div>
        `;
    }

    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    destroy() {
        // Destroy chart
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}
