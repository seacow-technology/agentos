/**
 * ConnectionStatus Component - Real-time connection status indicator
 *
 * Displays connection state for EventStreamService with visual indicators
 * and reconnection countdown.
 *
 * States:
 * - circle Connected (realtime)
 * - circle Connecting...
 * - circle Reconnecting (attempt N/M, retry in Xs)
 * - circle Disconnected
 * - cancel Error
 *
 * Usage:
 * ```javascript
 * import ConnectionStatus from './components/ConnectionStatus.js';
 *
 * const status = new ConnectionStatus({
 *     container: document.getElementById('status-container'),
 *     compact: false,
 *     showStats: true
 * });
 *
 * // Update from EventStreamService
 * eventStream.options.onStateChange = (state) => {
 *     status.setState(state);
 * };
 * ```
 */

export class ConnectionStatus {
    /**
     * Create connection status indicator
     *
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.container - Container element
     * @param {boolean} [options.compact=false] - Use compact layout
     * @param {boolean} [options.showStats=false] - Show statistics
     * @param {boolean} [options.showReconnectTimer=true] - Show reconnect countdown
     */
    constructor(options = {}) {
        this.options = {
            container: null,
            compact: false,
            showStats: false,
            showReconnectTimer: true,
            ...options
        };

        if (!this.options.container) {
            throw new Error('ConnectionStatus: container is required');
        }

        // State
        this.state = 'disconnected';
        this.reconnectAttempt = 0;
        this.maxReconnectAttempts = Infinity;
        this.reconnectDelay = 0;
        this.reconnectTimer = null;
        this.stats = {
            eventsReceived: 0,
            reconnects: 0,
            errors: 0,
            gapsDetected: 0,
            gapsRecovered: 0
        };

        // Elements
        this.element = null;
        this.indicatorElement = null;
        this.messageElement = null;
        this.statsElement = null;
        this.timerElement = null;

        this._render();
    }

    /**
     * Set connection state
     *
     * @param {string} state - Connection state
     * @param {Object} [meta] - Additional metadata
     * @param {number} [meta.reconnectAttempt] - Current reconnect attempt
     * @param {number} [meta.maxReconnectAttempts] - Max reconnect attempts
     * @param {number} [meta.reconnectDelay] - Reconnect delay (ms)
     */
    setState(state, meta = {}) {
        this.state = state;
        this.reconnectAttempt = meta.reconnectAttempt || 0;
        this.maxReconnectAttempts = meta.maxReconnectAttempts || Infinity;
        this.reconnectDelay = meta.reconnectDelay || 0;

        this._update();

        // Start reconnect countdown if reconnecting
        if (state === 'reconnecting' && this.reconnectDelay > 0 && this.options.showReconnectTimer) {
            this._startReconnectTimer();
        } else {
            this._stopReconnectTimer();
        }
    }

    /**
     * Update statistics
     *
     * @param {Object} stats - Statistics object
     */
    updateStats(stats) {
        this.stats = { ...this.stats, ...stats };
        if (this.options.showStats) {
            this._updateStats();
        }
    }

    /**
     * Destroy component
     */
    destroy() {
        this._stopReconnectTimer();
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
    }

    // ============================================
    // Private Methods
    // ============================================

    /**
     * Render component
     */
    _render() {
        const container = this.options.container;
        container.innerHTML = '';

        this.element = document.createElement('div');
        this.element.className = `connection-status ${this.options.compact ? 'compact' : ''}`;

        // Indicator
        this.indicatorElement = document.createElement('div');
        this.indicatorElement.className = 'connection-status-indicator';
        this.element.appendChild(this.indicatorElement);

        // Message
        this.messageElement = document.createElement('div');
        this.messageElement.className = 'connection-status-message';
        this.element.appendChild(this.messageElement);

        // Timer (for reconnecting)
        if (this.options.showReconnectTimer) {
            this.timerElement = document.createElement('div');
            this.timerElement.className = 'connection-status-timer';
            this.element.appendChild(this.timerElement);
        }

        // Stats
        if (this.options.showStats) {
            this.statsElement = document.createElement('div');
            this.statsElement.className = 'connection-status-stats';
            this.element.appendChild(this.statsElement);
        }

        container.appendChild(this.element);
        this._update();
    }

    /**
     * Update component display
     */
    _update() {
        // Update indicator
        this.indicatorElement.className = `connection-status-indicator state-${this.state}`;
        this.indicatorElement.textContent = this._getIndicatorIcon();

        // Update message
        this.messageElement.textContent = this._getStateMessage();

        // Update timer
        if (this.timerElement) {
            this.timerElement.textContent = '';
        }
    }

    /**
     * Get indicator icon for state
     */
    _getIndicatorIcon() {
        const icons = {
            connected: 'circle',
            connecting: 'circle',
            reconnecting: 'circle',
            disconnected: 'circle',
            error: 'cancel'
        };
        return icons[this.state] || 'circle';
    }

    /**
     * Get state message
     */
    _getStateMessage() {
        const messages = {
            connected: 'Connected (realtime)',
            connecting: 'Connecting...',
            reconnecting: this._getReconnectMessage(),
            disconnected: 'Disconnected',
            error: 'Connection error'
        };
        return messages[this.state] || 'Unknown';
    }

    /**
     * Get reconnect message
     */
    _getReconnectMessage() {
        const maxAttempts = this.maxReconnectAttempts === Infinity
            ? '∞'
            : this.maxReconnectAttempts;

        return `Reconnecting (attempt ${this.reconnectAttempt}/${maxAttempts})`;
    }

    /**
     * Update statistics display
     */
    _updateStats() {
        if (!this.statsElement) {
            return;
        }

        const statsHtml = `
            <div class="connection-status-stats-item">
                <span class="label">Events:</span>
                <span class="value">${this.stats.eventsReceived}</span>
            </div>
            <div class="connection-status-stats-item">
                <span class="label">Reconnects:</span>
                <span class="value">${this.stats.reconnects}</span>
            </div>
            <div class="connection-status-stats-item">
                <span class="label">Errors:</span>
                <span class="value">${this.stats.errors}</span>
            </div>
            <div class="connection-status-stats-item">
                <span class="label">Gaps:</span>
                <span class="value">${this.stats.gapsDetected}</span>
            </div>
        `;

        this.statsElement.innerHTML = statsHtml;
    }

    /**
     * Start reconnect countdown timer
     */
    _startReconnectTimer() {
        this._stopReconnectTimer();

        if (!this.timerElement || this.reconnectDelay <= 0) {
            return;
        }

        const startTime = Date.now();
        const endTime = startTime + this.reconnectDelay;

        const updateTimer = () => {
            const now = Date.now();
            const remaining = Math.max(0, endTime - now);
            const seconds = Math.ceil(remaining / 1000);

            if (remaining > 0) {
                this.timerElement.textContent = `Retry in ${seconds}s`;
                this.reconnectTimer = setTimeout(updateTimer, 100);
            } else {
                this.timerElement.textContent = '';
            }
        };

        updateTimer();
    }

    /**
     * Stop reconnect countdown timer
     */
    _stopReconnectTimer() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.timerElement) {
            this.timerElement.textContent = '';
        }
    }
}

// Export as default
export default ConnectionStatus;
