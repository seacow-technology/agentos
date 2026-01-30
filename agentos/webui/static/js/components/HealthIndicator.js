/**
 * HealthIndicator - System health indicator component
 *
 * Features:
 * - Health percentage display with progress bar
 * - Color-coded thresholds (critical/warning/healthy)
 * - Configurable thresholds
 * - Label and description
 * - Multiple display modes (bar/circular/compact)
 * - Loading and error states
 * - Dynamic updates with smooth transitions
 *
 * Task #7 - Governance Dashboard Visualization Components
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class HealthIndicator {
    /**
     * Create a HealthIndicator component
     * @param {Object} options - Configuration options
     * @param {number} options.percentage - Health percentage (0-100)
     * @param {HTMLElement|string} options.container - Container element or selector
     * @param {string} [options.label='Health'] - Label text
     * @param {string} [options.description=null] - Optional description
     * @param {Object} [options.thresholds] - Threshold configuration
     * @param {number} [options.thresholds.critical=50] - Critical threshold
     * @param {number} [options.thresholds.warning=70] - Warning threshold
     * @param {string} [options.mode='bar'] - Display mode: 'bar', 'circular', 'compact'
     * @param {boolean} [options.showPercentage=true] - Show percentage text
     * @param {boolean} [options.showLabel=true] - Show label
     * @param {boolean} [options.loading=false] - Loading state
     * @param {string} [options.error=null] - Error message
     */
    constructor(options = {}) {
        this.options = {
            percentage: options.percentage || 0,
            label: options.label || 'Health',
            description: options.description || null,
            thresholds: {
                critical: 50,
                warning: 70,
                ...options.thresholds,
            },
            mode: options.mode || 'bar',
            showPercentage: options.showPercentage !== false,
            showLabel: options.showLabel !== false,
            loading: options.loading || false,
            error: options.error || null,
            ...options,
        };

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        if (!this.container) {
            throw new Error('HealthIndicator: container is required');
        }

        this.element = null;
        this.render();
    }

    /**
     * Get health status based on percentage and thresholds
     * @param {number} percentage - Health percentage
     * @returns {Object} Status configuration
     */
    getHealthStatus(percentage) {
        const { critical, warning } = this.options.thresholds;

        if (percentage < critical) {
            return {
                status: 'critical',
                color: '#EF4444',
                label: 'Critical',
                cssClass: 'health-critical',
            };
        } else if (percentage < warning) {
            return {
                status: 'warning',
                color: '#F59E0B',
                label: 'Warning',
                cssClass: 'health-warning',
            };
        } else {
            return {
                status: 'healthy',
                color: '#10B981',
                label: 'Healthy',
                cssClass: 'health-healthy',
            };
        }
    }

    /**
     * Clamp percentage to 0-100 range
     * @param {number} percentage - Input percentage
     * @returns {number} Clamped percentage
     */
    clampPercentage(percentage) {
        return Math.max(0, Math.min(100, percentage));
    }

    /**
     * Render the component
     */
    render() {
        // Clear container
        this.container.innerHTML = '';

        // Create element
        this.element = document.createElement('div');
        this.element.className = `health-indicator health-indicator-${this.options.mode}`;

        // Handle error state
        if (this.options.error) {
            this.renderError();
            this.container.appendChild(this.element);
            return;
        }

        // Handle loading state
        if (this.options.loading) {
            this.renderLoading();
            this.container.appendChild(this.element);
            return;
        }

        // Render based on mode
        switch (this.options.mode) {
            case 'bar':
                this.renderBar();
                break;
            case 'circular':
                this.renderCircular();
                break;
            case 'compact':
                this.renderCompact();
                break;
            default:
                this.renderBar();
        }

        this.container.appendChild(this.element);
    }

    /**
     * Render loading state
     */
    renderLoading() {
        this.element.classList.add('health-indicator-loading');
        this.element.innerHTML = `
            <div class="health-label">${this.options.label}</div>
            <div class="health-loading">
                <div class="spinner"></div>
            </div>
        `;
    }

    /**
     * Render error state
     */
    renderError() {
        this.element.classList.add('health-indicator-error');
        this.element.innerHTML = `
            <div class="health-label">${this.options.label}</div>
            <div class="health-error">
                <span class="material-icons md-18">warning</span>
                <span class="health-error-text">${this.options.error}</span>
            </div>
        `;
    }

    /**
     * Render bar mode
     */
    renderBar() {
        const percentage = this.clampPercentage(this.options.percentage);
        const status = this.getHealthStatus(percentage);

        this.element.classList.add(status.cssClass);

        // Header
        if (this.options.showLabel) {
            const header = document.createElement('div');
            header.className = 'health-header';

            const label = document.createElement('div');
            label.className = 'health-label';
            label.textContent = this.options.label;
            header.appendChild(label);

            if (this.options.showPercentage) {
                const percentageEl = document.createElement('div');
                percentageEl.className = 'health-percentage';
                percentageEl.textContent = `${percentage.toFixed(0)}%`;
                percentageEl.style.color = status.color;
                header.appendChild(percentageEl);
            }

            this.element.appendChild(header);
        }

        // Progress bar
        const barContainer = document.createElement('div');
        barContainer.className = 'health-bar-container';

        const bar = document.createElement('div');
        bar.className = 'health-bar';
        bar.style.width = `${percentage}%`;
        bar.style.backgroundColor = status.color;

        barContainer.appendChild(bar);
        this.element.appendChild(barContainer);

        // Description
        if (this.options.description) {
            const description = document.createElement('div');
            description.className = 'health-description';
            description.textContent = this.options.description;
            this.element.appendChild(description);
        }
    }

    /**
     * Render circular mode (donut chart style)
     */
    renderCircular() {
        const percentage = this.clampPercentage(this.options.percentage);
        const status = this.getHealthStatus(percentage);

        this.element.classList.add(status.cssClass);

        // SVG circle
        const size = 100;
        const strokeWidth = 10;
        const radius = (size - strokeWidth) / 2;
        const circumference = radius * 2 * Math.PI;
        const offset = circumference - (percentage / 100) * circumference;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', size);
        svg.setAttribute('height', size);
        svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
        svg.classList.add('health-circle-svg');

        // Background circle
        const bgCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        bgCircle.setAttribute('cx', size / 2);
        bgCircle.setAttribute('cy', size / 2);
        bgCircle.setAttribute('r', radius);
        bgCircle.setAttribute('stroke', '#E5E7EB');
        bgCircle.setAttribute('stroke-width', strokeWidth);
        bgCircle.setAttribute('fill', 'none');
        svg.appendChild(bgCircle);

        // Progress circle
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', size / 2);
        circle.setAttribute('cy', size / 2);
        circle.setAttribute('r', radius);
        circle.setAttribute('stroke', status.color);
        circle.setAttribute('stroke-width', strokeWidth);
        circle.setAttribute('fill', 'none');
        circle.setAttribute('stroke-dasharray', circumference);
        circle.setAttribute('stroke-dashoffset', offset);
        circle.setAttribute('stroke-linecap', 'round');
        circle.setAttribute('transform', `rotate(-90 ${size / 2} ${size / 2})`);
        circle.classList.add('health-circle-progress');
        svg.appendChild(circle);

        const circleContainer = document.createElement('div');
        circleContainer.className = 'health-circle-container';
        circleContainer.appendChild(svg);

        // Center text
        const centerText = document.createElement('div');
        centerText.className = 'health-circle-text';
        centerText.innerHTML = `
            <div class="health-circle-percentage">${percentage.toFixed(0)}%</div>
            ${this.options.showLabel ? `<div class="health-circle-label">${this.options.label}</div>` : ''}
        `;
        circleContainer.appendChild(centerText);

        this.element.appendChild(circleContainer);

        // Description
        if (this.options.description) {
            const description = document.createElement('div');
            description.className = 'health-description';
            description.textContent = this.options.description;
            this.element.appendChild(description);
        }
    }

    /**
     * Render compact mode
     */
    renderCompact() {
        const percentage = this.clampPercentage(this.options.percentage);
        const status = this.getHealthStatus(percentage);

        this.element.classList.add(status.cssClass);
        this.element.classList.add('health-compact');

        const content = document.createElement('div');
        content.className = 'health-compact-content';

        // Status dot
        const dot = document.createElement('span');
        dot.className = 'health-compact-dot';
        dot.style.backgroundColor = status.color;
        content.appendChild(dot);

        // Label
        if (this.options.showLabel) {
            const label = document.createElement('span');
            label.className = 'health-compact-label';
            label.textContent = this.options.label;
            content.appendChild(label);
        }

        // Percentage
        if (this.options.showPercentage) {
            const percentageEl = document.createElement('span');
            percentageEl.className = 'health-compact-percentage';
            percentageEl.textContent = `${percentage.toFixed(0)}%`;
            percentageEl.style.color = status.color;
            content.appendChild(percentageEl);
        }

        this.element.appendChild(content);
    }

    /**
     * Update the health percentage
     * @param {number} newPercentage - New percentage value
     * @param {Object} options - Optional configuration updates
     */
    update(newPercentage, options = {}) {
        this.options.percentage = newPercentage;
        Object.assign(this.options, options);
        this.options.loading = false;
        this.options.error = null;
        this.render();
    }

    /**
     * Set loading state
     * @param {boolean} loading - Loading state
     */
    setLoading(loading) {
        this.options.loading = loading;
        this.options.error = null;
        this.render();
    }

    /**
     * Set error state
     * @param {string} error - Error message
     */
    setError(error) {
        this.options.error = error;
        this.options.loading = false;
        this.render();
    }

    /**
     * Get current status
     * @returns {Object} Current health status
     */
    getStatus() {
        return this.getHealthStatus(this.options.percentage);
    }

    /**
     * Destroy the component
     */
    destroy() {
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
        this.element = null;
    }
}

// Export to window
window.HealthIndicator = HealthIndicator;
