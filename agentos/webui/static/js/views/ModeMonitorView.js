/**
 * ModeMonitorView - Frontend monitoring view for Mode System
 *
 * Provides real-time monitoring of mode system alerts and statistics.
 * Features:
 * - Statistics cards showing total alerts, errors, and warnings
 * - Alert list with severity badges and timestamps
 * - Auto-refresh every 10 seconds
 * - Manual refresh button
 */
class ModeMonitorView {
    constructor() {
        this.alerts = [];
        this.stats = {};
        this.refreshInterval = null;
    }

    /**
     * Render the main monitoring interface
     * @param {HTMLElement} container - Container element to render into
     */
    async render(container) {
        container.innerHTML = `
            <div class="mode-monitor">
                <div class="view-header">
                    <div>
                        <h1>shield Mode System Monitor</h1>
                        <p class="text-sm text-gray-600 mt-1">Real-time mode system monitoring and alerts</p>
                    </div>
                    <div class="header-actions">
                        <button id="refresh-btn" class="btn-primary">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Total Alerts</h3>
                        <div class="stat-value" id="total-alerts">0</div>
                    </div>
                    <div class="stat-card">
                        <h3>Recent Errors</h3>
                        <div class="stat-value error" id="recent-errors">0</div>
                    </div>
                    <div class="stat-card">
                        <h3>Warnings</h3>
                        <div class="stat-value warning" id="warnings">0</div>
                    </div>
                </div>

                <div class="alerts-section">
                    <h3>Recent Alerts</h3>
                    <div id="alerts-list"></div>
                </div>
            </div>
        `;

        // Attach event listeners
        this.attachEventListeners();

        // Initial load
        await this.loadAlerts();

        // Start auto-refresh
        this.startAutoRefresh();
    }

    /**
     * Attach event listeners to UI elements
     */
    attachEventListeners() {
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadAlerts();
            });
        }
    }

    /**
     * Load alerts from API
     */
    async loadAlerts() {
        try {
            const response = await fetch('/api/mode/alerts');

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            this.alerts = data.alerts || [];
            this.stats = data.stats || {};

            this.updateStats();
            this.renderAlerts();
        } catch (error) {
            console.error('Failed to load alerts:', error);
            this.showError('Failed to load alerts: ' + error.message);
        }
    }

    /**
     * Update statistics cards
     */
    updateStats() {
        const totalAlertsEl = document.getElementById('total-alerts');
        const recentErrorsEl = document.getElementById('recent-errors');
        const warningsEl = document.getElementById('warnings');

        if (totalAlertsEl) {
            totalAlertsEl.textContent = this.stats.total_alerts || 0;
        }

        if (recentErrorsEl) {
            recentErrorsEl.textContent =
                this.stats.severity_breakdown?.error || 0;
        }

        if (warningsEl) {
            warningsEl.textContent =
                this.stats.severity_breakdown?.warning || 0;
        }
    }

    /**
     * Render alerts list
     */
    renderAlerts() {
        const container = document.getElementById('alerts-list');

        if (!container) {
            return;
        }

        if (this.alerts.length === 0) {
            container.innerHTML = '<div class="no-alerts">No alerts</div>';
            return;
        }

        container.innerHTML = this.alerts.map(alert => `
            <div class="alert-item ${alert.severity}">
                <div class="alert-header">
                    <span class="severity-badge ${alert.severity}">${alert.severity}</span>
                    <span class="mode-badge">${alert.mode_id}</span>
                    <span class="timestamp">${this.formatTimestamp(alert.timestamp)}</span>
                </div>
                <div class="alert-body">
                    <strong>${alert.operation}</strong>: ${this.escapeHtml(alert.message)}
                </div>
            </div>
        `).join('');
    }

    /**
     * Format timestamp for display
     * @param {string} timestamp - ISO timestamp string
     * @returns {string} Formatted timestamp
     */
    formatTimestamp(timestamp) {
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch (error) {
            return timestamp;
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Show error message to user
     * @param {string} message - Error message
     */
    showError(message) {
        const container = document.getElementById('alerts-list');
        if (container) {
            container.innerHTML = `
                <div class="alert-item error">
                    <div class="alert-body">
                        <strong>Error</strong>: ${this.escapeHtml(message)}
                    </div>
                </div>
            `;
        }
    }

    /**
     * Start auto-refresh (every 10 seconds)
     */
    startAutoRefresh() {
        // Clear any existing interval
        this.stopAutoRefresh();

        this.refreshInterval = setInterval(() => {
            this.loadAlerts();
        }, 10000); // 10 seconds
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
     * Cleanup when view is destroyed
     */
    destroy() {
        this.stopAutoRefresh();
    }
}

export default ModeMonitorView;
