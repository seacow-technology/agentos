/**
 * WriterStats Component - SQLiteWriter Monitoring Dashboard
 *
 * Displays real-time monitoring metrics for the SQLiteWriter:
 * - Queue status and backlog
 * - Write performance metrics (latency, throughput)
 * - Retry and failure statistics
 * - Health status indicators
 *
 * Features:
 * - Auto-refresh every 5 seconds
 * - Alert thresholds for queue backlog and failures
 * - Expandable advanced metrics
 * - Color-coded health indicators
 *
 * Task #17 - P2: Writer Monitoring (Minimum Viable)
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class WriterStats {
    /**
     * Create a WriterStats component
     * @param {Object} options - Configuration options
     * @param {HTMLElement|string} options.container - Container element or selector
     * @param {number} [options.refreshInterval=5000] - Refresh interval in milliseconds
     * @param {boolean} [options.autoStart=true] - Auto-start refresh on creation
     */
    constructor(options = {}) {
        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        if (!this.container) {
            throw new Error('WriterStats: container is required');
        }

        this.refreshInterval = options.refreshInterval || 5000;
        this.autoStart = options.autoStart !== false;
        this.intervalId = null;
        this.lastUpdateTime = null;

        if (this.autoStart) {
            this.start();
        }
    }

    /**
     * Fetch writer stats from API
     * @returns {Promise<Object>} Writer statistics
     */
    async fetchStats() {
        try {
            const response = await fetch('/api/writer-stats');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching writer stats:', error);
            throw error;
        }
    }

    /**
     * Determine alert level based on metrics
     * @param {Object} stats - Writer statistics
     * @returns {string} Alert level: 'success', 'warning', 'critical', 'error'
     */
    getAlertLevel(stats) {
        if (stats.error) {
            return 'error';
        }

        // Critical: queue backlog > 100 or failures detected
        if (stats.queue_size > 100 || stats.failed_writes > 0) {
            return 'critical';
        }

        // Warning: queue backlog > 50 or high retry rate
        if (stats.queue_size > 50) {
            return 'warning';
        }

        const retryRate = stats.total_writes > 0
            ? (stats.total_retries / stats.total_writes) : 0;
        if (retryRate > 0.05) { // >5% retry rate
            return 'warning';
        }

        return 'success';
    }

    /**
     * Get alert messages based on metrics
     * @param {Object} stats - Writer statistics
     * @returns {Array<string>} Alert messages
     */
    getAlertMessages(stats) {
        const messages = [];

        if (stats.failed_writes > 0) {
            const rate = stats.total_writes > 0
                ? ((stats.failed_writes / stats.total_writes) * 100).toFixed(1)
                : '0';
            messages.push(`Failed writes: ${stats.failed_writes} (${rate}% failure rate)`);
        }

        if (stats.queue_size > 100) {
            messages.push(`Queue backlog critical: ${stats.queue_size} items (threshold: 100)`);
        } else if (stats.queue_size > 50) {
            messages.push(`Queue backlog elevated: ${stats.queue_size} items (threshold: 50)`);
        }

        const retryRate = stats.total_writes > 0
            ? (stats.total_retries / stats.total_writes) : 0;
        if (retryRate > 0.05) {
            messages.push(`High retry rate: ${(retryRate * 100).toFixed(1)}% (threshold: 5%)`);
        }

        return messages;
    }

    /**
     * Format uptime duration
     * @param {number} seconds - Uptime in seconds
     * @returns {string} Formatted uptime
     */
    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const mins = Math.floor((seconds % 3600) / 60);

        if (days > 0) return `${days}d ${hours}h`;
        if (hours > 0) return `${hours}h ${mins}m`;
        return `${mins}m ${Math.floor(seconds % 60)}s`;
    }

    /**
     * Render the component
     * @param {Object} stats - Writer statistics
     */
    render(stats) {
        if (!stats) {
            this.renderLoading();
            return;
        }

        if (stats.error) {
            this.renderError(stats);
            return;
        }

        const alertLevel = this.getAlertLevel(stats);
        const alertMessages = this.getAlertMessages(stats);
        const statusBadge = this.getStatusBadge(alertLevel);

        this.container.innerHTML = `
            <div class="writer-stats-card">
                <div class="writer-stats-header">
                    <div class="writer-stats-title">
                        <span class="material-icons md-18">save</span>
                        <span>SQLiteWriter Stats</span>
                    </div>
                    ${statusBadge}
                </div>

                <div class="writer-stats-body">
                    ${alertMessages.length > 0 ? this.renderAlerts(alertMessages, alertLevel) : ''}

                    <div class="writer-stats-grid">
                        ${this.renderMetric('Queue Size', stats.queue_size, stats.queue_size > 50 ? 'warning' : 'normal')}
                        ${this.renderMetric('Total Writes', stats.total_writes.toLocaleString())}
                        ${this.renderMetric('Avg Latency', `${stats.avg_write_latency_ms}ms`)}
                        ${this.renderMetric('Throughput', `${stats.throughput_per_second.toFixed(1)}/s`)}
                    </div>

                    <details class="writer-stats-advanced">
                        <summary>Advanced Metrics</summary>
                        <div class="writer-stats-grid writer-stats-advanced-grid">
                            ${this.renderMetric('Queue High Water', stats.queue_high_water_mark)}
                            ${this.renderMetric('Total Retries', stats.total_retries, stats.total_retries > 0 ? 'warning' : 'normal')}
                            ${this.renderMetric('Failed Writes', stats.failed_writes, stats.failed_writes > 0 ? 'critical' : 'normal')}
                            ${this.renderMetric('Uptime', this.formatUptime(stats.uptime_seconds))}
                        </div>
                    </details>

                    <div class="writer-stats-footer">
                        <span class="material-icons md-18">schedule</span>
                        Last updated: ${this.lastUpdateTime ? this.lastUpdateTime.toLocaleTimeString() : 'Never'}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render loading state
     */
    renderLoading() {
        this.container.innerHTML = `
            <div class="writer-stats-card">
                <div class="writer-stats-header">
                    <div class="writer-stats-title">
                        <span class="material-icons md-18">save</span>
                        <span>SQLiteWriter Stats</span>
                    </div>
                </div>
                <div class="writer-stats-body">
                    <div class="writer-stats-loading">
                        <div class="spinner"></div>
                        <p>Loading writer statistics...</p>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render error state
     * @param {Object} stats - Error stats object
     */
    renderError(stats) {
        this.container.innerHTML = `
            <div class="writer-stats-card writer-stats-error">
                <div class="writer-stats-header">
                    <div class="writer-stats-title">
                        <span class="material-icons md-18">save</span>
                        <span>SQLiteWriter Stats</span>
                    </div>
                    <span class="writer-stats-badge writer-stats-badge-error">Error</span>
                </div>
                <div class="writer-stats-body">
                    <div class="writer-stats-error-content">
                        <span class="material-icons md-18">warning</span>
                        <div>
                            <div class="writer-stats-error-title">Failed to load writer stats</div>
                            <div class="writer-stats-error-message">${stats.error || 'Unknown error'}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render status badge
     * @param {string} level - Alert level
     * @returns {string} Badge HTML
     */
    getStatusBadge(level) {
        const configs = {
            success: { label: 'Healthy', icon: 'check_circle' },
            warning: { label: 'Warning', icon: 'warning' },
            critical: { label: 'Critical', icon: 'error' },
            error: { label: 'Error', icon: 'error' }
        };

        const config = configs[level] || configs.error;
        return `
            <span class="writer-stats-badge writer-stats-badge-${level}">
                <span class="material-icons writer-stats-badge-icon">${config.icon}</span>
                ${config.label}
            </span>
        `;
    }

    /**
     * Render alert messages
     * @param {Array<string>} messages - Alert messages
     * @param {string} level - Alert level
     * @returns {string} Alerts HTML
     */
    renderAlerts(messages, level) {
        const icon = level === 'critical' ? 'error' : 'warning';
        return `
            <div class="writer-stats-alerts writer-stats-alert-${level}">
                <span class="material-icons">${icon}</span>
                <ul>
                    ${messages.map(msg => `<li>${msg}</li>`).join('')}
                </ul>
            </div>
        `;
    }

    /**
     * Render a single metric
     * @param {string} label - Metric label
     * @param {string|number} value - Metric value
     * @param {string} [status='normal'] - Metric status: 'normal', 'warning', 'critical'
     * @returns {string} Metric HTML
     */
    renderMetric(label, value, status = 'normal') {
        return `
            <div class="writer-stats-metric writer-stats-metric-${status}">
                <div class="writer-stats-metric-label">${label}</div>
                <div class="writer-stats-metric-value">${value}</div>
            </div>
        `;
    }

    /**
     * Start auto-refresh
     */
    async start() {
        // Fetch immediately
        try {
            const stats = await this.fetchStats();
            this.lastUpdateTime = new Date();
            this.render(stats);
        } catch (error) {
            this.render({ error: error.message });
        }

        // Setup periodic refresh
        this.intervalId = setInterval(async () => {
            try {
                const stats = await this.fetchStats();
                this.lastUpdateTime = new Date();
                this.render(stats);
            } catch (error) {
                console.error('Failed to refresh writer stats:', error);
                // Don't replace the UI on refresh errors, just log
            }
        }, this.refreshInterval);
    }

    /**
     * Stop auto-refresh
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    /**
     * Destroy the component
     */
    destroy() {
        this.stop();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export to window
window.WriterStats = WriterStats;
