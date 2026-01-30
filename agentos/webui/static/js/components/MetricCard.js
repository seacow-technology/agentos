/**
 * MetricCard - Metric display card component
 *
 * Features:
 * - Display key metric with value
 * - Trend indicator (up/down/stable)
 * - Trend percentage
 * - Loading state
 * - Error state
 * - Mini sparkline integration
 * - Customizable styling
 *
 * Task #7 - Governance Dashboard Visualization Components
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class MetricCard {
    /**
     * Create a MetricCard component
     * @param {Object} options - Configuration options
     * @param {string} options.title - Card title
     * @param {string|number} options.value - Main metric value
     * @param {HTMLElement|string} options.container - Container element or selector
     * @param {string} [options.trend=null] - Trend direction: 'up', 'down', 'stable', null
     * @param {number} [options.trendValue=null] - Trend percentage value
     * @param {Array<number>} [options.sparklineData=null] - Optional sparkline data
     * @param {boolean} [options.loading=false] - Loading state
     * @param {string} [options.error=null] - Error message
     * @param {string} [options.subtitle=null] - Optional subtitle text
     * @param {string} [options.icon=null] - Optional icon
     * @param {string} [options.iconType='emoji'] - Icon type: 'emoji' or 'material'
     * @param {string} [options.size='medium'] - Size: 'small', 'medium', 'large'
     */
    constructor(options = {}) {
        this.options = {
            title: options.title || 'Metric',
            value: options.value || '0',
            trend: options.trend || null,
            trendValue: options.trendValue || null,
            sparklineData: options.sparklineData || null,
            loading: options.loading || false,
            error: options.error || null,
            subtitle: options.subtitle || null,
            icon: options.icon || null,
            iconType: options.iconType || 'emoji',
            size: options.size || 'medium',
            ...options,
        };

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        if (!this.container) {
            throw new Error('MetricCard: container is required');
        }

        this.element = null;
        this.sparkline = null;
        this.render();
    }

    /**
     * Get trend configuration
     * @param {string} trend - Trend direction
     * @returns {Object} Trend configuration
     */
    getTrendConfig(trend) {
        const configs = {
            up: {
                icon: 'arrow_upward',
                color: '#10B981',
                label: 'increase',
                cssClass: 'metric-trend-up',
            },
            down: {
                icon: 'arrow_downward',
                color: '#EF4444',
                label: 'decrease',
                cssClass: 'metric-trend-down',
            },
            stable: {
                icon: 'arrow_forward',
                color: '#6B7280',
                label: 'stable',
                cssClass: 'metric-trend-stable',
            },
        };

        return configs[trend] || null;
    }

    /**
     * Format trend value
     * @param {number} value - Trend value
     * @returns {string} Formatted trend value
     */
    formatTrendValue(value) {
        if (value === null || value === undefined) {
            return '';
        }

        const absValue = Math.abs(value);
        const sign = value >= 0 ? '+' : '-';
        return `${sign}${absValue.toFixed(1)}%`;
    }

    /**
     * Render the card
     */
    render() {
        // Clear container
        this.container.innerHTML = '';

        // Create card element
        this.element = document.createElement('div');
        this.element.className = `metric-card metric-card-${this.options.size}`;

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

        // Render normal state
        this.renderContent();
        this.container.appendChild(this.element);
    }

    /**
     * Render loading state
     */
    renderLoading() {
        this.element.classList.add('metric-card-loading');
        this.element.innerHTML = `
            <div class="metric-card-header">
                <div class="metric-card-title">${this.options.title}</div>
            </div>
            <div class="metric-card-body">
                <div class="metric-card-loading-spinner">
                    <div class="spinner"></div>
                </div>
                <div class="metric-card-loading-text">Loading...</div>
            </div>
        `;
    }

    /**
     * Render error state
     */
    renderError() {
        this.element.classList.add('metric-card-error');
        this.element.innerHTML = `
            <div class="metric-card-header">
                <div class="metric-card-title">${this.options.title}</div>
            </div>
            <div class="metric-card-body">
                <div class="metric-card-error-icon"><span class="material-icons md-18">warning</span></div>
                <div class="metric-card-error-text">${this.options.error}</div>
            </div>
        `;
    }

    /**
     * Render card content
     */
    renderContent() {
        // Header
        const header = document.createElement('div');
        header.className = 'metric-card-header';

        if (this.options.icon) {
            const icon = document.createElement('span');
            icon.className = 'metric-card-icon';
            if (this.options.iconType === 'material') {
                icon.classList.add('material-icons');
                icon.textContent = this.options.icon;
            } else {
                icon.textContent = this.options.icon;
            }
            header.appendChild(icon);
        }

        const title = document.createElement('div');
        title.className = 'metric-card-title';
        title.textContent = this.options.title;
        header.appendChild(title);

        this.element.appendChild(header);

        // Body
        const body = document.createElement('div');
        body.className = 'metric-card-body';

        // Value
        const valueRow = document.createElement('div');
        valueRow.className = 'metric-card-value-row';

        const value = document.createElement('div');
        value.className = 'metric-card-value';
        value.textContent = this.options.value;
        valueRow.appendChild(value);

        // Trend indicator
        if (this.options.trend) {
            const trendConfig = this.getTrendConfig(this.options.trend);
            if (trendConfig) {
                const trend = document.createElement('div');
                trend.className = `metric-card-trend ${trendConfig.cssClass}`;
                trend.style.color = trendConfig.color;

                trend.innerHTML = `
                    <span class="material-icons metric-trend-icon" style="font-size: 1rem;">${trendConfig.icon}</span>
                    <span class="metric-trend-value">${this.formatTrendValue(this.options.trendValue)}</span>
                `;

                valueRow.appendChild(trend);
            }
        }

        body.appendChild(valueRow);

        // Subtitle
        if (this.options.subtitle) {
            const subtitle = document.createElement('div');
            subtitle.className = 'metric-card-subtitle';
            subtitle.textContent = this.options.subtitle;
            body.appendChild(subtitle);
        }

        // Sparkline
        if (this.options.sparklineData && this.options.sparklineData.length > 0) {
            const sparklineContainer = document.createElement('div');
            sparklineContainer.className = 'metric-card-sparkline';
            body.appendChild(sparklineContainer);

            // Create sparkline component
            this.sparkline = new TrendSparkline({
                container: sparklineContainer,
                data: this.options.sparklineData,
                width: 100,
                height: 25,
                showArrow: false,
                showArea: true,
            });
        }

        this.element.appendChild(body);
    }

    /**
     * Update the card
     * @param {Object} newData - New data for the card
     */
    update(newData) {
        // Update options
        Object.assign(this.options, newData);

        // Re-render
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
     * Update value
     * @param {string|number} value - New value
     * @param {Object} options - Optional updates (trend, trendValue, etc.)
     */
    setValue(value, options = {}) {
        this.options.value = value;
        Object.assign(this.options, options);
        this.options.loading = false;
        this.options.error = null;
        this.render();
    }

    /**
     * Update sparkline data
     * @param {Array<number>} data - New sparkline data
     */
    updateSparkline(data) {
        this.options.sparklineData = data;
        if (this.sparkline) {
            this.sparkline.update(data);
        } else {
            this.render();
        }
    }

    /**
     * Destroy the component
     */
    destroy() {
        if (this.sparkline) {
            this.sparkline.destroy();
            this.sparkline = null;
        }

        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }

        this.element = null;
    }
}

// Export to window
window.MetricCard = MetricCard;
