/**
 * KnowledgeHealthView - Health monitoring for RAG system
 *
 * Phase 4: RAG Health
 * Coverage: GET /api/knowledge/health
 */

class KnowledgeHealthView {
    constructor(container) {
        this.container = container;
        this.refreshInterval = null;

        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div class="knowledge-health-view">
                <div class="view-header">
                    <div class="header-title-group">
                        <h1 style="font-size: 24px; font-weight: 600; margin: 0;">Knowledge Health</h1>
                        <p class="text-sm text-gray-600 mt-1">Knowledge base health metrics and diagnostics</p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="health-refresh">
                            <span class="icon"><span class="material-icons md-18">refresh</span></span> Refresh
                        </button>
                    </div>
                </div>

                <!-- Loading State -->
                <div id="health-loading" class="loading-spinner" style="display: none;">
                    <div class="spinner"></div>
                    <span>Loading health data...</span>
                </div>

                <!-- Error State -->
                <div id="health-error" class="error-message" style="display: none;">
                    <span class="error-icon"><span class="material-icons md-18">warning</span></span>
                    <div class="error-text" id="health-error-text"></div>
                </div>

                <!-- Health Content -->
                <div id="health-content" style="display: none; padding: 24px;">
                    <!-- Metrics Grid -->
                    <div class="metrics-grid">
                        <div class="metric-card" id="metric-index-lag">
                            <div class="metric-label">Index Lag</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                        <div class="metric-card" id="metric-fail-rate">
                            <div class="metric-label">Fail Rate (7d)</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                        <div class="metric-card" id="metric-empty-hit">
                            <div class="metric-label">Empty Hit Rate</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                        <div class="metric-card" id="metric-coverage">
                            <div class="metric-label">File Coverage</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                        <div class="metric-card" id="metric-chunks">
                            <div class="metric-label">Total Chunks</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                        <div class="metric-card" id="metric-files">
                            <div class="metric-label">Total Files</div>
                            <div class="metric-value">-</div>
                            <div class="metric-status">-</div>
                        </div>
                    </div>

                    <!-- Health Checks Section -->
                    <div style="margin-top: 32px;">
                        <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 16px;">Health Checks</h3>
                        <div class="health-check-list" id="health-checks">
                            <!-- Health checks will be rendered here -->
                        </div>
                    </div>

                    <!-- Bad Smells Section -->
                    <div style="margin-top: 32px;" id="bad-smells-section">
                        <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 16px;">Bad Smells</h3>
                        <div id="bad-smells-container">
                            <!-- Bad smells will be rendered here -->
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.setupEventListeners();
        this.loadHealthData();
    }

    setupEventListeners() {
        const refreshBtn = this.container.querySelector('#health-refresh');
        refreshBtn.addEventListener('click', () => {
            this.loadHealthData();
        });
    }

    async loadHealthData() {
        const loadingEl = this.container.querySelector('#health-loading');
        const errorEl = this.container.querySelector('#health-error');
        const contentEl = this.container.querySelector('#health-content');

        // Show loading
        loadingEl.style.display = 'flex';
        errorEl.style.display = 'none';
        contentEl.style.display = 'none';

        try {
            const response = await fetch('/api/knowledge/health');
            const data = await response.json();

            if (data.ok) {
                this.renderHealthData(data.data);
                loadingEl.style.display = 'none';
                contentEl.style.display = 'block';
            } else {
                throw new Error(data.error || 'Failed to load health data');
            }
        } catch (error) {
            console.error('Error loading health data:', error);
            loadingEl.style.display = 'none';
            errorEl.style.display = 'flex';
            this.container.querySelector('#health-error-text').textContent = error.message;
        }
    }

    renderHealthData(data) {
        const { metrics, checks, bad_smells } = data;

        // Render metrics
        this.renderMetrics(metrics);

        // Render health checks
        this.renderHealthChecks(checks);

        // Render bad smells
        this.renderBadSmells(bad_smells);
    }

    renderMetrics(metrics) {
        // Index Lag
        const indexLagCard = this.container.querySelector('#metric-index-lag');
        const lagHours = (metrics.index_lag_seconds / 3600).toFixed(1);
        const lagValue = indexLagCard.querySelector('.metric-value');
        const lagStatus = indexLagCard.querySelector('.metric-status');

        lagValue.textContent = `${lagHours}h`;

        // Remove existing action button if any
        const existingLagBtn = indexLagCard.querySelector('.metric-action-btn');
        if (existingLagBtn) {
            existingLagBtn.remove();
        }

        if (metrics.index_lag_seconds < 3600) {
            lagStatus.textContent = 'Fresh';
            lagStatus.className = 'metric-status ok';
        } else if (metrics.index_lag_seconds < 86400) {
            lagStatus.textContent = 'Needs refresh';
            lagStatus.className = 'metric-status warn';
            // Add refresh action button
            this.addActionButton(indexLagCard, 'refresh', 'Refresh index', () => this.triggerRefresh());
        } else {
            lagStatus.textContent = 'Stale';
            lagStatus.className = 'metric-status error';
            // Add refresh action button
            this.addActionButton(indexLagCard, 'refresh', 'Refresh index', () => this.triggerRefresh());
        }

        // Fail Rate
        const failRateCard = this.container.querySelector('#metric-fail-rate');
        const failValue = failRateCard.querySelector('.metric-value');
        const failStatus = failRateCard.querySelector('.metric-status');

        failValue.textContent = `${(metrics.fail_rate_7d * 100).toFixed(1)}%`;

        if (metrics.fail_rate_7d < 0.05) {
            failStatus.textContent = 'Good';
            failStatus.className = 'metric-status ok';
        } else if (metrics.fail_rate_7d < 0.10) {
            failStatus.textContent = 'Elevated';
            failStatus.className = 'metric-status warn';
        } else {
            failStatus.textContent = 'High';
            failStatus.className = 'metric-status error';
        }

        // Empty Hit Rate
        const emptyHitCard = this.container.querySelector('#metric-empty-hit');
        const emptyValue = emptyHitCard.querySelector('.metric-value');
        const emptyStatus = emptyHitCard.querySelector('.metric-status');

        emptyValue.textContent = `${(metrics.empty_hit_rate * 100).toFixed(1)}%`;

        if (metrics.empty_hit_rate < 0.10) {
            emptyStatus.textContent = 'Good';
            emptyStatus.className = 'metric-status ok';
        } else if (metrics.empty_hit_rate < 0.20) {
            emptyStatus.textContent = 'Elevated';
            emptyStatus.className = 'metric-status warn';
        } else {
            emptyStatus.textContent = 'High';
            emptyStatus.className = 'metric-status error';
        }

        // File Coverage
        const coverageCard = this.container.querySelector('#metric-coverage');
        const coverageValue = coverageCard.querySelector('.metric-value');
        const coverageStatus = coverageCard.querySelector('.metric-status');

        coverageValue.textContent = `${(metrics.file_coverage * 100).toFixed(1)}%`;

        // Remove existing action button if any
        const existingCoverageBtn = coverageCard.querySelector('.metric-action-btn');
        if (existingCoverageBtn) {
            existingCoverageBtn.remove();
        }

        if (metrics.file_coverage > 0.90) {
            coverageStatus.textContent = 'Excellent';
            coverageStatus.className = 'metric-status ok';
        } else if (metrics.file_coverage > 0.70) {
            coverageStatus.textContent = 'Good';
            coverageStatus.className = 'metric-status warn';
            // Add improve action button
            this.addActionButton(coverageCard, 'build', 'Rebuild index', () => this.triggerRebuild());
        } else {
            coverageStatus.textContent = 'Poor';
            coverageStatus.className = 'metric-status error';
            // Add improve action button
            this.addActionButton(coverageCard, 'build', 'Rebuild index', () => this.triggerRebuild());
        }

        // Total Chunks
        const chunksCard = this.container.querySelector('#metric-chunks');
        const chunksValue = chunksCard.querySelector('.metric-value');
        const chunksStatus = chunksCard.querySelector('.metric-status');

        chunksValue.textContent = metrics.total_chunks.toLocaleString();
        chunksStatus.textContent = 'Indexed';
        chunksStatus.className = 'metric-status info';

        // Total Files
        const filesCard = this.container.querySelector('#metric-files');
        const filesValue = filesCard.querySelector('.metric-value');
        const filesStatus = filesCard.querySelector('.metric-status');

        filesValue.textContent = metrics.total_files.toLocaleString();
        filesStatus.textContent = 'Tracked';
        filesStatus.className = 'metric-status info';
    }

    renderHealthChecks(checks) {
        const container = this.container.querySelector('#health-checks');

        if (!checks || checks.length === 0) {
            container.innerHTML = '<div class="text-muted">No health checks available</div>';
            return;
        }

        container.innerHTML = checks.map(check => `
            <div class="health-check-item">
                <div class="health-check-icon status-${check.status}">
                    ${this.getStatusIcon(check.status)}
                </div>
                <div class="health-check-content">
                    <div class="health-check-name">${this.escapeHtml(check.name)}</div>
                    <div class="health-check-message">${this.escapeHtml(check.message)}</div>
                </div>
                <div class="health-check-badge status-${check.status}">${check.status.toUpperCase()}</div>
            </div>
        `).join('');
    }

    renderBadSmells(badSmells) {
        const section = this.container.querySelector('#bad-smells-section');
        const container = this.container.querySelector('#bad-smells-container');

        if (!badSmells || badSmells.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';

        container.innerHTML = badSmells.map(smell => `
            <div class="bad-smell-card severity-${smell.severity}">
                <div class="bad-smell-header">
                    <div class="bad-smell-icon severity-${smell.severity}">
                        ${this.getSeverityIcon(smell.severity)}
                    </div>
                    <div class="bad-smell-info">
                        <div class="bad-smell-type">${this.formatSmellType(smell.type)}</div>
                        <div class="bad-smell-count">${smell.count} ${smell.count === 1 ? 'occurrence' : 'occurrences'}</div>
                    </div>
                    <div class="bad-smell-badge severity-${smell.severity}">${smell.severity.toUpperCase()}</div>
                </div>
                <div class="bad-smell-details">
                    <div class="details-label">Details:</div>
                    <ul class="details-list">
                        ${smell.details.map(detail => `<li>${this.escapeHtml(detail)}</li>`).join('')}
                        ${smell.count > smell.details.length ? `<li><em>+${smell.count - smell.details.length} more...</em></li>` : ''}
                    </ul>
                </div>
                <div class="bad-smell-suggestion">
                    <span class="suggestion-icon">lightbulb</span>
                    <span>${this.escapeHtml(smell.suggestion)}</span>
                </div>
            </div>
        `).join('');
    }

    getStatusIcon(status) {
        switch (status) {
            case 'ok':
                return '<span class="material-icons md-20">check_circle</span>';
            case 'warn':
                return '<span class="material-icons md-20">warning</span>';
            case 'error':
                return '<span class="material-icons md-20">error</span>';
            default:
                return '<span class="material-icons md-20">help</span>';
        }
    }

    getSeverityIcon(severity) {
        switch (severity) {
            case 'info':
                return '<span class="material-icons md-24">info</span>';
            case 'warn':
                return '<span class="material-icons md-24">warning</span>';
            case 'error':
                return '<span class="material-icons md-24">error</span>';
            default:
                return '<span class="material-icons md-24">help</span>';
        }
    }

    formatSmellType(type) {
        return type.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    addActionButton(card, icon, tooltip, onClick) {
        const actionBtn = document.createElement('button');
        actionBtn.className = 'metric-action-btn';
        actionBtn.title = tooltip;
        actionBtn.innerHTML = `<span class="material-icons md-18">${icon}</span>`;
        actionBtn.addEventListener('click', onClick);

        // Insert after metric-status
        const statusEl = card.querySelector('.metric-status');
        if (statusEl) {
            statusEl.parentNode.insertBefore(actionBtn, statusEl.nextSibling);
        }
    }

    async triggerRefresh() {
        const confirmed = await Dialog.confirm('Execute incremental index refresh? This will scan and index modified files.', {
            title: 'Confirm Refresh',
            confirmText: 'Execute Refresh',
            cancelText: 'Cancel'
        });

        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch('/api/knowledge/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: 'incremental'
                }),
            });

            const data = await response.json();

            if (data.ok) {
                window.showToast('Index refresh task started', 'success');
                // Reload health data after a short delay
                setTimeout(() => this.loadHealthData(), 2000);
            } else {
                throw new Error(data.error || 'Failed to start task');
            }
        } catch (error) {
            console.error('Error triggering refresh:', error);
            window.showToast(`Failed to start refresh task: ${error.message}`, 'error');
        }
    }

    async triggerRebuild() {
        const confirmed = await Dialog.confirm('Execute full index rebuild? This will rescan and index all files, which may take a long time.', {
            title: 'Confirm Rebuild',
            confirmText: 'Execute Rebuild',
            cancelText: 'Cancel'
        });

        if (!confirmed) {
            return;
        }

        try {
            const response = await fetch('/api/knowledge/jobs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: 'rebuild'
                }),
            });

            const data = await response.json();

            if (data.ok) {
                window.showToast('Index rebuild task started', 'success');
                // Reload health data after a short delay
                setTimeout(() => this.loadHealthData(), 2000);
            } else {
                throw new Error(data.error || 'Failed to start task');
            }
        } catch (error) {
            console.error('Error triggering rebuild:', error);
            window.showToast(`Failed to start rebuild task: ${error.message}`, 'error');
        }
    }

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

// Export for use in main.js
window.KnowledgeHealthView = KnowledgeHealthView;
