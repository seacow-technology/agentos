/**
 * PerformanceMonitor - Real-time performance monitoring widget
 *
 * Displays real-time performance metrics in a floating panel:
 * - FPS (Frames per second)
 * - Memory usage (if available)
 * - Event processing rate
 * - Render latency
 *
 * Features:
 * - Minimal overhead
 * - Draggable widget
 * - Collapsible/expandable
 * - Auto-hide on idle
 *
 * Usage:
 * ```javascript
 * const monitor = new PerformanceMonitor({
 *     position: 'bottom-right',
 *     autoHide: false
 * });
 *
 * monitor.show();
 *
 * // Track custom metrics
 * monitor.trackEvent('event_received');
 * monitor.trackRender(123); // 123ms render time
 * ```
 */

export class PerformanceMonitor {
    /**
     * Create performance monitor
     *
     * @param {Object} [options] - Configuration
     * @param {string} [options.position='bottom-right'] - Widget position
     * @param {boolean} [options.autoHide=false] - Auto-hide when idle
     * @param {number} [options.hideDelay=5000] - Auto-hide delay in ms
     * @param {boolean} [options.collapsed=false] - Start collapsed
     */
    constructor(options = {}) {
        this.options = {
            position: 'bottom-right',
            autoHide: false,
            hideDelay: 5000,
            collapsed: false,
            ...options
        };

        // State
        this.isVisible = false;
        this.isCollapsed = this.options.collapsed;
        this.isDragging = false;

        // Metrics
        this.fps = 0;
        this.memory = null;
        this.eventRate = 0;
        this.renderLatency = 0;

        // Counters
        this.frameCount = 0;
        this.lastFrameTime = performance.now();
        this.eventCount = 0;
        this.lastEventTime = performance.now();
        this.renderTimes = [];

        // DOM
        this.widget = null;

        // Timers
        this.updateTimer = null;
        this.hideTimer = null;
        this.rafId = null;

        this.init();
    }

    /**
     * Initialize monitor
     */
    init() {
        this.createWidget();
        this.setupEventListeners();
        this.startMonitoring();
    }

    /**
     * Create widget DOM
     */
    createWidget() {
        this.widget = document.createElement('div');
        this.widget.className = 'performance-monitor';
        this.widget.style.cssText = `
            position: fixed;
            ${this._getPositionStyles()}
            z-index: 99999;
            background: rgba(0, 0, 0, 0.85);
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            padding: 8px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
            min-width: 150px;
            cursor: move;
            user-select: none;
            display: none;
        `;

        this.widget.innerHTML = `
            <div class="perf-header" style="margin-bottom: 4px; border-bottom: 1px solid #0f0; padding-bottom: 4px; display: flex; justify-content: space-between;">
                <span>bolt Performance</span>
                <div>
                    <button class="perf-btn perf-collapse" style="background: none; border: none; color: #0f0; cursor: pointer; padding: 0 4px;">−</button>
                    <button class="perf-btn perf-close" style="background: none; border: none; color: #0f0; cursor: pointer; padding: 0 4px;">close</button>
                </div>
            </div>
            <div class="perf-content">
                <div class="perf-metric">FPS: <span class="perf-fps">--</span></div>
                <div class="perf-metric">Memory: <span class="perf-memory">--</span></div>
                <div class="perf-metric">Events/s: <span class="perf-event-rate">--</span></div>
                <div class="perf-metric">Render: <span class="perf-render-latency">--</span>ms</div>
            </div>
        `;

        document.body.appendChild(this.widget);

        // Store metric elements
        this.fpsEl = this.widget.querySelector('.perf-fps');
        this.memoryEl = this.widget.querySelector('.perf-memory');
        this.eventRateEl = this.widget.querySelector('.perf-event-rate');
        this.renderLatencyEl = this.widget.querySelector('.perf-render-latency');
        this.contentEl = this.widget.querySelector('.perf-content');
        this.collapseBtn = this.widget.querySelector('.perf-collapse');
    }

    /**
     * Get position styles
     *
     * @returns {string} CSS position styles
     */
    _getPositionStyles() {
        const positions = {
            'top-left': 'top: 10px; left: 10px;',
            'top-right': 'top: 10px; right: 10px;',
            'bottom-left': 'bottom: 10px; left: 10px;',
            'bottom-right': 'bottom: 10px; right: 10px;'
        };

        return positions[this.options.position] || positions['bottom-right'];
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Close button
        const closeBtn = this.widget.querySelector('.perf-close');
        closeBtn.addEventListener('click', () => this.hide());

        // Collapse button
        this.collapseBtn.addEventListener('click', () => this.toggleCollapse());

        // Dragging
        this.widget.addEventListener('mousedown', (e) => this._startDrag(e));
        document.addEventListener('mousemove', (e) => this._drag(e));
        document.addEventListener('mouseup', () => this._endDrag());

        // Auto-hide
        if (this.options.autoHide) {
            this.widget.addEventListener('mouseenter', () => this._cancelAutoHide());
            this.widget.addEventListener('mouseleave', () => this._scheduleAutoHide());
        }
    }

    /**
     * Start monitoring
     */
    startMonitoring() {
        // FPS monitoring (using RAF)
        this.rafId = requestAnimationFrame(() => this._measureFPS());

        // Update metrics every second
        this.updateTimer = setInterval(() => {
            this._updateMetrics();
        }, 1000);
    }

    /**
     * Measure FPS
     */
    _measureFPS() {
        const now = performance.now();
        const delta = now - this.lastFrameTime;

        this.frameCount++;

        // Calculate FPS every second
        if (delta >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / delta);
            this.frameCount = 0;
            this.lastFrameTime = now;
        }

        // Continue measuring
        this.rafId = requestAnimationFrame(() => this._measureFPS());
    }

    /**
     * Update metrics display
     */
    _updateMetrics() {
        // FPS
        this.fpsEl.textContent = this.fps;
        this._colorizeMetric(this.fpsEl, this.fps, 50, 30); // Green > 50, Yellow > 30, Red < 30

        // Memory (if available)
        if (performance.memory) {
            const usedMB = (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(1);
            const totalMB = (performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(1);
            this.memoryEl.textContent = `${usedMB}/${totalMB} MB`;

            const memoryPercent = (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100;
            this._colorizeMetric(this.memoryEl, 100 - memoryPercent, 50, 20); // Invert (less usage = better)
        } else {
            this.memoryEl.textContent = 'N/A';
        }

        // Event rate
        const now = performance.now();
        const deltaSeconds = (now - this.lastEventTime) / 1000;
        this.eventRate = deltaSeconds > 0 ? Math.round(this.eventCount / deltaSeconds) : 0;
        this.eventRateEl.textContent = this.eventRate;
        this._colorizeMetric(this.eventRateEl, 100 - this.eventRate, 50, 10); // Invert (less events = less load)

        // Reset event counter
        this.eventCount = 0;
        this.lastEventTime = now;

        // Render latency (average of last 10 renders)
        if (this.renderTimes.length > 0) {
            const avg = this.renderTimes.reduce((a, b) => a + b, 0) / this.renderTimes.length;
            this.renderLatency = Math.round(avg);
            this.renderLatencyEl.textContent = this.renderLatency;
            this._colorizeMetric(this.renderLatencyEl, 100 - this.renderLatency, 80, 50); // Invert (less time = better)
            this.renderTimes = [];
        } else {
            this.renderLatencyEl.textContent = '--';
        }
    }

    /**
     * Colorize metric based on thresholds
     *
     * @param {HTMLElement} element - Element to colorize
     * @param {number} value - Metric value
     * @param {number} greenThreshold - Green threshold
     * @param {number} yellowThreshold - Yellow threshold
     */
    _colorizeMetric(element, value, greenThreshold, yellowThreshold) {
        if (value >= greenThreshold) {
            element.style.color = '#0f0'; // Green
        } else if (value >= yellowThreshold) {
            element.style.color = '#ff0'; // Yellow
        } else {
            element.style.color = '#f00'; // Red
        }
    }

    /**
     * Track event
     */
    trackEvent() {
        this.eventCount++;
    }

    /**
     * Track render time
     *
     * @param {number} timeMs - Render time in milliseconds
     */
    trackRender(timeMs) {
        this.renderTimes.push(timeMs);
        if (this.renderTimes.length > 10) {
            this.renderTimes.shift();
        }
    }

    /**
     * Show widget
     */
    show() {
        this.isVisible = true;
        this.widget.style.display = 'block';

        if (this.options.autoHide) {
            this._scheduleAutoHide();
        }
    }

    /**
     * Hide widget
     */
    hide() {
        this.isVisible = false;
        this.widget.style.display = 'none';
        this._cancelAutoHide();
    }

    /**
     * Toggle visibility
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    /**
     * Toggle collapse
     */
    toggleCollapse() {
        this.isCollapsed = !this.isCollapsed;
        this.contentEl.style.display = this.isCollapsed ? 'none' : 'block';
        this.collapseBtn.textContent = this.isCollapsed ? '+' : '−';
    }

    /**
     * Start drag
     */
    _startDrag(e) {
        if (e.target.classList.contains('perf-btn')) {
            return; // Don't drag when clicking buttons
        }

        this.isDragging = true;
        this.dragOffsetX = e.clientX - this.widget.offsetLeft;
        this.dragOffsetY = e.clientY - this.widget.offsetTop;
        this.widget.style.cursor = 'grabbing';
    }

    /**
     * Drag
     */
    _drag(e) {
        if (!this.isDragging) return;

        const x = e.clientX - this.dragOffsetX;
        const y = e.clientY - this.dragOffsetY;

        this.widget.style.left = `${x}px`;
        this.widget.style.top = `${y}px`;
        this.widget.style.right = 'auto';
        this.widget.style.bottom = 'auto';
    }

    /**
     * End drag
     */
    _endDrag() {
        if (this.isDragging) {
            this.isDragging = false;
            this.widget.style.cursor = 'move';
        }
    }

    /**
     * Schedule auto-hide
     */
    _scheduleAutoHide() {
        this._cancelAutoHide();
        this.hideTimer = setTimeout(() => {
            this.hide();
        }, this.options.hideDelay);
    }

    /**
     * Cancel auto-hide
     */
    _cancelAutoHide() {
        if (this.hideTimer) {
            clearTimeout(this.hideTimer);
            this.hideTimer = null;
        }
    }

    /**
     * Destroy monitor
     */
    destroy() {
        // Stop monitoring
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
        }

        if (this.updateTimer) {
            clearInterval(this.updateTimer);
        }

        this._cancelAutoHide();

        // Remove widget
        if (this.widget && this.widget.parentNode) {
            this.widget.parentNode.removeChild(this.widget);
        }

        this.widget = null;
    }
}

// Export as default
export default PerformanceMonitor;

// Also expose globally for non-module usage
if (typeof window !== 'undefined') {
    window.PerformanceMonitor = PerformanceMonitor;
}
