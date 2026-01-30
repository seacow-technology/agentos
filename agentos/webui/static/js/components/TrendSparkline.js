/**
 * TrendSparkline - Mini trend chart component
 *
 * Features:
 * - Time series sparkline visualization
 * - Trend direction indicator (up/down/stable)
 * - SVG-based rendering
 * - Responsive sizing
 * - Color customization
 * - Dynamic data updates
 *
 * Task #7 - Governance Dashboard Visualization Components
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class TrendSparkline {
    /**
     * Create a TrendSparkline component
     * @param {Object} options - Configuration options
     * @param {Array<number>} options.data - Data points for the sparkline
     * @param {HTMLElement|string} options.container - Container element or selector
     * @param {string} [options.direction='auto'] - Trend direction: 'up', 'down', 'stable', 'auto'
     * @param {number} [options.width=100] - Width in pixels
     * @param {number} [options.height=30] - Height in pixels
     * @param {string} [options.color='auto'] - Line color (auto=based on direction)
     * @param {number} [options.strokeWidth=2] - Line stroke width
     * @param {boolean} [options.showArrow=true] - Show trend direction arrow
     * @param {boolean} [options.showArea=false] - Show area under line
     */
    constructor(options = {}) {
        this.options = {
            data: options.data || [],
            direction: options.direction || 'auto',
            width: options.width || 100,
            height: options.height || 30,
            color: options.color || 'auto',
            strokeWidth: options.strokeWidth || 2,
            showArrow: options.showArrow !== false,
            showArea: options.showArea || false,
            ...options,
        };

        this.container = typeof options.container === 'string'
            ? document.querySelector(options.container)
            : options.container;

        if (!this.container) {
            throw new Error('TrendSparkline: container is required');
        }

        this.svg = null;
        this.render();
    }

    /**
     * Calculate trend direction from data
     * @returns {string} Trend direction: 'up', 'down', 'stable'
     */
    calculateDirection() {
        if (this.options.direction !== 'auto') {
            return this.options.direction;
        }

        const data = this.options.data;
        if (data.length < 2) {
            return 'stable';
        }

        // Compare first and last values
        const first = data[0];
        const last = data[data.length - 1];
        const change = last - first;
        const threshold = Math.abs(first * 0.05); // 5% threshold

        if (change > threshold) {
            return 'up';
        } else if (change < -threshold) {
            return 'down';
        } else {
            return 'stable';
        }
    }

    /**
     * Get color based on direction
     * @param {string} direction - Trend direction
     * @returns {string} CSS color
     */
    getDirectionColor(direction) {
        if (this.options.color !== 'auto') {
            return this.options.color;
        }

        const colors = {
            up: '#10B981',    // Green
            down: '#EF4444',  // Red
            stable: '#6B7280', // Gray
        };

        return colors[direction] || colors.stable;
    }

    /**
     * Get arrow symbol for direction
     * @param {string} direction - Trend direction
     * @returns {string} Material icon name
     */
    getArrowSymbol(direction) {
        const arrows = {
            up: 'arrow_upward',
            down: 'arrow_downward',
            stable: 'arrow_forward',
        };

        return arrows[direction] || arrows.stable;
    }

    /**
     * Generate SVG path for sparkline
     * @returns {string} SVG path data
     */
    generatePath() {
        const data = this.options.data;
        if (data.length === 0) {
            return '';
        }

        // Calculate bounds
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1; // Avoid division by zero

        // Generate path points
        const padding = 2;
        const width = this.options.width - padding * 2;
        const height = this.options.height - padding * 2;
        const stepX = width / (data.length - 1 || 1);

        const points = data.map((value, index) => {
            const x = padding + index * stepX;
            const y = padding + height - ((value - min) / range) * height;
            return `${x},${y}`;
        });

        // Build path
        const pathData = `M${points.join(' L')}`;
        return pathData;
    }

    /**
     * Generate SVG area path (for filled area under line)
     * @returns {string} SVG path data
     */
    generateAreaPath() {
        const data = this.options.data;
        if (data.length === 0) {
            return '';
        }

        const linePath = this.generatePath();
        const padding = 2;
        const height = this.options.height - padding;

        // Close the path at bottom corners
        const lastX = this.options.width - padding;
        const areaPath = `${linePath} L${lastX},${height} L${padding},${height} Z`;

        return areaPath;
    }

    /**
     * Render the sparkline
     */
    render() {
        const direction = this.calculateDirection();
        const color = this.getDirectionColor(direction);

        // Clear container
        this.container.innerHTML = '';
        this.container.className = `trend-sparkline trend-${direction}`;

        // Create wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'sparkline-wrapper';

        // Create SVG
        this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        this.svg.setAttribute('width', this.options.width);
        this.svg.setAttribute('height', this.options.height);
        this.svg.setAttribute('viewBox', `0 0 ${this.options.width} ${this.options.height}`);
        this.svg.classList.add('sparkline-svg');

        // Add area if enabled
        if (this.options.showArea) {
            const areaPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            areaPath.setAttribute('d', this.generateAreaPath());
            areaPath.setAttribute('fill', color);
            areaPath.setAttribute('opacity', '0.2');
            this.svg.appendChild(areaPath);
        }

        // Add line path
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', this.generatePath());
        path.setAttribute('stroke', color);
        path.setAttribute('stroke-width', this.options.strokeWidth);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');
        this.svg.appendChild(path);

        wrapper.appendChild(this.svg);

        // Add arrow indicator if enabled
        if (this.options.showArrow) {
            const arrow = document.createElement('span');
            arrow.className = "material-icons sparkline-arrow sparkline-arrow-${direction}";
            arrow.textContent = this.getArrowSymbol(direction);
            arrow.style.color = color;
            arrow.style.fontSize = '1rem';
            wrapper.appendChild(arrow);
        }

        this.container.appendChild(wrapper);
    }

    /**
     * Update with new data
     * @param {Array<number>} newData - New data points
     * @param {Object} options - Optional configuration updates
     */
    update(newData, options = {}) {
        this.options.data = newData;

        // Update other options if provided
        Object.assign(this.options, options);

        this.render();
    }

    /**
     * Get current trend direction
     * @returns {string} Current direction
     */
    getDirection() {
        return this.calculateDirection();
    }

    /**
     * Get percentage change
     * @returns {number|null} Percentage change or null if insufficient data
     */
    getPercentageChange() {
        const data = this.options.data;
        if (data.length < 2) {
            return null;
        }

        const first = data[0];
        const last = data[data.length - 1];

        if (first === 0) {
            return null; // Avoid division by zero
        }

        return ((last - first) / Math.abs(first)) * 100;
    }

    /**
     * Destroy the component
     */
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.svg = null;
    }
}

// Export to window
window.TrendSparkline = TrendSparkline;
