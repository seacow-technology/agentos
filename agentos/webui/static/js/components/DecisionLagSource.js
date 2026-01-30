/**
 * DecisionLagSource Component
 *
 * Displays decision lag statistics with data source indicators (v21 columns vs payload JSON)
 *
 * Usage:
 *   const container = document.querySelector('#lag-container');
 *   const lagSource = new DecisionLagSource(container);
 *   lagSource.render(lagData);
 */
class DecisionLagSource {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            showSamples: true,
            showCoverage: true,
            showStatistics: true,
            ...options
        };
    }

    /**
     * Render decision lag data with source indicators
     *
     * @param {Object} lagData - Decision lag statistics from API
     * @param {number} lagData.p50 - P50 percentile (seconds)
     * @param {number} lagData.p95 - P95 percentile (seconds)
     * @param {number} lagData.count - Sample count
     * @param {Array} lagData.samples - Sample data with source tags
     * @param {string} lagData.query_method - "columns" or "payload_fallback"
     * @param {number} lagData.redundant_column_coverage - Coverage percentage (0.0-1.0)
     */
    render(lagData) {
        if (!lagData) {
            this.container.innerHTML = '<div class="empty-state">No lag data available</div>';
            return;
        }

        const {
            p50,
            p95,
            count,
            samples = [],
            query_method,
            redundant_column_coverage
        } = lagData;

        const coverage = (redundant_column_coverage * 100).toFixed(1);
        const isOptimized = query_method === 'columns';

        let html = `
            <div class="decision-lag-source">
                <!-- Overall Query Method -->
                <div class="lag-query-method">
                    <span class="label">Query Method:</span>
                    ${this.renderQueryMethodBadge(query_method)}
                </div>
        `;

        // Statistics
        if (this.options.showStatistics) {
            html += `
                <div class="lag-statistics">
                    <div class="stat-item">
                        <span class="stat-label">P50</span>
                        <span class="stat-value">${p50 ? (p50 * 1000).toFixed(0) + 'ms' : 'N/A'}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">P95</span>
                        <span class="stat-value">${p95 ? (p95 * 1000).toFixed(0) + 'ms' : 'N/A'}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Count</span>
                        <span class="stat-value">${count}</span>
                    </div>
                </div>
            `;
        }

        // Coverage Progress Bar (only for v21+ mode)
        if (this.options.showCoverage && isOptimized) {
            const coverageClass = parseFloat(coverage) > 90 ? 'coverage-excellent' :
                                  parseFloat(coverage) > 50 ? 'coverage-good' : 'coverage-poor';

            html += `
                <div class="lag-coverage">
                    <div class="coverage-header">
                        <span class="coverage-label">Redundant Column Coverage:</span>
                        <span class="coverage-percent">${coverage}%</span>
                    </div>
                    <div class="coverage-progress">
                        <div class="coverage-bar ${coverageClass}" style="width: ${coverage}%"></div>
                    </div>
                    <div class="coverage-description">
                        ${this.getCoverageDescription(parseFloat(coverage))}
                    </div>
                </div>
            `;
        }

        // Sample Data with Source Tags
        if (this.options.showSamples && samples.length > 0) {
            html += `
                <div class="lag-samples">
                    <div class="samples-header">High-Lag Samples (Top ${samples.length}):</div>
                    <div class="samples-list">
                        ${samples.map(sample => this.renderSample(sample)).join('')}
                    </div>
                </div>
            `;
        }

        html += `</div>`;

        this.container.innerHTML = html;
    }

    /**
     * Render query method badge
     * @param {string} method - "columns" or "payload_fallback"
     * @returns {string} HTML string
     */
    renderQueryMethodBadge(method) {
        if (method === 'columns') {
            return `
                <span class="badge badge-success" title="v21+ Fast Path: Querying redundant columns (~10x faster)">
                    <span class="material-icons md-16">bolt</span>
                    Fast Path (Columns)
                </span>
            `;
        } else {
            return `
                <span class="badge badge-secondary" title="v20 Compatibility: Extracting from payload JSON">
                    <span class="material-icons md-16">description</span>
                    Compatibility (Payload)
                </span>
            `;
        }
    }

    /**
     * Render individual sample with source tag
     * @param {Object} sample - Sample data
     * @param {string} sample.decision_id - Decision ID
     * @param {number} sample.lag_ms - Lag in milliseconds
     * @param {string} sample.source - "columns" or "payload"
     * @returns {string} HTML string
     */
    renderSample(sample) {
        const { decision_id, lag_ms, source } = sample;
        const isColumns = source === 'columns';

        const badge = isColumns
            ? `<span class="source-badge source-columns" title="Fast path: v21 redundant columns (Decision: ${decision_id})">
                   <span class="material-icons md-12">bolt</span> ${lag_ms}ms
               </span>`
            : `<span class="source-badge source-payload" title="Compatibility: Payload JSON extraction (Decision: ${decision_id})">
                   <span class="material-icons md-12">description</span> ${lag_ms}ms
               </span>`;

        return `
            <div class="sample-item">
                ${badge}
            </div>
        `;
    }

    /**
     * Get coverage description based on percentage
     * @param {number} coverage - Coverage percentage (0-100)
     * @returns {string} Description text
     */
    getCoverageDescription(coverage) {
        if (coverage > 90) {
            return '<span class="coverage-desc-excellent"><span class="material-icons md-18">check_circle</span> Excellent: Most records use v21 fast path</span>';
        } else if (coverage > 50) {
            return '<span class="coverage-desc-good"><span class="material-icons md-18">warning</span> Good: Partial optimization active</span>';
        } else {
            return '<span class="coverage-desc-poor"><span class="material-icons md-18">cancel</span> Poor: Consider running backfill migration</span>';
        }
    }

    /**
     * Clean up component
     */
    destroy() {
        this.container.innerHTML = '';
    }
}

// Export to global scope
window.DecisionLagSource = DecisionLagSource;
